"""Experiment B v3: slice-local position of each target inside its lung (motivated by set 2, B15).

A reader judges front/back and inner/outer within the axial image that shows the nodule, not across the
whole lung. For each target, on the axial slice of the TotalSegmentator lung (its side) nearest the
target centroid:
  ap: 0 = most anterior lung point on that slice, 1 = most posterior;
  ml: 0 = lung point nearest the body midline on that slice, 1 = farthest (most lateral).
cc (apex/base) stays whole-lung, as in v2: it is a position along the whole lung by definition.
If the side's lung has fewer than MIN_SLICE_POINTS on that slice, the whole-lung v2 value is used and
flagged.

    python expB_regions_v3.py --expb <expB dir> --expa <expA dir>
"""
import argparse
import json
from pathlib import Path

import nibabel as nib
import numpy as np

from expB_regions import SIDES

MIN_SLICE_POINTS = 50


def side_mask(ts_dir, names):
    imgs = [nib.load(str(ts_dir / f'{n}.nii.gz')) for n in names]
    if nib.aff2axcodes(imgs[0].affine)[2] not in ('S', 'I'):
        raise ValueError(f'{ts_dir}: third axis is not head-foot')
    mask = np.zeros(imgs[0].shape, bool)
    for img in imgs:
        mask |= np.asarray(img.dataobj) > 0
    return mask, imgs[0].affine


def slice_fractions(mask, affine, centroid_lps, midline_x):
    """ap and ml of the centroid within the lung on the nearest axial slice; None if too few points."""
    ras = np.array([-centroid_lps[0], -centroid_lps[1], centroid_lps[2], 1.0])
    k = int(round((np.linalg.inv(affine) @ ras)[2]))
    if not 0 <= k < mask.shape[2]:
        return None
    ij = np.argwhere(mask[:, :, k])
    if len(ij) < MIN_SLICE_POINTS:
        return None
    pts = (affine @ np.c_[ij, np.full(len(ij), k), np.ones(len(ij))].T).T
    x, y = -pts[:, 0], -pts[:, 1]                               # RAS -> LPS
    frac = lambda v, lo, hi: float(np.clip((v - lo) / (hi - lo), 0, 1)) if hi > lo else 0.5
    dist = np.abs(x - midline_x)
    return dict(ap=round(frac(centroid_lps[1], y.min(), y.max()), 3),
                ml=round(frac(abs(centroid_lps[0] - midline_x), dist.min(), dist.max()), 3), slice_index=k,
                slice_points=int(len(ij)))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--expb', required=True, type=Path)
    ap.add_argument('--expa', required=True, type=Path)
    args = ap.parse_args(argv)
    table = {s['ct_series']: s for s in json.loads((args.expa / 'targets.json').read_text())['series']}
    v2 = json.loads((args.expb / 'regions.json').read_text())
    out = {}
    for uid, per in v2.items():
        ts = args.expb / 'ts' / uid[-10:]
        masks = {side: side_mask(ts, names) for side, names in SIDES.items()}
        cent = {t['target']: t['centroid_lps_mm'] for t in table[uid]['targets']}
        res = {}
        for tid, r in per.items():
            mask, aff = masks[r['side']]
            local = slice_fractions(mask, aff, cent[int(tid)], table[uid]['midline_x_mm'])
            res[tid] = dict(side=r['side'], cc=r['cc'], **(dict(ap=local['ap'], ml=local['ml'], local=True,
                            slice_points=local['slice_points']) if local else dict(ap=r['ap'], ml=r['ml'], local=False)))
        out[uid] = res
        print(table[uid]['patient'], sum(v['local'] for v in res.values()), '/', len(res), 'slice-local', flush=True)
    (args.expb / 'regions_v3.json').write_text(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
