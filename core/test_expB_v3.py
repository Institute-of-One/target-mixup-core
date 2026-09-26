"""Hand-made cases for the v3 dual-reader gates and the slice-local position."""
import unittest

import numpy as np

from expB_readers_v3 import gate_dual, same_reason
from expB_regions_v3 import slice_fractions
from test_expB_readers_v2 import FRAC, TARGETS


def spec(**kw):
    base = dict(side=None, lobe=None, ordinal=None, size=None, regions=[], measurement=None, marker=False,
                unverifiable=False)
    base.update(kw)
    return base


class Dual(unittest.TestCase):
    def test_target_consensus(self):
        r, m = spec(side='right', regions=['posterior']), spec(side='right', lobe='RLL', ordinal='largest')
        self.assertEqual(gate_dual(TARGETS, r, m, FRAC, 2), 'authorize')          # both reach target 2
        self.assertEqual(gate_dual(TARGETS, r, m, FRAC, 2, reason=True), 'defer')  # for different reasons

    def test_disagreement_defers(self):
        r, m = spec(side='right', ordinal='largest'), spec(side='right', regions=['anterior', 'apex'])
        self.assertEqual(gate_dual(TARGETS, r, m, FRAC, 2), 'defer')               # rule 2, model 1
        self.assertEqual(gate_dual(TARGETS, r, m, FRAC, 1), 'defer')

    def test_missing_reader_defers(self):
        self.assertEqual(gate_dual(TARGETS, spec(side='left'), None, FRAC, 4), 'defer')

    def test_same_reason_ignores_region_order(self):
        self.assertTrue(same_reason(spec(regions=['lateral', 'posterior']), spec(regions=['posterior', 'lateral'])))


class Band(unittest.TestCase):
    def test_borderline_is_kept_clear_opposite_is_excluded(self):
        from expB_readers_v3 import excluded_by_region
        self.assertFalse(excluded_by_region(dict(ap=0.5, ml=0.44, cc=0.5), 'lateral'))   # B15-like, kept
        self.assertTrue(excluded_by_region(dict(ap=0.5, ml=0.30, cc=0.5), 'lateral'))
        self.assertFalse(excluded_by_region(dict(ap=0.5, ml=0.5, cc=0.45), 'apex'))
        self.assertTrue(excluded_by_region(dict(ap=0.5, ml=0.5, cc=0.49), 'apex'))

    def test_borderline_candidates_make_the_gate_defer(self):
        from expB_readers_v3 import resolve_v3
        targets = [dict(target=1, side='right', lobe='RLL', size_mm=8.0, centroid_lps_mm=[0, 0, 0]),
                   dict(target=2, side='right', lobe='RLL', size_mm=8.0, centroid_lps_mm=[0, 0, 10])]
        frac = {1: dict(ap=0.8, ml=0.42, cc=0.9), 2: dict(ap=0.7, ml=0.9, cc=0.8)}
        s = spec(side='right', lobe='RLL', regions=['lateral', 'posterior'])
        self.assertIsNone(resolve_v3(targets, s, frac))           # v2 would have picked 2 alone


class SecondReader(unittest.TestCase):
    def response(self, **picks):
        from expB_readers_v2 import QUESTIONS
        base = {k: ('unspecified' if 'unspecified' in q['criteria'] else 'none' if 'none' in q['criteria'] else 'no')
                for k, q in QUESTIONS.items()}
        base.update(picks)
        return dict(answers={k: dict(choice=v, confidence=0.95) for k, v in base.items()})

    def test_low_confidence_value_drops_only_that_field(self):
        from expB_readers_v3 import read_model_v3
        r = self.response(side='right', lobe='RLL', cc='base')
        r['answers']['cc']['confidence'] = 0.5                  # 'base' inferred from 下葉, unsure
        s = read_model_v3(r)
        self.assertEqual((s['lobe'], s['regions']), ('RLL', []))

    def test_nothing_confident_is_none(self):
        from expB_readers_v3 import read_model_v3
        r = self.response(side='right')
        r['answers']['side']['confidence'] = 0.4
        self.assertIsNone(read_model_v3(r))


class SliceLocal(unittest.TestCase):
    def test_lateral_within_the_slice(self):
        # affine diag(-1, -1, 1): LPS x = i, y = j, z = k. On slice k = 1 the lung lies 20..100 mm from the
        # midline; on slice k = 2 it reaches 150 mm. A nodule 90 mm from the midline on slice 1 is lateral on
        # its own slice (0.875) but would be medial against the whole-lung extent (0.54).
        aff = np.diag([-1.0, -1.0, 1.0, 1.0])
        mask = np.zeros((200, 200, 3), bool)
        mask[20:101, 50:150, 1] = True
        mask[20:151, 50:150, 2] = True
        f = slice_fractions(mask, aff, [90.0, 100.0, 1.0], midline_x=0.0)
        self.assertAlmostEqual(f['ml'], (90 - 20) / (100 - 20), places=3)
        self.assertAlmostEqual(f['ap'], (100 - 50) / (149 - 50), places=3)

    def test_empty_slice_is_none(self):
        mask = np.zeros((10, 10, 2), bool)
        self.assertIsNone(slice_fractions(mask, np.eye(4), [1.0, 1.0, 0.0], 0.0))


if __name__ == '__main__':
    unittest.main()
