"""The author's labels feed the v2 gate through author_to_v2; hand-made labels only."""
import unittest

from expB_readers_v2 import resolve_v2
from expB_score_v2 import author_to_v2
from test_expB_readers_v2 import FRAC, TARGETS


def label(**kw):
    base = dict(side=None, lobe=None, ordinal=None, size=None, ap=None, ml=None, cc=None, unverifiable=False)
    base.update(kw)
    return base


class AuthorToV2(unittest.TestCase):
    def test_regions_are_carried_and_bind(self):
        spec = author_to_v2(label(side='right', ap='posterior'))
        self.assertEqual(spec['regions'], ['posterior'])
        self.assertEqual(resolve_v2(TARGETS, spec, FRAC), 2)

    def test_three_axes(self):
        self.assertEqual(author_to_v2(label(side='left', ap='anterior', ml='lateral', cc='apex'))['regions'],
                         ['anterior', 'apex', 'lateral'])

    def test_nothing_identifying_is_none(self):
        self.assertIsNone(author_to_v2(label(unverifiable=True)))


if __name__ == '__main__':
    unittest.main()
