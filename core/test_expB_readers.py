"""Tests on hand-made requests written before any expert request exists (not evaluation data)."""
import unittest
from expB_readers import read_rules, read_model, resolve, gate


def t(n, side, lobe, size, z):
    return dict(target=n, side=side, lobe=lobe, size_mm=size, centroid_lps_mm=[0, 0, z])


TARGETS = [t(1, 'right', 'RUL', 6.0, 50), t(2, 'right', 'RLL', 12.0, -40), t(3, 'right', 'RLL', 4.0, -60),
           t(4, 'left', 'LUL', 8.0, 30), t(5, 'left', 'LLL', 25.0, -20)]


class RuleReaderTests(unittest.TestCase):
    def test_lobe_from_side_and_level(self):
        s = read_rules('右肺下葉の結節の体積を測ってください')
        self.assertEqual((s['side'], s['lobe'], s['ordinal'], s['unverifiable']), ('right', 'RLL', None, False))

    def test_abbreviation_size_and_unverifiable(self):
        s = read_rules('RLL S10 subpleural nodule, 12 mm, please measure')
        self.assertEqual((s['lobe'], s['size'], s['unverifiable']), ('RLL', '10to20', True))

    def test_cm_and_ordinal(self):
        s = read_rules('左の一番大きい病変（約2.5cm）を計測')
        self.assertEqual((s['side'], s['ordinal'], s['size']), ('left', 'largest', '20to30'))

    def test_contradiction_and_empty(self):
        self.assertIsNone(read_rules('右と左の結節を測って'))
        self.assertIsNone(read_rules('この病変を測ってください'))


class GateTests(unittest.TestCase):
    def test_lobe_binding(self):
        self.assertIsNone(resolve(TARGETS, dict(side='right', lobe='RLL', ordinal=None, size=None, unverifiable=False)))
        self.assertEqual(resolve(TARGETS, dict(side='right', lobe='RLL', ordinal='largest', size=None,
                                               unverifiable=False)), 2)
        self.assertEqual(resolve(TARGETS, dict(side='left', lobe=None, ordinal=None, size='20to30',
                                               unverifiable=False)), 5)

    def test_size_tolerance_one_class(self):
        # 12 mm is class 10to20; a stated 5to10 is one class away and still admits it.
        self.assertIsNone(resolve(TARGETS, dict(side='right', lobe=None, ordinal=None, size='5to10', unverifiable=False)))

    def test_gate(self):
        spec = dict(side='right', lobe='RLL', ordinal='largest', size=None, unverifiable=False)
        self.assertEqual(gate(spec, TARGETS, 2), 'authorize')
        self.assertEqual(gate(spec, TARGETS, 3), 'defer')
        self.assertEqual(gate(None, TARGETS, 2), 'defer')


class ModelReaderTests(unittest.TestCase):
    def response(self, **picks):
        base = dict(side='unspecified', lobe='unspecified', ordinal='none', size='unspecified', unverifiable='no')
        base.update(picks)
        return dict(answers={k: dict(choice=v, confidence=0.99) for k, v in base.items()})

    def test_lobe_sets_side_and_unclear_is_unresolvable(self):
        s = read_model(self.response(lobe='LLL', ordinal='smallest'))
        self.assertEqual((s['side'], s['lobe'], s['ordinal']), ('left', 'LLL', 'smallest'))
        self.assertIsNone(read_model(self.response(lobe='unclear')))
        self.assertIsNone(read_model(self.response()))

    def test_low_confidence_is_unresolvable(self):
        r = self.response(side='right')
        r['answers']['side']['confidence'] = 0.5
        self.assertIsNone(read_model(r))


if __name__ == '__main__':
    unittest.main()
