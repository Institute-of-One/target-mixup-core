"""Compare regenerated results with the released copies as data, not as bytes (line endings and
whitespace may differ between platforms; values may not).

JSON is compared parsed. CSV is compared row by row, because two of the manuscript's
supplementary tables are released as CSV and were not being compared at all.

    python check_reproduced.py --released <dir> --regenerated <dir> expB/paper_results.json ...
"""
import argparse
import csv
import json
import sys
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--released', required=True, type=Path)
    ap.add_argument('--regenerated', required=True, type=Path)
    ap.add_argument('--ignore', action='append', default=[],
                    help='a top-level key to drop from both sides, for a field '
                         'that records when the step ran and so differs every run')
    ap.add_argument('files', nargs='+')
    args = ap.parse_args(argv)
    bad = 0
    for f in args.files:
        released = (args.released / f).read_text(encoding='utf-8')
        regenerated = (args.regenerated / f).read_text(encoding='utf-8')
        if f.endswith('.csv'):
            a = list(csv.reader(released.splitlines()))
            b = list(csv.reader(regenerated.splitlines()))
        else:
            a, b = json.loads(released), json.loads(regenerated)
            for k in args.ignore:
                if isinstance(a, dict):
                    a.pop(k, None)
                if isinstance(b, dict):
                    b.pop(k, None)
        ok = a == b
        bad += not ok
        print(('same      ' if ok else 'DIFFERENT ') + f)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
