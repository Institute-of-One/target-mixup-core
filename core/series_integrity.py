"""Explainable header-level integrity checks for DICOM SEG objects in a folder.

Every SEG found under a folder is checked against the image series it references.
Each check reports what was compared, the evidence values, and whether a failure
blocks measurement. Passing every check establishes structural consistency only:
it does not establish that the segment is the target a request intended, nor that
its boundary is anatomically correct. Pixel data are not read.

    python series_integrity.py <folder>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pydicom

ATOL_MM = 1e-3
TARGET_NOTE = ('Structural checks cannot show that this segment is the target the request '
               'intended; that requires an independently supplied target binding.')


def scan(folder):
    """Header-only read of every DICOM file below folder, grouped by series UID."""
    series, skipped = {}, 0
    for path in sorted(p for p in Path(folder).rglob('*') if p.is_file()):
        try:
            ds = pydicom.dcmread(path, stop_before_pixels=True)
            uid = str(ds.SeriesInstanceUID)
        except Exception:
            skipped += 1
            continue
        series.setdefault(uid, []).append((path, ds))
    return series, skipped


def check(id_, label, passed, evidence, blocks=True):
    return dict(id=id_, label=label, passed=bool(passed), blocks_measurement=blocks, evidence=evidence)


def seg_sources(seg):
    header = {}
    for item in seg.get('ReferencedSeriesSequence', []):
        header.setdefault(str(item.SeriesInstanceUID), set()).update(
            str(i.ReferencedSOPInstanceUID) for i in item.get('ReferencedInstanceSequence', []))
    frames = []
    shared = seg.get('SharedFunctionalGroupsSequence', [None])[0]
    # Derivation may be per frame or, as in the 2014 QIN SEGs, one shared list of all sources.
    shared_sources = [str(s.ReferencedSOPInstanceUID)
                      for d in (shared.get('DerivationImageSequence', []) if shared is not None else [])
                      for s in d.get('SourceImageSequence', [])]
    for frame in seg.get('PerFrameFunctionalGroupsSequence', []):
        pos = frame.get('PlanePositionSequence')
        sources = [str(s.ReferencedSOPInstanceUID) for d in frame.get('DerivationImageSequence', [])
                   for s in d.get('SourceImageSequence', [])] or shared_sources
        frames.append(dict(position=[float(v) for v in pos[0].ImagePositionPatient] if pos else None,
                           sources=sources))
    orient = None
    for group in (shared,) + tuple(seg.get('PerFrameFunctionalGroupsSequence', [])[:1]):
        if group is not None and 'PlaneOrientationSequence' in group:
            orient = [float(v) for v in group.PlaneOrientationSequence[0].ImageOrientationPatient]
            break
    spacing = None
    for group in (shared,) + tuple(seg.get('PerFrameFunctionalGroupsSequence', [])[:1]):
        if group is not None and 'PixelMeasuresSequence' in group:
            spacing = [float(v) for v in group.PixelMeasuresSequence[0].PixelSpacing]
            break
    return header, frames, orient, spacing


def lattice_offset(position, image, matrix):
    """(row, column) offset of a frame origin on an image's pixel lattice, or None.

    The frame must be in the image plane (within ATOL_MM), offset by whole pixels,
    and its matrix must fit inside the image.
    """
    orient = np.asarray(image.ImageOrientationPatient, dtype=float)
    spacing = np.asarray(image.PixelSpacing, dtype=float)  # (between rows, between columns)
    delta = np.asarray(position, dtype=float) - np.asarray(image.ImagePositionPatient, dtype=float)
    normal = np.cross(orient[:3], orient[3:])
    if abs(float(np.dot(delta, normal))) > ATOL_MM:
        return None
    col = float(np.dot(delta, orient[:3])) / spacing[1]
    row = float(np.dot(delta, orient[3:])) / spacing[0]
    r, c = round(row), round(col)
    if abs(row - r) * spacing[0] > ATOL_MM or abs(col - c) * spacing[1] > ATOL_MM:
        return None
    if r < 0 or c < 0 or r + matrix[0] > int(image.Rows) or c + matrix[1] > int(image.Columns):
        return None
    return (r, c)


def grid(images):
    """Regularity of an image series along its normal; None if not a single regular stack."""
    orient = np.asarray(images[0].ImageOrientationPatient, dtype=float)
    normal = np.cross(orient[:3], orient[3:])
    same = all(np.allclose(np.asarray(d.ImageOrientationPatient, dtype=float), orient, atol=1e-4)
               and np.allclose(np.asarray(d.PixelSpacing, dtype=float),
                               np.asarray(images[0].PixelSpacing, dtype=float), atol=1e-4)
               and (d.Rows, d.Columns) == (images[0].Rows, images[0].Columns) for d in images)
    z = np.sort([float(np.dot(np.asarray(d.ImagePositionPatient, dtype=float), normal)) for d in images])
    steps = np.diff(z)
    regular = same and len(z) > 1 and steps.min() > 0 and np.allclose(steps, np.median(steps), atol=1e-3)
    return dict(instances=len(images), same_orientation_spacing_size=bool(same), regular=bool(regular),
                slice_step_mm=float(np.median(steps)) if len(z) > 1 else None,
                orientation=[float(v) for v in orient],
                pixel_spacing=[float(v) for v in images[0].PixelSpacing])


def audit_seg(seg, series):
    header_refs, frames, seg_orient, seg_spacing = seg_sources(seg)
    frame_sops = {s for f in frames for s in f['sources']}
    refs = set(header_refs)
    if not refs:  # no ReferencedSeriesSequence: infer from the frames' source SOPs
        refs = {uid for uid, items in series.items()
                if any(str(ds.SOPInstanceUID) in frame_sops for _, ds in items)}
    seg_for = str(seg.get('FrameOfReferenceUID', ''))
    inferred = []
    if not refs and not frame_sops:
        # No source reference of any kind: the Frame of Reference UID is the only link left.
        inferred = sorted(uid for uid, items in series.items()
                          if str(items[0][1].get('Modality', '')) != 'SEG' and seg_for
                          and str(items[0][1].get('FrameOfReferenceUID', '')) == seg_for)
    checks = []
    present = sorted(u for u in refs if u in series)
    checks.append(check('referenced_series_present', 'Referenced image series is in the folder',
                        refs and len(present) == len(refs),
                        dict(referenced=sorted(refs), found=present, inferred_by_frame_of_reference=inferred)))
    placement = 'reference' if present else 'position_only' if len(inferred) == 1 else None
    display = present if present else inferred[:1] if placement else []
    images = [ds for uid in display for _, ds in series[uid]]
    by_sop = {str(d.SOPInstanceUID): d for d in images}
    wanted = set().union(*header_refs.values(), frame_sops) if header_refs else frame_sops
    found = wanted & set(by_sop)
    checks.append(check('sop_references_resolved', 'Every referenced source image exists',
                        wanted and found == wanted,
                        dict(referenced=len(wanted), found=len(found), missing=len(wanted - found))))
    if images:
        patients = sorted({str(d.PatientID) for d in images})
        studies = sorted({str(d.StudyInstanceUID) for d in images})
        checks.append(check('patient_study_match', 'Same patient and study as the images',
                            patients == [str(seg.PatientID)] and studies == [str(seg.StudyInstanceUID)],
                            dict(seg_patient=str(seg.PatientID), image_patients=patients,
                                 seg_study=str(seg.StudyInstanceUID), image_studies=studies)))
        image_for = sorted({str(d.get('FrameOfReferenceUID', '')) for d in images})
        checks.append(check('frame_of_reference_match', 'Same Frame of Reference UID as the images',
                            bool(seg_for) and image_for == [seg_for],
                            dict(seg=seg_for, images=image_for)))
        g = grid(images)
        checks.append(check('image_grid_regular', 'Images form one regular slice stack', g['regular'], g))
        orient_ok = seg_orient is not None and np.allclose(seg_orient, g['orientation'], atol=1e-4)
        spacing_ok = seg_spacing is not None and np.allclose(seg_spacing, g['pixel_spacing'], atol=1e-4)
        seg_matrix, image_matrix = [int(seg.Rows), int(seg.Columns)], [int(images[0].Rows), int(images[0].Columns)]
        # A SEG may legitimately use a cropped sub-grid; frame placement is checked below.
        checks.append(check('seg_plane_matches_images', 'SEG orientation and pixel spacing match the images',
                            orient_ok and spacing_ok,
                            dict(seg_orientation=seg_orient, seg_pixel_spacing=seg_spacing,
                                 seg_matrix=seg_matrix, image_matrix=image_matrix,
                                 cropped_subgrid=seg_matrix != image_matrix)))
        # A frame must lie on exactly one source image plane, at a whole-pixel in-plane
        # offset, with the SEG matrix inside that image.
        misplaced = unresolved = ambiguous = 0
        offsets = set()
        for f in frames:
            src = images if placement == 'position_only' else [by_sop[s] for s in f['sources'] if s in by_sop]
            if f['position'] is None or not src:
                unresolved += 1
                continue
            placed = [o for o in (lattice_offset(f['position'], d, seg_matrix) for d in src) if o is not None]
            misplaced += not placed
            ambiguous += len(placed) > 1
            offsets.update(placed)
        checks.append(check('frame_positions_match_sources', 'Each SEG frame lies on one source image plane',
                            frames and misplaced == unresolved == ambiguous == 0,
                            dict(frames=len(frames), misplaced=misplaced, unresolved=unresolved,
                                 ambiguous=ambiguous, tolerance_mm=ATOL_MM, placement=placement,
                                 pixel_offsets=[list(o) for o in sorted(offsets)][:5])))
    blocking = [c['id'] for c in checks if c['blocks_measurement'] and not c['passed']]
    def meaning(item, name):
        codes = item.get(name, [])
        return str(codes[0].get('CodeMeaning', '')) if codes else ''
    # Free-text label plus the coded property; only the codes are machine-comparable.
    segments = [dict(number=int(s.SegmentNumber), label=str(s.get('SegmentLabel', '')),
                     property_category=meaning(s, 'SegmentedPropertyCategoryCodeSequence'),
                     property_type=meaning(s, 'SegmentedPropertyTypeCodeSequence'),
                     anatomic_region=meaning(s, 'AnatomicRegionSequence'),
                     algorithm_type=str(s.get('SegmentAlgorithmType', '')),
                     algorithm_name=str(s.get('SegmentAlgorithmName', '')))
                for s in seg.get('SegmentSequence', [])]
    return dict(seg_series=str(seg.SeriesInstanceUID), seg_sop=str(seg.SOPInstanceUID),
                patient=str(seg.PatientID), description=str(seg.get('SeriesDescription', '')),
                software=str(seg.get('SoftwareVersions', '')), segments=segments,
                referenced_series=sorted(refs), display_series=display, placement=placement, checks=checks, failed_blocking=blocking,
                structurally_consistent=not blocking, measurement_permitted=not blocking,
                target_identity_established=False, target_note=TARGET_NOTE)


def audit_folder(folder):
    series, skipped = scan(folder)
    inventory = []
    for uid, items in sorted(series.items()):
        ds = items[0][1]
        inventory.append(dict(series_uid=uid, modality=str(ds.get('Modality', '')),
                              patient=str(ds.get('PatientID', '')),
                              description=str(ds.get('SeriesDescription', '')), instances=len(items),
                              frame_of_reference=str(ds.get('FrameOfReferenceUID', '')),
                              files=[str(p) for p, _ in items]))
    segs = [ds for items in series.values() for _, ds in items if str(ds.get('Modality', '')) == 'SEG']
    return dict(folder=str(Path(folder).resolve()), non_dicom_files=skipped, series=inventory,
                segmentations=[audit_seg(s, series) for s in segs])


if __name__ == '__main__':
    result = audit_folder(sys.argv[1])
    for s in result['series']:
        s.pop('files')
    print(json.dumps(result, indent=1))
