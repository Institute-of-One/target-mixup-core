"""Experiment A, step 1: target table for LIDC CT series with two or more annotated targets.

Definitions follow EXPERIMENT_A_DESIGN_v1 (frozen): targets are geometric groups of QIICR
segments; centroid = mean of annotation centroids; size = median over annotations of the longest
axial diameter; side from the body midline on one CT slice near the targets' median z. The slice
is chosen among source images referenced by the SEG frames, so only one image per series is fetched.

    python expA_targets.py --census <census dir> --out <expA dir>
"""
import argparse
import io
import json
import random
from pathlib import Path

import numpy as np
import pydicom

from seg_census import get
from seg_census_targets import group_targets, meaning
from seg_point_match import read_seg

EXCLUDED_PATIENTS = {'LIDC-IDRI-0325', 'LIDC-IDRI-0314', 'LIDC-IDRI-0510'}  # used in development
DEV_SERIES = 10
SEED = 20260925
BODY_HU = -300
BONE_HU = 200
SIDE_MARGIN_MM = 10.0  # v1.1: nearer the midline, side is indeterminate


def annotation(seg_path):
    """Per segment: voxel LPS points grouped by frame, plus frame -> source SOP."""
    seg = read_seg(seg_path)
    shared = seg.SharedFunctionalGroupsSequence[0]
    frames = seg.pixel_array.reshape(int(seg.NumberOfFrames), seg.Rows, seg.Columns)
    out = {}
    for frame, pixels in zip(seg.PerFrameFunctionalGroupsSequence, frames):
        def group(name):
            return (frame.get(name) or shared.get(name))[0]
        rows, cols = np.nonzero(pixels)
        if not len(rows):
            continue
        o = np.asarray(group('PlaneOrientationSequence').ImageOrientationPatient, dtype=float)
        sp = np.asarray(group('PixelMeasuresSequence').PixelSpacing, dtype=float)
        origin = np.asarray(group('PlanePositionSequence').ImagePositionPatient, dtype=float)
        pts = origin + np.outer(cols * sp[1], o[:3]) + np.outer(rows * sp[0], o[3:])
        number = int(group('SegmentIdentificationSequence').ReferencedSegmentNumber)
        src = [str(s.ReferencedSOPInstanceUID) for d in (frame.get('DerivationImageSequence') or [])
               for s in d.get('SourceImageSequence', [])]
        item = out.setdefault(number, dict(slices=[], sources=[]))
        item['slices'].append(pts)
        item['sources'].append((float(origin[2]), src[0] if len(src) == 1 else None))
    labels = {int(s.SegmentNumber): (str(s.get('SegmentLabel', '')), meaning(s, 'SegmentedPropertyTypeCodeSequence'))
              for s in seg.SegmentSequence}
    return seg, out, labels


def longest_axial_mm(slices):
    best = 0.0
    for pts in slices:
        if len(pts) > 1:
            d = pts[:, None, :2] - pts[None, :, :2]
            best = max(best, float(np.sqrt((d ** 2).sum(-1)).max()))
    return best


def midline_x(series_uid, sop):
    ds = pydicom.dcmread(io.BytesIO(get('getSingleImage', SeriesInstanceUID=series_uid, SOPInstanceUID=sop)))
    hu = ds.pixel_array.astype(float) * float(ds.get('RescaleSlope', 1)) + float(ds.get('RescaleIntercept', 0))
    body = hu > BODY_HU
    counts = body.sum(axis=0)
    cols = np.nonzero(counts >= 0.05 * counts.max())[0]
    o = np.asarray(ds.ImageOrientationPatient, dtype=float)
    sp = np.asarray(ds.PixelSpacing, dtype=float)
    origin = np.asarray(ds.ImagePositionPatient, dtype=float)
    mid_col = (cols.min() + cols.max()) / 2
    # Independent check: centroid column of bone (spine, sternum, ribs) on the same slice.
    bone_col = float(np.nonzero(hu > BONE_HU)[1].mean())
    to_x = lambda c: float((origin + o[:3] * sp[1] * c)[0])
    return to_x(mid_col), dict(sop=sop, z=float(origin[2]), body_cols=[int(cols.min()), int(cols.max())],
                               bone_centroid_x_mm=round(to_x(bone_col), 2))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--census', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    args = ap.parse_args(argv)
    last = {}
    for line in filter(None, (args.census / 'records.jsonl').read_text().splitlines()):
        r = json.loads(line)
        last[r['seg_series']] = r
    by_ct = {}
    for r in last.values():
        if r['stratum'] == 'LIDC-IDRI | QIICR' and r['status'] in ('match', 'mismatch') and r['ct']:
            by_ct.setdefault(r['ct'][0]['series_uid'], []).append(r)
    series = []
    for uid, recs in sorted(by_ct.items()):
        items = []
        for r in recs:
            seg, anns, labels = annotation(args.census / 'cache' / 'seg' / f"{r['seg_series']}.zip")
            for n, a in anns.items():
                pts = np.concatenate(a['slices'])
                items.append(dict(seg_series=r['seg_series'], segment=n, label=labels[n][0], type=labels[n][1],
                                  centroid=pts.mean(axis=0), keys=set(map(tuple, np.round(pts, 2))),
                                  size=longest_axial_mm(a['slices']), sources=a['sources']))
        roots = group_targets(items)
        groups = {}
        for it, root in zip(items, roots):
            groups.setdefault(root, []).append(it)
        if len(groups) < 2:
            continue
        targets = []
        for k, members in enumerate(sorted(groups.values(), key=lambda m: -np.mean([x['centroid'][2] for x in m]))):
            c = np.mean([m['centroid'] for m in members], axis=0)
            targets.append(dict(target=k + 1, centroid_lps_mm=[round(float(v), 2) for v in c],
                                size_mm=round(float(np.median([m['size'] for m in members])), 1),
                                annotations=[dict(seg_series=m['seg_series'], segment=m['segment'], label=m['label'],
                                                  type=m['type'], size_mm=round(m['size'], 1)) for m in members],
                                _sources=[s for m in members for s in m['sources'] if s[1]]))
        zmed = float(np.median([t['centroid_lps_mm'][2] for t in targets]))
        sources = [s for t in targets for s in t.pop('_sources')]
        sop = min(sources, key=lambda s: abs(s[0] - zmed))[1]
        mid, probe = midline_x(uid, sop)
        for t in targets:
            # LPS: +x toward the patient's left.
            # v1.1: side only when both midline estimates agree and both are >= SIDE_MARGIN_MM away.
            dx = [t['centroid_lps_mm'][0] - m for m in (mid, probe['bone_centroid_x_mm'])]
            same = all(v > 0 for v in dx) or all(v < 0 for v in dx)
            t['side'] = ('left' if dx[0] > 0 else 'right') if same and min(map(abs, dx)) >= SIDE_MARGIN_MM else 'midline'
            t['size_class'] = 'mass' if t['size_mm'] > 30 else 'nodule'
        series.append(dict(ct_series=uid, patient=recs[0]['patient'], midline_x_mm=round(mid, 2), midline_probe=probe,
                           targets=targets))
        print(recs[0]['patient'], len(targets), 'targets', flush=True)
    eligible = sorted(s['ct_series'] for s in series if s['patient'] not in EXCLUDED_PATIENTS)
    dev = set(random.Random(SEED).sample(eligible, DEV_SERIES))
    for s in series:
        s['split'] = 'excluded' if s['patient'] in EXCLUDED_PATIENTS else 'development' if s['ct_series'] in dev else 'evaluation'
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'targets.json').write_text(json.dumps(dict(seed=SEED, dev_series=DEV_SERIES,
                                                           excluded_patients=sorted(EXCLUDED_PATIENTS), series=series), indent=1))
    splits = {k: sum(s['split'] == k for s in series) for k in ('excluded', 'development', 'evaluation')}
    print(len(series), 'series', splits)


if __name__ == '__main__':
    main()
