"""Experiment B: lung lobe of each target from TotalSegmentator (task total, fast mode, CPU).

For every selected series whose CT is downloaded, TotalSegmentator is run once (cached). A target's
lobe is the lobe containing its centroid; otherwise the lobe holding most of its annotation voxels;
otherwise 'outside'. LPS target coordinates are converted to the NIfTI voxel grid through the image
affine (RAS), so no resampling of the masks is involved.

    python expB_lobes.py --expb <expB dir> --expa <expA dir> --census <census dir> --ts <TotalSegmentator exe>
"""
import argparse
import json
import subprocess
from pathlib import Path

import nibabel as nib
import numpy as np

from seg_point_match import read_seg, segment_voxels

LOBES = {'RUL': 'lung_upper_lobe_right', 'RML': 'lung_middle_lobe_right', 'RLL': 'lung_lower_lobe_right',
         'LUL': 'lung_upper_lobe_left', 'LLL': 'lung_lower_lobe_left'}


def lobe_masks(ct_dir, out_dir, ts):
    out_dir.mkdir(parents=True, exist_ok=True)
    if not all((out_dir / f'{v}.nii.gz').exists() for v in LOBES.values()):
        subprocess.run([ts, '-i', str(ct_dir), '-o', str(out_dir), '--fast', '--roi_subset', *LOBES.values()],
                       check=True, capture_output=True)
    return {k: nib.load(str(out_dir / f'{v}.nii.gz')) for k, v in LOBES.items()}


def lobe_at(masks, lps_points):
    """Lobe label for LPS points (N,3): per point, which lobe mask contains it."""
    any_img = next(iter(masks.values()))
    inv = np.linalg.inv(any_img.affine)
    ras = np.c_[-lps_points[:, 0], -lps_points[:, 1], lps_points[:, 2], np.ones(len(lps_points))]
    ijk = np.rint((inv @ ras.T).T[:, :3]).astype(int)
    shape = any_img.shape
    ok = np.all((ijk >= 0) & (ijk < np.array(shape)), axis=1)
    labels = np.array(['outside'] * len(lps_points), dtype=object)
    for name, img in masks.items():
        data = np.asarray(img.dataobj)
        hit = np.zeros(len(lps_points), bool)
        hit[ok] = data[ijk[ok, 0], ijk[ok, 1], ijk[ok, 2]] > 0
        labels[hit] = name
    return labels


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--expb', required=True, type=Path)
    ap.add_argument('--expa', required=True, type=Path)
    ap.add_argument('--census', required=True, type=Path)
    ap.add_argument('--ts', required=True)
    args = ap.parse_args(argv)
    chosen = json.loads((args.expb / 'series.json').read_text())['chosen']
    table = {s['ct_series']: s for s in json.loads((args.expa / 'targets.json').read_text())['series']}
    out_path = args.expb / 'lobes.json'
    result = json.loads(out_path.read_text()) if out_path.exists() else {}
    for uid in chosen:
        if uid in result:
            continue
        folder = next((p for p in (args.expb / 'cases').glob(f'*_{uid[-10:]}') if p.is_dir()), None)
        ct = folder / f'ct_{uid[-10:]}' if folder else None
        if not ct or not ct.exists():
            continue
        masks = lobe_masks(ct, args.expb / 'ts' / uid[-10:], args.ts)
        per_target = {}
        for t in table[uid]['targets']:
            centre = lobe_at(masks, np.asarray([t['centroid_lps_mm']], dtype=float))[0]
            if centre != 'outside':
                per_target[t['target']] = dict(lobe=centre, by='centroid')
                continue
            pts = []
            for a in t['annotations']:
                vox, _ = segment_voxels(read_seg(args.census / 'cache' / 'seg' / f"{a['seg_series']}.zip"))
                pts.append(vox[a['segment']])
            labels = lobe_at(masks, np.concatenate(pts))
            inside = [l for l in labels if l != 'outside']
            per_target[t['target']] = dict(lobe=max(set(inside), key=inside.count) if inside else 'outside',
                                           by='majority' if inside else 'none')
        result[uid] = per_target
        out_path.write_text(json.dumps(result, indent=1))
        print(table[uid]['patient'], {k: v['lobe'] for k, v in per_target.items()}, flush=True)


if __name__ == '__main__':
    main()
