import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('publisher', ROOT / 'pipeline/publish_outlook.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)

class OutlookPublicationTests(unittest.TestCase):
    def setUp(self):
        self.edition = json.loads((ROOT / 'reports/example.json').read_text())
        self.edition.update(id='test-edition', status='published', published_at='2026-10-02T12:00:00Z', information_cutoff='2026-10-02T11:00:00Z')
        self.edition['sources'][0].update(url='https://www.un.org/en/', published='2026-10-01', accessed='2026-10-02')

    def test_invalid_editions_are_rejected(self):
        for changes in ({'status': 'draft'}, {'id': '../escape'}, {'id': 'latest'}, {'id': 'index'}, {'information_cutoff': '2026-10-02T13:00:00Z'}, {'information_cutoff': '2026-10-02T11:00:00'}, {'published_at': '2099-01-01T00:00:00Z'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                publisher.validate(dict(self.edition, **changes))
        for mutation in ('unknown-source', 'example-url', 'future-source'):
            edition = copy.deepcopy(self.edition)
            if mutation == 'unknown-source': edition['developments'][0]['source_ids'] = ['missing']
            if mutation == 'example-url': edition['sources'][0]['url'] = 'https://example.com'
            if mutation == 'future-source': edition['sources'][0]['published'] = '2099-01-01'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): publisher.validate(edition)

    def test_archive_preserves_editions_and_latest_order(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(publisher, 'ROOT', Path(directory)):
            path = Path(directory) / 'edition.json'
            path.write_text(json.dumps(self.edition))
            publisher.publish(path)
            folder = Path(directory) / 'docs/data/outlook'
            original = (folder / 'test-edition.json').read_bytes()
            with self.assertRaises(ValueError): publisher.publish(path)
            older = copy.deepcopy(self.edition)
            older.update(id='older-edition', published_at='2026-10-01T12:00:00Z', information_cutoff='2026-10-01T11:00:00Z')
            older['sources'][0]['accessed'] = '2026-10-01'
            path.write_text(json.dumps(older))
            publisher.publish(path)
            self.assertEqual(json.loads((folder / 'latest.json').read_text())['id'], 'test-edition')
            self.assertEqual([e['id'] for e in json.loads((folder / 'index.json').read_text())['editions']], ['test-edition', 'older-edition'])
            self.assertEqual((folder / 'test-edition.json').read_bytes(), original)

if __name__ == '__main__': unittest.main()
