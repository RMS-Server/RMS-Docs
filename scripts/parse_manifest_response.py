#!/usr/bin/env python3
"""Parse /api/sync manifest responses and print selected entries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, List


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse manifest response JSON")
    parser.add_argument(
        "response",
        nargs="?",
        type=Path,
        help="Path to the JSON response returned by /api/sync; reads stdin when omitted",
    )
    parser.add_argument(
        "--field",
        choices=["upload", "deleted", "files"],
        default="upload",
        help="Which manifest field to emit; defaults to upload",
    )
    parser.add_argument(
        "--prefix",
        default="",
        help="Optional text prefix for each emitted line",
    )
    return parser


def normalize_entries(payload: object, key: str) -> List[str]:
    # Ensure the result always uses simple relative paths for downstream scripts.
    if isinstance(payload, dict):
        items = payload.get(key) or []
    else:
        items = []

    result: List[str] = []
    for entry in items:
        if isinstance(entry, str) and entry:
            result.append(entry)
    return result


def emit_entries(paths: Iterable[str], prefix: str) -> None:
    for path in paths:
        sys.stdout.write(f"{prefix}{path}\n")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.response is None:
        try:
            payload = json.load(sys.stdin)
        except json.JSONDecodeError as exc:
            parser.error(f"failed to parse JSON from stdin: {exc}")
    else:
        with args.response.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

    entries = normalize_entries(payload, args.field)
    if args.field == "upload" and not entries and isinstance(payload, list):
        # Maintain backward compatibility with legacy array responses.
        entries = [item for item in payload if isinstance(item, str) and item]

    emit_entries(entries, prefix=args.prefix)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
