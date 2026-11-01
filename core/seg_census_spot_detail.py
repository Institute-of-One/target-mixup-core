"""The acquisition each visual judgement was made on, and how the case was chosen.

A reviewer asked how the spot-checked SEGs were selected and at what slice
thickness they were viewed. The selection rule is in spot_checks.json, frozen
before any outcome existed; the acquisition is in the fetched CT headers and had
never been reported. This puts both in one file, one row per check, together with
the structural status the audit recorded and the answers the author gave.

Nothing here is a judgement. The answers are copied from reviews.jsonl as saved.

    python seg_census_spot_detail.py --census <census dir>
"""
import argparse
import json
import sys
from pathlib import Path

import pydicom

sys.stdout.reconfigure(encoding='utf-8')


def latest_per_dataset(path):
    out = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.strip():
            record = json.loads(line)
            out[record['dataset']] = record
    return out


def acquisition(folder):
    """Slice thickness, in-plane spacing and slice count of the CT series viewed."""
    ct = next(p for p in sorted(folder.iterdir()) if p.is_dir() and p.name.startswith('ct_'))
    thickness, spacing, positions = set(), set(), []
    for path in sorted(ct.iterdir()):
        try:
            ds = pydicom.dcmread(path, stop_before_pixels=True)
        except Exception:                               # noqa: BLE001 - non-DICOM extras
            continue
        if ds.get('Modality') != 'CT':
            continue
        thickness.add(round(float(ds.get('SliceThickness', 0) or 0), 3))
        spacing.add(tuple(round(float(v), 3) for v in ds.PixelSpacing))
        positions.append(float(ds.ImagePositionPatient[2]))
    gaps = sorted({round(abs(b - a), 3) for a, b in zip(sorted(positions), sorted(positions)[1:])})
    return dict(slice_thickness_mm=sorted(thickness), pixel_spacing_mm=sorted(spacing),
                slices=len(positions), slice_gaps_mm=gaps[:3])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--census', required=True, type=Path)
    args = ap.parse_args(argv)
    spot = args.census / 'spot_checks'
    plan = json.loads((args.census / 'spot_checks.json').read_text(encoding='utf-8'))
    manifest = {e['folder']: e for e in json.loads(
        (spot / 'fetch_manifest.json').read_text(encoding='utf-8'))}
    v1 = latest_per_dataset(spot / 'reviews.jsonl')
    v2 = latest_per_dataset(spot / 'reviews_v2_anatomy.jsonl')

    rows = []
    for folder, entry in sorted(manifest.items()):
        rows.append(dict(check=folder.split('_')[0], stratum=entry['stratum'],
                         patient=entry['patient'], seg_series=entry['seg_series'],
                         status=entry['status'], ct_source=entry['ct_source'],
                         answers_round1=v1[folder]['answers'],
                         answers_round2=v2.get(folder, {}).get('answers'),
                         **acquisition(spot / folder)))
    out = dict(selection=plan['rule'], frozen_at=plan['frozen_at'],
               records_present_when_frozen=plan['records_present_when_frozen'], checks=rows)
    (args.census / 'spot_detail.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    print('selection: %s (frozen %s)' % (plan['rule'], plan['frozen_at']))
    for row in rows:
        print('%s %-44s %-22s thickness %s mm, %d slices, %s'
              % (row['check'], row['stratum'], row['patient'],
                 '/'.join('%g' % t for t in row['slice_thickness_mm']), row['slices'],
                 row['answers_round1']))
    print('wrote spot_detail.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
