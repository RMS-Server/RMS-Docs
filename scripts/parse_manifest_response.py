#!/usr/bin/env python3

import json
import sys


def main():
    if len(sys.argv) != 2:
        sys.stderr.write("Usage: parse_manifest_response.py <response>\n")
        return 1

    response_path = sys.argv[1]

    with open(response_path, 'r', encoding='utf-8') as fh:
        payload = json.load(fh)

    if isinstance(payload, dict):
        files = payload.get('upload') or payload.get('files') or []
    elif isinstance(payload, list):
        files = payload
    else:
        files = []

    for item in files:
        if isinstance(item, str) and item:
            print(item)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
