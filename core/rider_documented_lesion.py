"""Where each RIDER SEG lies relative to the lesion the collection documents.

Section 3.1 says that Siemens SEGs which pass every structural check segment
another real nodule than the one in the collection's lesion notes. That is two
claims with two different kinds of evidence, and a reviewer asked for them to be
separated:

* that a SEG is not on the documented lesion is arithmetic. RIDER Lung CT ships
  the MSKCC notes, which give, per scan, "Location of a voxel around the lesion
  center (origin: top-left)" as a column, a row, an image number and that image's
  z position. This converts that voxel to patient coordinates with the CT's own
  geometry and measures, for every SEG on the series, the distance from the point
  to the SEG's nearest foreground voxel and to its centroid.
* what the SEG is on instead is a visual judgement, and stays one. It is recorded
  in target_reviews.jsonl and is not touched here.

The notes locate a voxel around the centre, not the centre, so a distance of a few
millimetres means the point is in the lesion the SEG covers. "Inside" below means
the point lies within half a voxel of a foreground voxel centre of that SEG.

    python rider_documented_lesion.py --census <census dir> --rider <rider dir>
"""
import argparse
import collections
import json
import sys
from pathlib import Path

import numpy as np
import pydicom

from seg_point_match import read_seg, segment_voxels

sys.stdout.reconfigure(encoding='utf-8')

SHEET, FIRST_ROW = 0, 4
COLUMNS = {'1': (2, 3, 4, 5), '2': (7, 8, 9, 10)}   # x pixel, y pixel, image number, z mm
Z_TOLERANCE_MM = 0.75       # a note's z must land on a slice of the series


def notes(path):
    """{RIDER id: {scan: (x_pixel, y_pixel, image_number, z_mm)}} from the MSKCC workbook."""
    import xlrd
    sheet = xlrd.open_workbook(str(path)).sheet_by_index(SHEET)
    out = {}
    for r in range(FIRST_ROW, sheet.nrows):
        rid = str(sheet.cell_value(r, 1)).strip()
        if not rid.startswith('RIDER-'):
            continue
        per = {}
        for scan, cols in COLUMNS.items():
            values = [str(sheet.cell_value(r, c)).strip() for c in cols]
            if all(values):
                per[scan] = tuple(float(v) for v in values)
        if per:
            out[rid] = per
    return out


def ct_geometry(folder):
    """Slice positions, orientation and spacing of one CT series, ordered by z."""
    slices = []
    for path in sorted(folder.iterdir()):
        try:
            ds = pydicom.dcmread(path, stop_before_pixels=True)
        except Exception:                               # noqa: BLE001 - non-DICOM extras
            continue
        if ds.get('Modality') != 'CT':
            continue
        slices.append(dict(position=np.asarray(ds.ImagePositionPatient, dtype=float),
                           instance=int(ds.get('InstanceNumber', 0)),
                           sop=str(ds.SOPInstanceUID),
                           thickness=float(ds.get('SliceThickness', 0) or 0)))
    if not slices:
        raise RuntimeError('no CT instances in %s' % folder)
    ds = pydicom.dcmread(sorted(folder.iterdir())[0], stop_before_pixels=True)
    return dict(slices=sorted(slices, key=lambda s: s['position'][2]),
                orientation=np.asarray(ds.ImageOrientationPatient, dtype=float),
                spacing=np.asarray(ds.PixelSpacing, dtype=float),
                rows=int(ds.Rows), columns=int(ds.Columns),
                thickness=float(ds.get('SliceThickness', 0) or 0),
                series=str(ds.SeriesInstanceUID))


def note_point(geometry, x_pixel, y_pixel, z_mm):
    """Patient coordinates of the noted voxel, on the slice whose z the note gives.

    Both readings of the stored y are returned. The workbook's header says the
    origin is top-left, but only y counted from the bottom row puts the noted voxel
    on the lesion the collection's own QIICR segmentation covers; which reading is
    used is decided per series by that agreement and recorded, and x and z, which
    no reading changes, are reported on their own.
    """
    hits = [s for s in geometry['slices'] if abs(s['position'][2] - z_mm) <= Z_TOLERANCE_MM]
    if len(hits) != 1:
        return None, len(hits)
    o, (dr, dc) = geometry['orientation'], geometry['spacing']
    rows = {'y_from_top': y_pixel, 'y_from_bottom': geometry['rows'] - 1 - y_pixel}
    points = {name: hits[0]['position'] + o[:3] * dc * x_pixel + o[3:] * dr * row
              for name, row in rows.items()}
    return dict(readings={k: [round(float(v), 1) for v in p] for k, p in points.items()},
                _points=points,
                slice_instance=hits[0]['instance'], slice_sop=hits[0]['sop'],
                z_mm=round(float(hits[0]['position'][2]), 2)), 1


def seg_rows(folder, manifest_segs, point, reading):
    """Every segment on the series, with its distance from the noted voxel.

    The separations in x alone and z alone are kept beside the full distance,
    because neither depends on how the stored y is read.
    """
    target = point['_points'][reading]
    out = []
    for sub in sorted(folder.iterdir()):
        if not sub.is_dir() or not sub.name.startswith('seg_'):
            continue
        files = sorted(p for p in sub.iterdir() if p.suffix.lower() == '.dcm')
        seg = read_seg(files[0])
        uid = str(seg.SeriesInstanceUID)
        voxels, spacing = segment_voxels(seg)
        for number, points in sorted(voxels.items()):
            centroid = points.mean(axis=0)
            nearest = float(np.linalg.norm(points - target, axis=1).min())
            half = float(max(spacing)) / 2
            out.append(dict(
                seg_series=uid, segment=number,
                stratum=manifest_segs.get(uid, {}).get('stratum', 'unknown'),
                label=str(seg.SegmentSequence[number - 1].get('SegmentLabel', '') or ''),
                voxels=int(len(points)),
                centroid_mm=[round(float(v), 1) for v in centroid],
                distance_to_note_centroid_mm=round(float(np.linalg.norm(centroid - target)), 1),
                distance_to_note_nearest_mm=round(nearest, 1),
                separation_x_mm=round(abs(float(centroid[0] - target[0])), 1),
                separation_z_mm=round(abs(float(centroid[2] - target[2])), 1),
                covers_noted_voxel=bool(nearest <= half)))
    return out


def choose_reading(folder, manifest_segs, point, anchor='QIICR'):
    """Which reading of the stored y agrees with the collection's own conversion.

    The QIICR segmentations are the collection's conversion of the documented
    target, so the reading that places the noted voxel on them is the one the
    workbook meant. Both distances are reported, so the choice is visible.
    """
    distances = {}
    for reading in point['_points']:
        rows = [r for r in seg_rows(folder, manifest_segs, point, reading)
                if anchor in r['stratum']]
        if not rows:
            raise RuntimeError('%s: no %s segmentation to anchor the reading' % (folder.name, anchor))
        distances[reading] = min(r['distance_to_note_centroid_mm'] for r in rows)
    best = min(distances, key=distances.get)
    return best, distances


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--census', required=True, type=Path)
    ap.add_argument('--rider', required=True, type=Path)
    args = ap.parse_args(argv)
    checks = args.census / 'target_checks'
    manifest = json.loads((checks / 'fetch_manifest.json').read_text(encoding='utf-8'))
    table = notes(args.rider / 'MSKCC-RepeatCT-Lesion-notes-for-RIDER.xls')

    cases, counts = [], collections.Counter()
    for entry in manifest:
        folder = checks / entry['folder']
        geometry = ct_geometry(folder / ('ct_%s' % entry['folder'].split('_')[1]))
        per_scan = table[entry['patient']]
        matched = {}
        for scan, (x, y, image, z) in sorted(per_scan.items()):
            point, hits = note_point(geometry, x, y, z)
            if point:
                matched[scan] = dict(point, noted_pixel=[x, y], noted_image_number=image)
            elif hits == 0:
                counts['note z matches no slice of this series'] += 1
            else:
                counts['note z matches several slices'] += 1
        if len(matched) != 1:
            raise RuntimeError('%s: %d of the two scans land on this series' % (folder.name, len(matched)))
        scan, point = matched.popitem()
        reading, distances = choose_reading(folder, entry['segs'], point)
        rows = seg_rows(folder, entry['segs'], point, reading)
        counts['reading ' + reading] += 1
        for row in rows:
            counts[('covers' if row['covers_noted_voxel'] else 'misses') + ' | ' + row['stratum']] += 1
        point = {k: v for k, v in point.items() if k != '_points'}
        cases.append(dict(folder=entry['folder'], patient=entry['patient'],
                          ct_series=geometry['series'], scan=scan,
                          slice_thickness_mm=geometry['thickness'],
                          pixel_spacing_mm=[round(float(v), 3) for v in geometry['spacing']],
                          ct_slices=len(geometry['slices']),
                          note=dict(point, reading=reading,
                                    lps_mm=point['readings'][reading],
                                    anchor_distance_mm=distances),
                          segments=rows))

    out = dict(source='MSKCC-RepeatCT-Lesion-notes-for-RIDER.xls, shipped with RIDER Lung CT',
               note_meaning='Location of a voxel around the lesion center (origin: top-left)',
               z_tolerance_mm=Z_TOLERANCE_MM, cases=cases, tally=dict(counts))
    (args.census / 'rider_targets.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    for case in cases:
        print('%s  scan %s  %.2f mm slices  note at %s (%s; the other reading is %.0f mm '
              'from the QIICR segmentation)'
              % (case['folder'], case['scan'], case['slice_thickness_mm'],
                 case['note']['lps_mm'], case['note']['reading'],
                 max(case['note']['anchor_distance_mm'].values())))
        for row in case['segments']:
            print('    %-28s %-18s nearest %6.1f  centroid %6.1f  |x| %6.1f  |z| %6.1f  %s'
                  % (row['stratum'].split(' | ')[1], row['label'][:18],
                     row['distance_to_note_nearest_mm'], row['distance_to_note_centroid_mm'],
                     row['separation_x_mm'], row['separation_z_mm'],
                     'covers the noted voxel' if row['covers_noted_voxel'] else ''))
    print('wrote rider_targets.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
