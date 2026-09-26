"""The release metadata agree with each other (runbook: the Zenodo version cannot be corrected after issue).

Skipped when run outside the released repository layout.
"""
import json
import re
import unittest
from pathlib import Path

from version import __version__

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless((ROOT / '.zenodo.json').exists(), 'not in the released repository layout')
class ReleaseMetadata(unittest.TestCase):
    def test_versions_agree(self):
        zen = json.loads((ROOT / '.zenodo.json').read_text(encoding='utf-8'))
        cff = re.search(r'^version:\s*(\S+)', (ROOT / 'CITATION.cff').read_text(encoding='utf-8'), re.M).group(1)
        pyp = re.search(r'^version = "([^"]+)"', (ROOT / 'pyproject.toml').read_text(encoding='utf-8'), re.M).group(1)
        self.assertEqual({zen['version'], cff, pyp, __version__}, {__version__})

    def test_zenodo_has_no_top_level_doi(self):
        # A top-level "doi" makes Zenodo stop issuing version DOIs.
        self.assertNotIn('doi', json.loads((ROOT / '.zenodo.json').read_text(encoding='utf-8')))


if __name__ == '__main__':
    unittest.main()
