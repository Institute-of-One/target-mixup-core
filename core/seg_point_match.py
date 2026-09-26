"""Match patient-coordinate points to DICOM SEG segments.

For every segment frame, pixels are mapped to patient LPS (mm) with the SEG's own plane
position, orientation and pixel spacing. A point is reported as inside a segment when it
lies within half a slice step of a frame plane and within half a pixel of a foreground
pixel centre on that plane; the distance to the segment centroid is always reported.

    python seg_point_match.py --points points.json SEG [SEG ...]

points.json: [{"id": "...", "lps_mm": [x, y, z]}, ...]. SEG files may be .dcm or TCIA .zip.
"""
import argparse
import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pydicom


def read_seg(path):
    path = Path(path)
    if path.suffix.lower() == '.zip':
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.lower().endswith('.dcm'))
            return pydicom.dcmread(io.BytesIO(z.read(name)))
    return pydicom.dcmread(path)


def segment_voxels(seg):
    """{segment number: (N, 3) LPS centres of foreground pixels}, plus the in-plane spacing."""
    shared = seg.SharedFunctionalGroupsSequence[0]
    frames = seg.pixel_array.reshape(int(seg.NumberOfFrames), seg.Rows, seg.Columns)
    out, spacing = {}, None
    for frame, pixels in zip(seg.PerFrameFunctionalGroupsSequence, frames):
        def group(name):
            return (frame.get(name) or shared.get(name))[0]
        o = np.asarray(group('PlaneOrientationSequence').ImageOrientationPatient, dtype=float)
        spacing = np.asarray(group('PixelMeasuresSequence').PixelSpacing, dtype=float)
        origin = np.asarray(group('PlanePositionSequence').ImagePositionPatient, dtype=float)
        number = int(group('SegmentIdentificationSequence').ReferencedSegmentNumber)
        rows, cols = np.nonzero(pixels)
        if len(rows):
            pts = origin + np.outer(cols * spacing[1], o[:3]) + np.outer(rows * spacing[0], o[3:])
            out.setdefault(number, []).append(pts)
    return {k: np.concatenate(v) for k, v in out.items()}, spacing


def match(points, seg_paths):
    results = []
    for path in seg_paths:
        seg = read_seg(path)
        voxels, spacing = segment_voxels(seg)
        labels = {int(s.SegmentNumber): str(s.get('SegmentLabel', '')) for s in seg.SegmentSequence}
        for number, pts in voxels.items():
            z = np.unique(np.round(pts[:, 2], 3))
            step = float(np.median(np.diff(z))) if len(z) > 1 else float(seg.SharedFunctionalGroupsSequence[0]
                                                                         .PixelMeasuresSequence[0].get('SliceThickness', 1))
            centroid = pts.mean(axis=0)
            for p in points:
                q = np.asarray(p['lps_mm'], dtype=float)
                near_plane = np.abs(pts[:, 2] - q[2]) <= step / 2 + 1e-3
                inplane = np.linalg.norm(pts[near_plane, :2] - q[:2], axis=1) if near_plane.any() else np.array([np.inf])
                results.append(dict(point=p['id'], seg=str(path), series_description=str(seg.get('SeriesDescription', '')),
                                    segment=number, label=labels.get(number, ''),
                                    inside=bool(inplane.min() <= float(max(spacing)) / 2 * 1.5),
                                    nearest_inplane_mm=round(float(inplane.min()), 2) if np.isfinite(inplane.min()) else None,
                                    centroid_distance_mm=round(float(np.linalg.norm(centroid - q)), 2),
                                    centroid_lps_mm=[round(float(v), 2) for v in centroid],
                                    z_range_mm=[round(float(pts[:, 2].min()), 2), round(float(pts[:, 2].max()), 2)]))
    return results


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--points', required=True, type=Path)
    ap.add_argument('segs', nargs='+')
    args = ap.parse_args(argv)
    print(json.dumps(match(json.loads(args.points.read_text(encoding='utf-8')), args.segs), indent=1))


if __name__ == '__main__':
    main()
