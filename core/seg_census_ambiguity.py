"""Can the source series of an unreferenced SEG be identified by plane positions?

For SEGs without source references whose study holds two or more CT series with the same
FrameOfReferenceUID, every candidate series is fetched and each SEG frame is tested with
series_integrity.lattice_offset (same plane, whole-pixel offset, inside the image).

    python seg_census_ambiguity.py --out <census dir>
"""
import argparse
import io
import json
import zipfile
from pathlib import Path

import pydicom

from seg_census import get
from series_integrity import lattice_offset


def headers_from_zip(blob):
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        return [pydicom.dcmread(io.BytesIO(z.read(n)), stop_before_pixels=True)
                for n in z.namelist() if n.lower().endswith('.dcm')]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True, type=Path)
    args = ap.parse_args(argv)
    last = {}
    for line in filter(None, (args.out / 'records.jsonl').read_text().splitlines()):
        r = json.loads(line)
        last[r['seg_series']] = r
    cache = args.out / 'cache' / 'ct_full'
    cache.mkdir(parents=True, exist_ok=True)
    series_headers, result = {}, []
    for r in sorted(last.values(), key=lambda r: (r['patient'], r['seg_series'])):
        if r.get('for_candidates', 0) < 2:
            continue
        candidates = [c['series_uid'] for c in r['study_ct_series'] if c['frame_of_reference'] == r['seg_frame_of_reference']]
        for uid in candidates:
            if uid not in series_headers:
                path = cache / f'{uid}.zip'
                if not path.exists():
                    path.write_bytes(get('getImage', SeriesInstanceUID=uid))
                series_headers[uid] = headers_from_zip(path.read_bytes())
        seg = headers_from_zip((args.out / 'cache' / 'seg' / f"{r['seg_series']}.zip").read_bytes())[0]
        matrix = (int(seg.Rows), int(seg.Columns))
        per_series = {}
        for uid in candidates:
            placed = 0
            for frame in seg.PerFrameFunctionalGroupsSequence:
                p = [float(v) for v in frame.PlanePositionSequence[0].ImagePositionPatient]
                hits = [o for d in series_headers[uid] for o in [lattice_offset(p, d, matrix)] if o is not None]
                placed += len(hits) == 1
            per_series[uid] = dict(frames=len(seg.PerFrameFunctionalGroupsSequence), placed=placed,
                                   instances=len(series_headers[uid]))
        complete = [u for u, v in per_series.items() if v['placed'] == v['frames']]
        result.append(dict(patient=r['patient'], seg_series=r['seg_series'], candidates=per_series,
                           fully_placeable=complete, identifiable=len(complete) == 1))
        print(r['patient'], r['seg_series'][-12:], {u[-8:]: f"{v['placed']}/{v['frames']}" for u, v in per_series.items()},
              'identifiable' if len(complete) == 1 else f'{len(complete)} series fit', flush=True)
    (args.out / 'ambiguity.json').write_text(json.dumps(result, indent=1))


if __name__ == '__main__':
    main()
