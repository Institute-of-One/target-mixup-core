"""Verify every freeze record against the files as released.

Each FREEZE*.json lists SHA-256 hashes of code, design documents and data at the moment of freezing.
A file passes if it is byte-identical; an append-only JSONL file passes if some prefix of its lines is
byte-identical (later sets were appended, earlier lines untouched). Any other difference must be listed,
with its reason, in freeze_exceptions.json; an unlisted difference or a missing file fails.

    python verify_freezes.py --root <repository root>
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def prefix_match(data, digest):
    """Number of leading lines whose bytes hash to digest, or 0."""
    lines = data.splitlines(keepends=True)
    acc = b''
    for k, line in enumerate(lines, 1):
        acc += line
        if sha(acc) == digest:
            return k
    return 0


def locate(root, freeze_path, section, name):
    """Code in core/ (or core/paper), design documents in protocol/, data next to the freeze record."""
    candidates = {'files': [root / 'core' / name, root / 'core' / 'paper' / name, freeze_path.parent / name],
                  'gui': [root / 'gui_snapshot' / name],
                  'design': [root / 'protocol' / name],
                  'data': [freeze_path.parent / name]}.get(section, [freeze_path.parent / name])
    return next((p for p in candidates if p.exists()), None)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = ap.parse_args(argv)
    root = args.root
    exc_path = root / 'results' / 'freeze_exceptions.json'
    exceptions = json.loads(exc_path.read_text(encoding='utf-8')) if exc_path.exists() else {}
    failed = 0
    for fz in sorted(p for p in root.glob('results/**/*.json') if 'FREEZE' in p.name):   # case-sensitive
        record = json.loads(fz.read_text(encoding='utf-8'))
        if isinstance(record.get('design'), str):          # single-document form: {"design": name, "sha256": ...}
            record = dict(record, design={record['design']: record['sha256']})
        rel = fz.relative_to(root).as_posix()
        print(f'== {rel} ({record.get("frozen_utc", record.get("frozen", "?"))})')
        for section in ('files', 'gui', 'design', 'data'):
            for name, digest in (record.get(section) or {}).items():
                key = f'{rel}::{section}/{name}'
                p = locate(root, fz, section, name)
                if p is None:
                    status = 'MISSING'
                else:
                    data = p.read_bytes()
                    if sha(data) == digest:
                        status = 'OK'
                    elif p.suffix == '.jsonl' and (k := prefix_match(data, digest)):
                        status = f'OK (append-only: first {k} of {len(data.splitlines())} lines)'
                    else:
                        status = 'CHANGED'
                if status in ('MISSING', 'CHANGED'):
                    if key in exceptions:
                        status += f' — documented: {exceptions[key]}'
                    else:
                        failed += 1
                        status += ' — NOT DOCUMENTED'
                print(f'  {section}/{name}: {status}')
    print('FAIL' if failed else 'PASS', f'({failed} undocumented differences)')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
