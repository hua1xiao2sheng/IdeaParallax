import asyncio
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from idea_parallax.catalog import catalog, strategy
from idea_parallax.cli import main
from idea_parallax.config import validate_config
from idea_parallax.contracts import validate_brief, validate_batch, validate_review
from idea_parallax.engine import Engine
from idea_parallax.io_utils import ValidationError, parse_model_json, load_json
from idea_parallax.providers import Provider
from helpers import config, brief, batch

class Contracts(unittest.TestCase):
    def test_six_distinct_strategies(self):
        self.assertEqual(len(catalog()), 6)
        self.assertEqual(len({strategy(k)[1] for k in catalog()}), 6)
    def test_brief_preserves_user_scope(self):
        raw = brief()
        self.assertEqual(validate_brief(raw)['topic'], raw['topic'])
    def test_empty_topic_rejected(self):
        with self.assertRaises(ValidationError): validate_brief({'topic': ' '})
    def test_unknown_config_rejected(self):
        with self.assertRaises(ValidationError): validate_config({**config(), 'secret': 'never'})
    def test_duplicate_branch_rejected(self):
        c = config(); c['branches'][1]['id'] = c['branches'][0]['id']
        with self.assertRaises(ValidationError): validate_config(c)
    def test_path_traversal_branch_rejected(self):
        c = config(); c['branches'][0]['id'] = '../other'
        with self.assertRaises(ValidationError): validate_config(c)
    def test_missing_hypothesis_rejected(self):
        b = batch(); del b['candidates'][0]['hypothesis']
        with self.assertRaises(ValidationError): validate_batch(b, set(), 3)
    def test_fabricated_evidence_rejected(self):
        b = batch(); b['candidates'][0]['evidence_ids'] = ['imagined-paper']
        with self.assertRaises(ValidationError): validate_batch(b, set(), 3)
    def test_zero_candidates_allowed(self):
        self.assertEqual(validate_batch({'candidates': [], 'notes': 'No useful question'}, set(), 3)['candidates'], [])
    def test_quota_enforced(self):
        b = batch(); b['candidates'] *= 2
        with self.assertRaises(ValidationError): validate_batch(b, set(), 1)
    def test_fenced_json(self):
        self.assertEqual(parse_model_json('```json\n{"ok":true}\n```'), {'ok': True})
    def test_nan_rejected(self):
        with self.assertRaises(ValidationError): parse_model_json('{"x":NaN}')

class EndToEnd(unittest.IsolatedAsyncioTestCase):
    async def test_demo_complete_report(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)/'run'
            r = await Engine(brief(), config(), root).run()
            self.assertEqual(r['status'], 'completed')
            self.assertEqual(len(r['candidates']), 6)
            self.assertTrue(r['synthetic_demo'])
            self.assertEqual(r['budget']['calls_reserved'], 8)
            for f in ('report.html', 'report.md', 'report.json'):
                self.assertTrue((root/f).is_file())
    async def test_resume_does_not_repeat_success(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)/'run'
            first = await Engine(brief(), config(), root).run()
            second = await Engine(brief(), config(), root).run(resume=True)
            self.assertEqual(first['candidates'], second['candidates'])
            self.assertEqual(first['budget'], second['budget'])
    async def test_config_change_refuses_resume(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)/'run'
            await Engine(brief(), config(), root).run()
            c = config(); c['concurrency'] = 2
            with self.assertRaises(ValidationError): await Engine(brief(), c, root).run(resume=True)
    async def test_real_parallel_and_separate_payloads(self):
        active = 0; peak = 0; seen = []
        class Recorder(Provider):
            async def complete(self, kind, payload, schema, workspace):
                nonlocal active, peak
                active += 1; peak = max(peak, active)
                if kind == 'generate':
                    seen.append((str(workspace), copy.deepcopy(payload)))
                await asyncio.sleep(.02)
                try: return await super().complete(kind, payload, schema, workspace)
                finally: active -= 1
        with tempfile.TemporaryDirectory() as d:
            await Engine(brief(), config(), Path(d)/'run', provider_factory=Recorder).run()
        self.assertGreater(peak, 1); self.assertLessEqual(peak, 3)
        self.assertEqual(len({x[0] for x in seen}), 6)
        for _, payload in seen:
            self.assertNotIn('candidates', payload)
            self.assertNotIn('provenance', payload)
    async def test_review_blinds_project_sources(self):
        seen = []
        class Recorder(Provider):
            async def complete(self, kind, payload, schema, workspace):
                if kind == 'review': seen.append(copy.deepcopy(payload))
                return await super().complete(kind, payload, schema, workspace)
        with tempfile.TemporaryDirectory() as d:
            await Engine(brief(), config(), Path(d)/'run', provider_factory=Recorder).run()
        for packet in seen:
            for candidate in packet['candidates']:
                self.assertNotIn('provenance', candidate)
                self.assertNotIn('aris', candidate['id'])
    async def test_existing_output_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValidationError): await Engine(brief(), config(), Path(d)).run()
