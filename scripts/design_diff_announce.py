#!/usr/bin/env python
"""Scan markdown diffs, chunk them via Markdown AST, and dispatch summaries."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set

from markdown_it import MarkdownIt

# Hard-coded interface so the workflow stays deterministic.
OPENAI_ENDPOINT = "https://api.deepseek.com/v1/chat/completions"
OPENAI_MODEL = "deepseek-chat"
QQ_ENDPOINT = "http://119.23.57.80:53000/_send_group_notice"
QQ_GROUP_ID = 457054386
QQ_MAX_RETRIES = 5
PROMPT_TEMPLATE_PATH = Path(__file__).with_name("design_announce_prompt.txt")


DEFAULT_PROMPT_TEMPLATE = (
    "Review the following Markdown changes and craft a Simplified-Chinese "
    "announcement for RMS players. Use a concise bullet-point summary "
    "suitable for a QQ group announcement.\n"
)


def _load_prompt_template() -> str:
    try:
        return PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        logging.warning(
            "Prompt template file %s missing, falling back to default template",
            PROMPT_TEMPLATE_PATH,
        )
        return DEFAULT_PROMPT_TEMPLATE


PROMPT_TEMPLATE = _load_prompt_template()


@dataclass(frozen=True)
class ChangedFile:
    path: Path
    diff_text: str
    added_lines: Set[int]


@dataclass(frozen=True)
class MarkdownChunk:
    path: Path
    heading_path: str
    start_line: int
    end_line: int
    content: str


@dataclass(frozen=True)
class HeadingFrame:
    level: int
    title: str


# Parser stays global to avoid re-initializing per file.
_MARKDOWN = MarkdownIt("commonmark").enable("table").enable("strikethrough")
_HUNK_PATTERN = re.compile(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Announce markdown diffs through QQ")
    parser.add_argument("--base", help="Base commit for git diff (defaults to HEAD~1 when possible)")
    parser.add_argument("--dry-run", action="store_true", help="Skip API calls and only log payloads")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--key",
        help="API key for the OpenAI-compatible endpoint; overrides environment and default",
    )
    return parser


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(message)s")


def determine_range(base: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    # GitHub returns all-zero SHA when pushing a new tag; treat it as missing.
    if base and base != "0" * 40:
        return f"{base}..HEAD", base
    # When pushing a notice-*-end tag, find the corresponding notice-*-start.
    try:
        result = subprocess.run(
            ["git", "tag", "-l", "notice-*-start", "--sort=-version:refname"],
            check=True,
            capture_output=True,
            text=True,
        )
        tags = [t for t in result.stdout.strip().split("\n") if t]
        if tags:
            start_tag = tags[0]
            logging.info("Using start tag %s as base", start_tag)
            return f"{start_tag}..HEAD", start_tag
    except subprocess.CalledProcessError:
        pass
    # Fall back to the previous commit when no start tag exists.
    try:
        subprocess.run(
            ["git", "rev-parse", "HEAD~1"],
            check=True,
            capture_output=True,
            text=True,
        )
        return "HEAD~1..HEAD", "HEAD~1"
    except subprocess.CalledProcessError:
        return None, None


def gather_changed_files(range_spec: Optional[str]) -> List[ChangedFile]:
    diff_cmd = ["git", "diff", "--unified=3", "--no-color", "--text"]
    if range_spec:
        diff_cmd.append(range_spec)
    # Only markdown files matter and .github noise must never escape.
    diff_cmd += ["--", "*.md", ":(exclude).github/**"]
    logging.debug("Running diff command: %s", " ".join(diff_cmd))
    completed = subprocess.run(diff_cmd, capture_output=True, text=True, check=True)
    return list(_parse_diff_output(completed.stdout))


def get_repo_root() -> Path:
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
    )
    return Path(completed.stdout.strip())


def _parse_diff_output(raw_diff: str) -> Iterable[ChangedFile]:
    current_path: Optional[Path] = None
    current_lines: List[str] = []
    added_lines: Set[int] = set()
    next_line_no = 0
    for line in raw_diff.splitlines():
        if line.startswith("diff --git "):
            if current_path and added_lines:
                yield ChangedFile(current_path, "\n".join(current_lines), set(added_lines))
            current_path = None
            current_lines = [line]
            added_lines = set()
            next_line_no = 0
            continue
        if line.startswith("+++ "):
            current_lines.append(line)
            path_token = line.split(maxsplit=1)[1].strip()
            if path_token == "/dev/null":
                current_path = None
                continue
            rel_path = path_token[2:] if path_token.startswith("b/") else path_token
            path = Path(rel_path)
            if path.parts and path.parts[0] == ".github":
                current_path = None
                continue
            current_path = path
            continue
        if current_path is None:
            continue
        current_lines.append(line)
        if line.startswith("@@ "):
            match = _HUNK_PATTERN.match(line)
            if not match:
                next_line_no = 0
                continue
            start = int(match.group(1))
            span = int(match.group(2) or "1")
            next_line_no = start
            if span == 0:
                next_line_no -= 1
            continue
        if line.startswith("+") and not line.startswith("+++"):
            if next_line_no > 0:
                added_lines.add(next_line_no)
            next_line_no += 1
        elif line.startswith("-") and not line.startswith("---"):
            continue
        else:
            if next_line_no > 0:
                next_line_no += 1
    if current_path and added_lines:
        yield ChangedFile(current_path, "\n".join(current_lines), set(added_lines))


def extract_chunks(changed: ChangedFile, repo_root: Path, base_commit: Optional[str]) -> List[MarkdownChunk]:
    text = _load_file_text(changed.path, repo_root, base_commit)
    if text is None:
        logging.warning("Skipping missing file %s", changed.path)
        return []
    lines = text.splitlines()
    tokens = _MARKDOWN.parse(text)
    chunks: List[MarkdownChunk] = []
    heading_stack: List[HeadingFrame] = []
    pending_heading: Optional[int] = None
    # We stream the AST once, tracking heading frames lazily.
    for token in tokens:
        if token.type == "heading_open":
            level = int(token.tag[1])
            while heading_stack and heading_stack[-1].level >= level:
                heading_stack.pop()
            pending_heading = level
            continue
        if token.type == "inline":
            if pending_heading:
                heading_stack.append(HeadingFrame(pending_heading, token.content.strip()))
                pending_heading = None
            chunk = _inline_to_chunk(token, heading_stack, lines, changed)
            if chunk and _intersects(chunk, changed.added_lines):
                chunks.append(chunk)
            continue
        if token.type == "heading_close":
            pending_heading = None
            continue
    return chunks


def _load_file_text(path: Path, repo_root: Path, base_commit: Optional[str]) -> Optional[str]:
    disk_path = repo_root / path
    try:
        return disk_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        if not base_commit:
            return None
        try:
            return _read_git_blob(base_commit, path)
        except subprocess.CalledProcessError:
            return None


def _read_git_blob(commit: str, path: Path) -> str:
    target = f"{commit}:{path.as_posix()}"
    completed = subprocess.run(
        ["git", "show", target],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout


def _inline_to_chunk(token, heading_stack: Sequence[HeadingFrame], lines: Sequence[str], changed: ChangedFile) -> Optional[MarkdownChunk]:
    if token.map is None:
        return None
    start, end = token.map
    if start == end:
        return None
    snippet = "\n".join(lines[start:end]).strip()
    if not snippet:
        return None
    heading_path = " / ".join(frame.title for frame in heading_stack if frame.title)
    return MarkdownChunk(
        path=changed.path,
        heading_path=heading_path or "(root)",
        start_line=start + 1,
        end_line=end,
        content=snippet,
    )


def _intersects(chunk: MarkdownChunk, added_lines: Set[int]) -> bool:
    for line_no in range(chunk.start_line, chunk.end_line + 1):
        if line_no in added_lines:
            return True
    return False


def summarize_file(
    changed: ChangedFile,
    chunks: Sequence[MarkdownChunk],
    dry_run: bool,
    api_key: str,
) -> str:
    chunk_blobs = []
    for idx, chunk in enumerate(chunks, 1):
        chunk_blobs.append(
            f"### Chunk {idx}: {chunk.heading_path} (lines {chunk.start_line}-{chunk.end_line})\n{chunk.content}\n"
        )
    context_blob = "\n".join(chunk_blobs)
    beijing_now = datetime.utcnow() + timedelta(hours=8)
    beijing_str = beijing_now.strftime("%Y-%m-%d %H:%M:%S")
    user_prompt = (
        f"{PROMPT_TEMPLATE}\n"
        f"Current real-world time in Beijing (UTC+8): {beijing_str}.\n"
        f"Repository-relative path of the changed markdown file: {changed.path}\n"
        "Below are markdown content chunks (AST-based) that contain added lines:\n"
        f"{context_blob}\n"
        "Below is the unified diff for the same file. Use it only to detect substantive content changes and ignore whitespace-only or formatting-only edits:\n"
        f"{changed.diff_text}\n"
    )
    if dry_run:
        logging.info("Dry run prompt for %s", changed.path)
        return "[dry-run] summary skipped"
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are an RMS announcement assistant. Summaries must be concise and written in Simplified Chinese.",
            },
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }
    request = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        response = _http_post(OPENAI_ENDPOINT, request, headers)
        blob = json.loads(response)
        return blob["choices"][0]["message"]["content"]
    except (KeyError, IndexError, json.JSONDecodeError, RuntimeError) as exc:
        logging.error("OpenAI summarize failed for %s: %s", changed.path, exc)
        return "[summary unavailable due to API error]"


def _http_post(url: str, payload: bytes, headers: dict[str, str]) -> str:
    import urllib.request
    from urllib.error import HTTPError, URLError
    from socket import timeout as SocketTimeout

    # Using urllib keeps the dependency surface tiny for Actions.
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")
    except (HTTPError, URLError, SocketTimeout, TimeoutError) as exc:
        raise RuntimeError(f"HTTP request failed: {exc}") from exc


def send_to_qq(message: str, path: Path, dry_run: bool) -> None:
    if dry_run:
        logging.info("Dry run QQ dispatch for %s:\n%s", path, message)
        return
    payload = json.dumps({"group_id": QQ_GROUP_ID, "content": message}).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer rmstoken",
    }
    for attempt in range(1, QQ_MAX_RETRIES + 1):
        try:
            _http_post(QQ_ENDPOINT, payload, headers)
            logging.info("QQ announcement sent for %s on attempt %d", path, attempt)
            return
        except RuntimeError as exc:
            logging.warning(
                "QQ dispatch attempt %d failed for %s: %s", attempt, path, exc
            )
            if attempt == QQ_MAX_RETRIES:
                logging.error(
                    "QQ dispatch giving up for %s after %d attempts",
                    path,
                    QQ_MAX_RETRIES,
                )
                return
            time.sleep(min(5, attempt))


def main() -> int:
    args = build_parser().parse_args()
    configure_logging(args.verbose)
    api_key = args.key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        logging.error("API key is missing; use --key or set OPENAI_API_KEY")
        return 1
    range_spec, base_commit = determine_range(args.base)
    repo_root = get_repo_root()
    changed_files = gather_changed_files(range_spec)
    if not changed_files:
        logging.info("No markdown diffs outside .github detected.")
        return 0
    processed = 0
    for changed in changed_files:
        chunks = extract_chunks(changed, repo_root, base_commit)
        if not chunks:
            continue
        summary = summarize_file(changed, chunks, args.dry_run, api_key)
        send_to_qq(summary, changed.path, args.dry_run)
        processed += 1
    logging.info("Processed %d markdown files.", processed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
