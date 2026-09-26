from pathlib import Path
import sys
import tempfile
import unittest
import pydicom
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from synthetic_dicom import make_pair
from series_integrity import audit_folder


def failed(folder):
    segs = audit_folder(folder)['segmentations']
    assert len(segs) == 1, segs
    return segs[0]


class SeriesIntegrityTests(unittest.TestCase):
    """Each injected defect must fail its own check and nothing else."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.pair = make_pair(self.dir)
        self.seg = Path(self.pair['seg']['files'][0]['path'])
        self.cts = [Path(f['path']) for f in self.pair['ct']['files']]

    def tearDown(self):
        self.tmp.cleanup()

    def edit(self, path, change):
        ds = pydicom.dcmread(path)
        change(ds)
        ds.save_as(path, enforce_file_format=True)

    def test_consistent_pair_passes_but_target_is_not_established(self):
        r = failed(self.dir)
        self.assertEqual(r['failed_blocking'], [])
        self.assertTrue(r['measurement_permitted'])
        self.assertFalse(r['target_identity_established'])
        self.assertEqual(len(r['checks']), 7)

    def test_frame_of_reference_mismatch(self):
        self.edit(self.seg, lambda d: setattr(d, 'FrameOfReferenceUID', '2.25.1'))
        self.assertEqual(failed(self.dir)['failed_blocking'], ['frame_of_reference_match'])

    def test_missing_source_image(self):
        self.cts[1].unlink()
        r = failed(self.dir)
        self.assertIn('sop_references_resolved', r['failed_blocking'])
        self.assertNotIn('frame_of_reference_match', r['failed_blocking'])
        evidence = next(c for c in r['checks'] if c['id'] == 'sop_references_resolved')['evidence']
        self.assertEqual(evidence['missing'], 1)

    def test_shifted_image_plane(self):
        self.edit(self.cts[2], lambda d: setattr(d, 'ImagePositionPatient', [10, 20, 30 + 4 * 2 + 1.5]))
        self.assertEqual(failed(self.dir)['failed_blocking'],
                         ['image_grid_regular', 'frame_positions_match_sources'])

    def test_other_patient(self):
        self.edit(self.seg, lambda d: setattr(d, 'PatientID', 'SOMEONE-ELSE'))
        self.assertEqual(failed(self.dir)['failed_blocking'], ['patient_study_match'])

    def test_other_pixel_spacing(self):
        def change(d):
            d.SharedFunctionalGroupsSequence[0].PixelMeasuresSequence[0].PixelSpacing = [2, 2]
        self.edit(self.seg, change)
        self.assertEqual(failed(self.dir)['failed_blocking'], ['seg_plane_matches_images'])

    def shift_frames(self, dx, rows=None):
        def change(d):
            for frame in d.PerFrameFunctionalGroupsSequence:
                p = frame.PlanePositionSequence[0]
                p.ImagePositionPatient = [float(p.ImagePositionPatient[0]) + dx] + list(p.ImagePositionPatient[1:])
            if rows:
                d.Rows = d.Columns = rows
        self.edit(self.seg, change)

    def test_cropped_subgrid_on_the_pixel_lattice_passes(self):
        self.shift_frames(3.0, rows=4)  # one column (3 mm) right, 4x4 matrix inside 8x8
        r = failed(self.dir)
        self.assertEqual(r['failed_blocking'], [])
        frame = next(c for c in r['checks'] if c['id'] == 'frame_positions_match_sources')['evidence']
        self.assertEqual(frame['pixel_offsets'], [[0, 1]])

    def test_half_pixel_shift(self):
        self.shift_frames(1.5)
        self.assertEqual(failed(self.dir)['failed_blocking'], ['frame_positions_match_sources'])

    def test_subgrid_outside_the_image(self):
        self.shift_frames(3.0)  # full 8x8 matrix shifted one column: overhangs the image
        self.assertEqual(failed(self.dir)['failed_blocking'], ['frame_positions_match_sources'])

    def test_referenced_series_absent(self):
        for p in self.cts:
            p.unlink()
        r = failed(self.dir)
        self.assertEqual(r['failed_blocking'], ['referenced_series_present', 'sop_references_resolved'])
        self.assertFalse(r['measurement_permitted'])


if __name__ == '__main__':
    unittest.main()
