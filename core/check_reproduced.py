"""Compare regenerated JSON results with the released copies as parsed data (line endings and
whitespace may differ between platforms; values may not).

    python check_reproduced.py --released <dir> --regenerated <dir> results/expB/paper_results.json ...
"""
import argparse
import json
import sys
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--released', required=True, type=Path)
    ap.add_argument('--regenerated', required=True, type=Path)
    ap.add_argument('files', nargs='+')
    args = ap.parse_args(argv)
    bad = 0
    for f in args.files:
        a = json.loads((args.released / f).read_text(encoding='utf-8'))
        b = json.loads((args.regenerated / f).read_text(encoding='utf-8'))
        ok = a == b
        bad += not ok
        print(('same      ' if ok else 'DIFFERENT ') + f)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
