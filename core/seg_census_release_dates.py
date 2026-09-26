"""Compare TCIA release metadata of CT series whose SEG FrameOfReferenceUID matches or not.

Tests one explanation of FoR mismatch: the CT series was re-released (re-curated) after
the SEG was created, so the SEG kept the older FoR. Metadata only; no images downloaded.

    python seg_census_release_dates.py --out <census dir> [--stratum-prefix "LIDC-IDRI | QIN"]
"""
import argparse
import json
from pathlib import Path

from seg_census import get


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--stratum-prefix', default='LIDC-IDRI | QIN')
    args = ap.parse_args(argv)
    last = {}
    for line in filter(None, (args.out / 'records.jsonl').read_text().splitlines()):
        r = json.loads(line)
        last[r['seg_series']] = r
    rows = {}
    for r in last.values():
        if not r['stratum'].startswith(args.stratum_prefix) or r['status'] not in ('match', 'mismatch'):
            continue
        for ct in r['ct']:
            if (r['patient'], ct['series_uid']) in rows:
                continue
            seg_meta = json.loads(get('getSeriesMetaData', SeriesInstanceUID=r['seg_series']))[0]
            ct_meta = json.loads(get('getSeriesMetaData', SeriesInstanceUID=ct['series_uid']))[0]
            rows[(r['patient'], ct['series_uid'])] = dict(
                patient=r['patient'], status=r['status'],
                seg_series_date=seg_meta.get('Series Date'), seg_released=seg_meta.get('Date Released'),
                ct_released=ct_meta.get('Date Released'), ct_timestamp=ct_meta.get('TimeStamp'),
                ct_images=ct_meta.get('Number of Images'), ct_description=ct_meta.get('Series Description'))
    result = sorted(rows.values(), key=lambda x: (x['status'], x['patient']))
    (args.out / 'release_dates.json').write_text(json.dumps(result, indent=1))
    for x in result:
        print(f"{x['status']:9} {x['patient']}  CT released {x['ct_released']}  SEG made {x['seg_series_date']}")


if __name__ == '__main__':
    main()
