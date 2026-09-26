"""Hand-made examples (not the expert requests) for the v2 readers and gate."""
import unittest
from expB_readers_v2 import read_rules_v2, read_model_v2, resolve_v2, QUESTIONS


def t(n, side, lobe, size, z):
    return dict(target=n, side=side, lobe=lobe, size_mm=size, centroid_lps_mm=[0, 0, z])


TARGETS = [t(1, 'right', 'RUL', 6.0, 50), t(2, 'right', 'RLL', 12.0, -40), t(3, 'right', 'RLL', 4.0, -60),
           t(4, 'left', 'LUL', 8.0, 30)]
FRAC = {1: dict(ap=0.2, ml=0.7, cc=0.1), 2: dict(ap=0.8, ml=0.3, cc=0.8), 3: dict(ap=0.3, ml=0.8, cc=0.9),
        4: dict(ap=0.5, ml=0.5, cc=0.4)}


class RulesV2(unittest.TestCase):
    def test_longest_diameter_is_not_a_rank(self):
        s = read_rules_v2('右肺の結節の最大径を計測してください')
        self.assertEqual((s['side'], s['ordinal'], s['measurement']), ('right', None, 'longest_diameter'))

    def test_regions_marker_and_paravertebral(self):
        s = read_rules_v2('右肺の椎体に隣接する、マーキングした結節の長径をお願いします')
        self.assertEqual((s['regions'], s['marker'], s['measurement']), (['medial', 'posterior'], True, 'longest_diameter'))
        self.assertEqual(read_rules_v2('左肺背外側の結節')['regions'], ['lateral', 'posterior'])
        self.assertEqual(read_rules_v2('右肺尖部の結節')['regions'], ['apex'])

    def test_contradiction(self):
        self.assertIsNone(read_rules_v2('右肺前方と背側の結節'))


class GateV2(unittest.TestCase):
    def spec(self, **kw):
        base = dict(side=None, lobe=None, ordinal=None, size=None, regions=[], measurement=None, marker=False,
                    unverifiable=False)
        base.update(kw)
        return base

    def test_region_binding(self):
        self.assertEqual(resolve_v2(TARGETS, self.spec(side='right', regions=['anterior', 'apex']), FRAC), 1)
        self.assertEqual(resolve_v2(TARGETS, self.spec(side='right', regions=['posterior']), FRAC), 2)
        self.assertIsNone(resolve_v2(TARGETS, self.spec(side='right', regions=['base']), FRAC))  # 2 and 3
        self.assertEqual(resolve_v2(TARGETS, self.spec(side='right', regions=['base'], ordinal='largest'), FRAC), 2)
        self.assertIsNone(resolve_v2(TARGETS, self.spec(side='left', regions=['apex']), FRAC))   # none there


class ModelV2(unittest.TestCase):
    def response(self, **picks):
        base = {k: ('unspecified' if 'unspecified' in q['criteria'] else 'none' if 'none' in q['criteria'] else 'no')
                for k, q in QUESTIONS.items()}
        base.update(picks)
        return dict(answers={k: dict(choice=v, confidence=0.95) for k, v in base.items()})

    def test_low_confidence_unspecified_keeps_other_fields(self):
        r = self.response(side='right', ap='posterior')
        r['answers']['lobe']['confidence'] = 0.3            # 'unspecified' with low confidence
        s = read_model_v2(r)
        self.assertEqual((s['side'], s['lobe'], s['regions']), ('right', None, ['posterior']))

    def test_low_confidence_specific_value_is_unresolvable(self):
        r = self.response(side='right', lobe='RLL')
        r['answers']['lobe']['confidence'] = 0.5
        self.assertIsNone(read_model_v2(r))

    def test_size_key_mapping(self):
        self.assertEqual(read_model_v2(self.response(side='left', size='s10to20'))['size'], '10to20')


if __name__ == '__main__':
    unittest.main()
