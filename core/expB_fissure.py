"""Experiment B, descriptive (after set 3): distance from each requested target's centroid to the nearest
voxel of a different TotalSegmentator lobe on the same side, and the lobe the request text names.

    python expB_fissure.py --expb <expB dir> --expa <expA dir>
"""
import argparse
import json
from pathlib import Path

import nibabel as nib
import numpy as np

from expB_readers_v2 import read_rules_v2
from expB_score import load_jsonl

LOBES = {'RUL': 'lung_upper_lobe_right', 'RML': 'lung_middle_lobe_right', 'RLL': 'lung_lower_lobe_right',
         'LUL': 'lung_upper_lobe_left', 'LLL': 'lung_lower_lobe_left'}


def lobe_points(ts_dir, name, step=1):
    img = nib.load(str(ts_dir / f'{LOBES[name]}.nii.gz'))
    ijk = np.argwhere(np.asarray(img.dataobj)[::step, ::step, ::step] > 0) * step
    ras = (img.affine @ np.c_[ijk, np.ones(len(ijk))].T).T[:, :3]
    return np.c_[-ras[:, 0], -ras[:, 1], ras[:, 2]]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--expb', required=True, type=Path)
    ap.add_argument('--expa', required=True, type=Path)
    args = ap.parse_args(argv)
    table = {s['ct_series']: s for s in json.loads((args.expa / 'targets.json').read_text())['series']}
    lobes = json.loads((args.expb / 'lobes.json').read_text())
    cache, out = {}, []
    for q in load_jsonl(args.expb / 'requests_expert.jsonl'):
        uid = q['ct_series']
        t = next(t for t in table[uid]['targets'] if t['target'] == q['target'])
        ts_lobe = lobes[uid][str(q['target'])]['lobe']
        c = np.asarray(t['centroid_lps_mm'], float)
        side = 'R' if ts_lobe.startswith('R') else 'L'
        dist = {}
        for name in LOBES:
            if name[0] != side or name == ts_lobe:
                continue
            key = (uid, name)
            if key not in cache:
                cache[key] = lobe_points(args.expb / 'ts' / uid[-10:], name, step=2)
            pts = cache[key]
            dist[name] = round(float(np.min(np.linalg.norm(pts - c, axis=1))), 1) if len(pts) else None
        text_lobe = (read_rules_v2(q['text']) or {}).get('lobe')
        out.append(dict(set=q.get('set', 1), case=q['case'], ts_lobe=ts_lobe, text_lobe=text_lobe,
                        disagree=bool(text_lobe and text_lobe != ts_lobe), dist_to_other_lobes_mm=dist,
                        size_mm=round(t['size_mm'], 1), text=q['text']))
    (args.expb / 'fissure.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    named = [r for r in out if r['text_lobe']]
    print(f'requests naming a lobe: {len(named)}; disagree with TotalSegmentator: {sum(r["disagree"] for r in named)}')
    for r in named:
        near = min((v for v in r['dist_to_other_lobes_mm'].values() if v is not None), default=None)
        print(f"set{r['set']} {r['case']} text {r['text_lobe']} TS {r['ts_lobe']} {'DISAGREE' if r['disagree'] else 'agree   '} "
              f"nearest other lobe {near} mm  {r['dist_to_other_lobes_mm']}")


if __name__ == '__main__':
    main()
