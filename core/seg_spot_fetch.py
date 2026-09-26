"""Download the frozen spot-check pairs (SEG + source CT series) for visual review.

Reads spot_checks.json and records.jsonl from a seg_census.py output directory and
writes one folder per check under <out>/spot_checks/. For a SEG without source
references, every CT series in its study with the same FrameOfReferenceUID is fetched.
Downloaded files are local only and must not be redistributed.

    python seg_spot_fetch.py --out <census dir>
"""
import argparse
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

from seg_census import get


def extract(blob, folder):
    folder.mkdir(parents=True, exist_ok=True)
    digests = {}
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for name in z.namelist():
            if name.lower().endswith('.dcm'):
                raw = z.read(name)
                (folder / Path(name).name).write_bytes(raw)
                digests[Path(name).name] = hashlib.sha256(raw).hexdigest()
    return digests


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True, type=Path)
    args = ap.parse_args(argv)
    checks = json.loads((args.out / 'spot_checks.json').read_text())['checks']
    records = {}
    for line in filter(None, (args.out / 'records.jsonl').read_text().splitlines()):
        r = json.loads(line)
        records[r['seg_series']] = r
    manifest = []
    for n, check in enumerate(checks, 1):
        rec = records[check['seg_series']]
        slug = re.sub(r'[^A-Za-z0-9]+', '-', check['stratum']).strip('-')
        folder = args.out / 'spot_checks' / f'{n:02d}_{slug}'
        seg_blob = (args.out / 'cache' / 'seg' / f"{check['seg_series']}.zip").read_bytes()
        entry = dict(check, folder=folder.name, status=rec['status'], seg=extract(seg_blob, folder / 'seg'))
        if rec.get('ct'):
            ct_uids = [c['series_uid'] for c in rec['ct']]
            entry['ct_source'] = 'referenced'
        else:
            ct_uids = [c['series_uid'] for c in rec.get('study_ct_series', [])
                       if c['frame_of_reference'] == rec['seg_frame_of_reference']]
            entry['ct_source'] = f'same study and FrameOfReferenceUID ({len(ct_uids)} candidate series)'
        entry['ct'] = {}
        for uid in ct_uids:
            target = folder / f'ct_{uid[-12:]}'
            if not target.exists():
                entry['ct'][uid] = extract(get('getImage', SeriesInstanceUID=uid), target)
            else:
                entry['ct'][uid] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(target.glob('*.dcm'))}
        print(f"{folder.name}: {rec['status']}, CT series {len(ct_uids)}, "
              f"{sum(len(v) for v in entry['ct'].values())} images", flush=True)
        manifest.append(entry)
    (args.out / 'spot_checks' / 'fetch_manifest.json').write_text(json.dumps(manifest, indent=1))


if __name__ == '__main__':
    main()
