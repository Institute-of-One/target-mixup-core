"""Experiment B, step 1: seeded selection of 20 evaluation series with >= 3 targets.

    python expB_select.py --expa <expA dir> --out <expB dir>
"""
import argparse
import json
import random
from pathlib import Path

SEED = 20260926
N_SERIES = 20
MIN_TARGETS = 3
EXCLUDED_PATIENTS = {'LIDC-IDRI-0314', 'LIDC-IDRI-0325', 'LIDC-IDRI-0510'}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--expa', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    args = ap.parse_args(argv)
    series = json.loads((args.expa / 'targets.json').read_text())['series']
    eligible = sorted(s['ct_series'] for s in series if s['split'] == 'evaluation' and len(s['targets']) >= MIN_TARGETS
                      and s['patient'] not in EXCLUDED_PATIENTS)
    chosen = sorted(random.Random(SEED).sample(eligible, min(N_SERIES, len(eligible))))
    args.out.mkdir(parents=True, exist_ok=True)
    rec = dict(seed=SEED, eligible=len(eligible), chosen=chosen,
               patients=[next(s['patient'] for s in series if s['ct_series'] == c) for c in chosen])
    (args.out / 'series.json').write_text(json.dumps(rec, indent=1))
    print(len(eligible), 'eligible;', len(chosen), 'chosen')


if __name__ == '__main__':
    main()
