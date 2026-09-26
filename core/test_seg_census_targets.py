import unittest
import numpy as np
from seg_census_targets import group_targets, SAME_TARGET_MM


def item(centroid, keys=()):
    return dict(centroid=np.asarray(centroid, dtype=float), keys=set(keys))


class GroupTargetTests(unittest.TestCase):
    def test_overlap_or_near_centroids_are_one_target(self):
        roots = group_targets([item([0, 0, 0], {(1, 1, 1)}), item([9, 0, 0], {(1, 1, 1)}),
                               item([0, SAME_TARGET_MM - 0.1, 0])])
        self.assertEqual(len(set(roots)), 1)

    def test_separate_lesions_are_separate_targets(self):
        roots = group_targets([item([0, 0, 0], {(0, 0, 0)}), item([0, SAME_TARGET_MM + 0.1, 0], {(5, 5, 5)}),
                               item([40, 0, 0])])
        self.assertEqual(len(set(roots)), 3)

    def test_grouping_is_transitive(self):
        # a~b by overlap, b~c by centroid: all three are one target even though a and c are far apart.
        roots = group_targets([item([0, 0, 0], {(1, 1, 1)}), item([10, 0, 0], {(1, 1, 1)}), item([12, 0, 0])])
        self.assertEqual(len(set(roots)), 1)


if __name__ == '__main__':
    unittest.main()
