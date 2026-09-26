"""Assemble per-CT review folders: the CT series plus selected cached SEGs.

Used for follow-up checks on census findings. For each CT series given, the full series is
fetched from TCIA (NBIA v1) and every audited SEG placed on that CT (by reference, or as the
single same-FoR series of its study) is copied from the census cache. Local use only.

    python seg_fetch_pairs.py --out <census dir> --dest <folder> CT_SERIES_UID [...]
"""
import argparse
import hashlib
import io
import json
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
    ap.add_argument('--dest', required=True, type=Path)
    ap.add_argument('ct', nargs='+')
    args = ap.parse_args(argv)
    last = {}
    for line in filter(None, (args.out / 'records.jsonl').read_text().splitlines()):
        r = json.loads(line)
        last[r['seg_series']] = r

    def on_ct(r, uid):
        if r.get('ct'):
            return r['ct'][0]['series_uid'] == uid
        same = [c['series_uid'] for c in r.get('study_ct_series', []) if c['frame_of_reference'] == r['seg_frame_of_reference']]
        return same == [uid]
    manifest = []
    for uid in args.ct:
        segs = sorted((r for r in last.values() if on_ct(r, uid)), key=lambda r: (r['stratum'], r['seg_series']))
        folder = args.dest / f"{segs[0]['patient']}_{uid[-10:]}"
        entry = dict(folder=folder.name, patient=segs[0]['patient'], ct_series=uid, segs={})
        for r in segs:
            blob = (args.out / 'cache' / 'seg' / f"{r['seg_series']}.zip").read_bytes()
            entry['segs'][r['seg_series']] = dict(stratum=r['stratum'], files=extract(blob, folder / f"seg_{r['seg_series'][-10:]}"))
        ct_dir = folder / f'ct_{uid[-10:]}'
        entry['ct'] = extract(get('getImage', SeriesInstanceUID=uid), ct_dir) if not ct_dir.exists() else \
            {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ct_dir.glob('*.dcm'))}
        print(folder.name, 'SEGs', len(segs), 'CT images', len(entry['ct']), flush=True)
        manifest.append(entry)
    args.dest.mkdir(parents=True, exist_ok=True)
    (args.dest / 'fetch_manifest.json').write_text(json.dumps(manifest, indent=1))


if __name__ == '__main__':
    main()
