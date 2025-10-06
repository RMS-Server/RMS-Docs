#!/usr/bin/env python3

import hashlib
import json
import os
import sys


def should_skip(relpath):
    return (
        relpath.startswith('.git/')
        or relpath == '.git'
        or relpath.startswith('.github/')
        or relpath == '.github'
    )


def iter_files(root):
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = [
            d
            for d in dirnames
            if not should_skip(os.path.relpath(os.path.join(dirpath, d), root))
        ]
        for name in filenames:
            rel = os.path.relpath(os.path.join(dirpath, name), root)
            if should_skip(rel):
                continue
            yield dirpath, name, rel


def main():
    if len(sys.argv) != 2:
        sys.stderr.write("Usage: generate_manifest.py <output>\n")
        return 1

    target = sys.argv[1]
    files = []

    for dirpath, name, rel in iter_files('.'):
        hasher = hashlib.sha256()
        with open(os.path.join(dirpath, name), 'rb') as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b''):
                hasher.update(chunk)
        files.append({'path': rel, 'sha256': hasher.hexdigest()})

    files.sort(key=lambda item: item['path'])

    with open(target, 'w', encoding='utf-8') as out:
        json.dump({'files': files}, out, ensure_ascii=False)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
