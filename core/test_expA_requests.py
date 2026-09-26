import unittest
from expA_requests import resolve, render


def t(n, side, size, z):
    return dict(target=n, side=side, size_mm=size, centroid_lps_mm=[0, 0, z])


class ResolveTests(unittest.TestCase):
    def test_unique_by_side_and_ordinal(self):
        ts = [t(1, 'right', 10, 0), t(2, 'right', 5, 50), t(3, 'left', 20, 20)]
        self.assertEqual(resolve(ts, 'right', 'largest'), 1)
        self.assertEqual(resolve(ts, 'right', 'most_cranial'), 2)
        self.assertEqual(resolve(ts, None, 'largest'), 3)
        self.assertEqual(resolve(ts, 'left', 'smallest'), 3)

    def test_ties_are_ambiguous(self):
        ts = [t(1, 'right', 10.0, 0), t(2, 'right', 10.8, 30)]
        self.assertIsNone(resolve(ts, 'right', 'largest'))          # 0.8 mm <= 1 mm size tie
        self.assertEqual(resolve(ts, 'right', 'most_cranial'), 2)
        ts = [t(1, 'left', 5, 10.0), t(2, 'left', 9, 11.5)]
        self.assertIsNone(resolve(ts, 'left', 'most_cranial'))      # 1.5 mm <= 2 mm position tie

    def test_indeterminate_side_that_changes_the_answer_is_ambiguous(self):
        ts = [t(1, 'right', 10, 0), t(2, 'midline', 30, 0)]
        self.assertIsNone(resolve(ts, 'right', 'largest'))          # target 2 might be the right largest
        self.assertEqual(resolve(ts, 'right', 'smallest'), 1)       # either way target 1 is smallest
        self.assertIsNone(resolve([t(1, 'midline', 5, 0)], 'left', 'largest'))

    def test_no_candidate_is_ambiguous(self):
        self.assertIsNone(resolve([t(1, 'right', 5, 0)], 'left', 'largest'))

    def test_render(self):
        self.assertEqual(render('E5', None, 'largest'), '最も大きい結節を測定してください。')
        self.assertEqual(render('E4', 'left', 'most_cranial'), 'Left lung, uppermost lesion — volume please.')


if __name__ == '__main__':
    unittest.main()
