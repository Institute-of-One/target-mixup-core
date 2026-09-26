from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from synthetic_dicom import make_pair
from seg_point_match import match


class PointMatchTests(unittest.TestCase):
    """Synthetic cuboid: rows 1-2 (2 mm), columns 2-3 (3 mm), slices z = 30 and 34 mm.

    Origin (10, 20, 30); a pixel (row r, column c) on slice k is at (10 + 3c, 20 + 2r, 30 + 4k).
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.seg = make_pair(Path(cls.tmp.name))['seg']['files'][0]['path']

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_points(self, **points):
        rows = match([dict(id=k, lps_mm=v) for k, v in points.items()], [self.seg])
        return {r['point']: r for r in rows}

    def test_inside_outside_and_centroid(self):
        r = self.run_points(inside=[10 + 3 * 2, 20 + 2 * 1, 30], corner=[10 + 3 * 3, 20 + 2 * 2, 34],
                            beside=[10 + 3 * 5, 20 + 2 * 1, 30], above=[16, 22, 42])
        self.assertTrue(r['inside']['inside'])
        self.assertTrue(r['corner']['inside'])
        self.assertFalse(r['beside']['inside'])      # two columns (6 mm) away in plane
        self.assertFalse(r['above']['inside'])       # 8 mm above the top frame
        # Centroid of the 8 voxels: x = 10 + 3*2.5, y = 20 + 2*1.5, z = 32.
        self.assertEqual(r['inside']['centroid_lps_mm'], [17.5, 23.0, 32.0])
        self.assertAlmostEqual(r['inside']['centroid_distance_mm'], (1.5 ** 2 + 1 ** 2 + 2 ** 2) ** 0.5, places=2)


if __name__ == '__main__':
    unittest.main()
