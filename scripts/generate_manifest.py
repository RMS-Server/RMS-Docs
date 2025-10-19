#!/usr/bin/env python3
"""Generate a manifest payload for the /api/sync endpoint."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Iterator, Tuple

# Chunk size keeps memory usage predictable during hashing.
_CHUNK_SIZE = 1 << 20
_EXCLUDE_NAMES = {".git", ".github", "__pycache__"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate manifest JSON for /api/sync")
    parser.add_argument(
        "output",
        type=Path,
        help="Path to write the manifest JSON file",
    )
    parser.add_argument(
        "--root",
        dest="root",
        type=Path,
        default=None,
        help="Directory to scan; defaults to ./context when present",
    )
    return parser


def determine_root(candidate: Path | None) -> Path:
    # Prefer the context directory to match server expectations.
    if candidate is not None:
        return candidate.resolve()
    context_dir = Path("context")
    if context_dir.is_dir():
        return context_dir.resolve()
    return Path(".").resolve()


def should_skip(relative: Path) -> bool:
    return any(part in _EXCLUDE_NAMES for part in relative.parts)


def iter_files(root: Path) -> Iterator[Tuple[Path, Path]]:
    # Walk the directory tree while pruning unwanted folders.
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        base = Path(dirpath)
        rel_dir = base.relative_to(root)
        dirnames[:] = [
            name
            for name in dirnames
            if not should_skip(rel_dir / name)
        ]
        for name in filenames:
            relative_path = rel_dir / name
            if should_skip(relative_path):
                continue
            yield base / name, relative_path


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    root = determine_root(args.root)

    files = []

    for absolute, relative in iter_files(root):
        digest = compute_sha256(absolute)
        # Persist manifest entries relative to the sync root.
        files.append({"path": relative.as_posix(), "sha256": digest})

    # Stable ordering keeps downstream comparisons straightforward.
    files.sort(key=lambda item: item["path"])

    # Ensure the output directory exists before writing the manifest file.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump({"files": files}, handle, ensure_ascii=False)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
