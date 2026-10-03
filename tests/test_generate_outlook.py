import copy
import datetime as dt
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pipeline'))
import generate_outlook as generator

class GenerateOutlookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'reports').mkdir()
        (self.root / 'reports/EDITORIAL.md').write_text('EDITORIAL TEST RULE: center community impact.')
        self.calls = []
        self.source = 'https://www.un.org/en/'
        self.draft = {'summary': 'Test assessment', 'coverage': 'Test coverage', 'developments': [dict(region='Americas', title='Test topic', facts='Dated test evidence', response='Test response', effects='Test analysis', outlook='Test outlook', horizon='30 days', confidence='Moderate, test evidence', indicators='Test indicators', source_ids=['s1'])], 'sources': [dict(id='s1', name='Test source', url=self.source, published='2026-10-01')]}

    def tearDown(self): self.temp.cleanup()

    def api(self, key, payload):
        self.calls.append(payload)
        if len(self.calls) == 1:
            return {'status': 'completed', 'usage': {'input_tokens': 1000, 'output_tokens': 500}, 'output': [{'type': 'web_search_call', 'action': {'sources': [{'url': self.source}]}}, {'type': 'message', 'content': [{'type': 'output_text', 'text': 'Test sourced research'}]}]}
        return {'status': 'completed', 'usage': {'input_tokens': 2000, 'output_tokens': 1000}, 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(self.draft)}]}]}

    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-only-not-a-key'})
    def test_generation_researches_and_saves_draft(self):
        edition = generator.generate('request-test', self.root, self.api)
        self.assertEqual(edition['status'], 'draft')
        self.assertTrue((self.root / 'docs/data/outlook/generated/request-test.json').exists())
        self.assertFalse((self.root / 'docs/data/outlook/latest.json').exists())
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.calls[0]['tools'][0]['type'], 'web_search')
        self.assertEqual(self.calls[1]['text']['format']['type'], 'json_schema')
        self.assertIn('EDITORIAL TEST RULE', self.calls[0]['instructions'])
        self.assertAlmostEqual(edition['usage']['estimated_usd'], .031)
        with self.assertRaises(ValueError): generator.generate('request-test', self.root, self.api)

    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-only-not-a-key'})
    def test_unresearched_source_does_not_save(self):
        self.draft['sources'][0]['url'] = 'https://www.example.org/unresearched'
        with self.assertRaises(ValueError): generator.generate('request-test', self.root, self.api)
        self.assertFalse((self.root / 'docs/data/outlook/latest-generated.json').exists())

    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-only-not-a-key'})
    def test_incomplete_research_does_not_trigger_writing(self):
        def incomplete(key, payload):
            self.calls.append(payload)
            return {'status': 'incomplete', 'output': []}
        with self.assertRaises(ValueError): generator.generate('request-test', self.root, incomplete)
        self.assertEqual(len(self.calls), 1)

    def test_bad_id_and_missing_key_are_rejected(self):
        with self.assertRaises(ValueError): generator.generate('../escape', self.root, self.api)
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ValueError): generator.generate('request-test', self.root, self.api)
        self.assertFalse(self.calls)

    def test_previous_topics_are_supplied(self):
        folder = self.root / 'docs/data/outlook/generated';folder.mkdir(parents=True)
        (folder / 'prior.json').write_text(json.dumps(dict(self.draft, published_at='2026-10-01T10:00:00Z')))
        self.assertIn('Test topic', generator.history(self.root))

if __name__ == '__main__': unittest.main()
