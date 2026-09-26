"""Experiment B v2: relative position of each target inside its lung, from TotalSegmentator lobes.

For each series the right lung (RUL+RML+RLL) and left lung (LUL+LLL) masks give, in patient LPS mm,
the lung extent. Each target (on the side of its lobe) gets three fractions in [0, 1]:
  ap: 0 = most anterior point of that lung, 1 = most posterior (LPS +y is posterior);
  ml: 0 = most medial (nearest the body midline), 1 = most lateral;
  cc: 0 = apex (cranial end), 1 = base (caudal end).

    python expB_regions.py --expb <expB dir> --expa <expA dir>
"""
import argparse
import json
from pathlib import Path

import nibabel as nib
import numpy as np

SIDES = {'right': ('lung_upper_lobe_right', 'lung_middle_lobe_right', 'lung_lower_lobe_right'),
         'left': ('lung_upper_lobe_left', 'lung_lower_lobe_left')}


def lung_points_lps(ts_dir, names, step=2):
    imgs = [nib.load(str(ts_dir / f'{n}.nii.gz')) for n in names]
    mask = np.zeros(imgs[0].shape, bool)
    for img in imgs:
        mask |= np.asarray(img.dataobj) > 0
    ijk = np.argwhere(mask[::step, ::step, ::step]) * step
    ras = (imgs[0].affine @ np.c_[ijk, np.ones(len(ijk))].T).T[:, :3]
    return np.c_[-ras[:, 0], -ras[:, 1], ras[:, 2]]  # RAS -> LPS


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--expb', required=True, type=Path)
    ap.add_argument('--expa', required=True, type=Path)
    args = ap.parse_args(argv)
    table = {s['ct_series']: s for s in json.loads((args.expa / 'targets.json').read_text())['series']}
    lobes = json.loads((args.expb / 'lobes.json').read_text())
    out = {}
    for uid, per in lobes.items():
        ts = args.expb / 'ts' / uid[-10:]
        mid = table[uid]['midline_x_mm']
        lungs = {side: lung_points_lps(ts, names) for side, names in SIDES.items()}
        res = {}
        for t in table[uid]['targets']:
            lobe = per[str(t['target'])]['lobe']
            side = 'right' if lobe.startswith('R') else 'left' if lobe.startswith('L') else t['side']
            if side not in lungs:
                continue
            pts, c = lungs[side], np.asarray(t['centroid_lps_mm'], float)
            dist = np.abs(pts[:, 0] - mid)
            frac = lambda v, lo, hi: float(np.clip((v - lo) / (hi - lo), 0, 1))
            res[t['target']] = dict(
                side=side,
                ap=round(frac(c[1], pts[:, 1].min(), pts[:, 1].max()), 3),
                ml=round(frac(abs(c[0] - mid), dist.min(), dist.max()), 3),
                cc=round(frac(-c[2], -pts[:, 2].max(), -pts[:, 2].min()), 3))
        out[uid] = res
        print(table[uid]['patient'], {k: (v['ap'], v['ml'], v['cc']) for k, v in list(res.items())[:3]}, flush=True)
    (args.expb / 'regions.json').write_text(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
