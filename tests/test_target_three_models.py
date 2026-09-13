"""Offline matched-model extension tests; no paid requests or credentials."""
import asyncio
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from budgeted_science.agents import target_three_models as m
from budgeted_science.agents.records import RunLog, digest, read_events, json_text
from budgeted_science.agents.spending import ApiBudget
from budgeted_science.paired_claim_audit.followup_core import build_catalog
from budgeted_science.paired_claim_audit.target_three import build_catalog as three_catalog


class MatchedModels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = three_catalog(build_catalog())

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self, ceiling='3.00'):
        slots, payloads, prior = [], [], []
        for i, case in enumerate(self.catalog['cases']):
            study = case['study']
            cpu = m.luna.Audit(study)
            cpu.dispatch('submit', {'verdicts': {f'C{j}': 'ABSTAIN' for j in range(1, 4)},
                                   'evidence_ids': [], 'explanation': 'offline CPU fixture'})
            cpu_result = {**cpu.evaluate(), 'path': str(self.root / 'cpu')}
            env = m.luna.Audit(study)
            if i != 3:
                env.dispatch('submit', {'verdicts': {f'C{j}': 'ABSTAIN' for j in range(1, 4)},
                                       'evidence_ids': [], 'explanation': 'offline Luna fixture'})
            slot = f'{i+1:02d}-{case["case_id"]}'
            comparison = {m.luna.COMPARISON: cpu_result}
            payloads.append({'study': deepcopy(study), 'comparisons': deepcopy(comparison)})
            slots.append({'slot': slot, 'case_id': case['case_id']})
            prior.append({'slot': slot, 'case_id': case['case_id'], 'evaluation': env.evaluate(),
                          'path': str(self.root / 'old' / slot), 'fixed_policy': comparison,
                          'api_budget': {'committed_upper_usd': '0.00'}})
        imported = {'tools_hash': digest(m.luna.tool_definitions()), 'results_hash': digest(prior)}
        with patch.object(m, 'import_luna', return_value=(slots, payloads, prior, imported)):
            return m.prepare(self.root, ceiling)

    def test_config_exact_models_high_limits_and_prices(self):
        for model in m.MODELS:
            for cap in ('1.00', '3.00'):
                c = m.Config(model=model, api_ceiling_usd=cap)
                self.assertEqual(c.public(), {**m.luna.Config().public(), 'model': model, 'api_ceiling_usd': cap})
        for args in ({'model': 'gpt-5.6-luna'}, {'reasoning_effort': 'medium'},
                     {'api_ceiling_usd': '2'}, {'scientific_budget': 24}, {'max_output_tokens': 8192}):
            with self.assertRaises(ValueError):
                m.Config(**args)
        self.assertEqual(ApiBudget('3.00', model=m.MODELS[0]).reserve('a', 1000, 32768), Decimal('0.66036'))
        self.assertEqual(ApiBudget('3.00', model=m.MODELS[1]).reserve('a', 1000, 32768), Decimal('0.395716'))

    def test_exact_scientific_prompts_schemas_and_empty_initial_ledgers(self):
        study = self.catalog['cases'][0]['study']
        for model in m.MODELS:
            log = RunLog(self.root, 'fixture')
            try:
                config = m.Config(model=model)
                e = m.Adapter.create_episode(config, m.luna.Instance(study), log)
                expected = m.luna.prompts(m.luna.Config(), e)
                actual = m.prompts(config, e)
                actual[1]['content'] = actual[1]['content'].replace('a separate $3 API ceiling', 'a separate $1 API ceiling')
                self.assertEqual(actual, expected)
                self.assertEqual(m.Adapter.tool_definitions(config), m.luna.tool_definitions())
                self.assertEqual(e.environment.status()['spent'], 0)
            finally:
                log.close()

    def test_twelve_slots_matched_cases_and_alternating_order(self):
        prepared = self.prepare()
        manifest, configs, payloads = m.load_prepared(prepared)
        self.assertEqual(manifest['api_maximum_total_usd'], '36.00')
        self.assertEqual(manifest['api_maximum_per_model_usd'], '18.00')
        self.assertEqual(len(manifest['slots']), 12)
        for i in range(6):
            pair = manifest['slots'][2*i:2*i+2]
            self.assertEqual([s['model'] for s in pair], list(m.MODELS if i%2==0 else reversed(m.MODELS)))
            self.assertEqual(pair[0]['case_id'], pair[1]['case_id'])
            self.assertEqual(payloads[2*i], payloads[2*i+1])
        prior = m.read(prepared / 'luna_results.json')
        self.assertFalse(prior[3]['evaluation']['completed'])

    def test_full_rehearsal_history_and_offline_regeneration(self):
        prepared = self.prepare()
        with patch('budgeted_science.agents.runner.load_api_key', side_effect=AssertionError('offline key access')):
            path = asyncio.run(m.run(prepared, 'dry-run'))
        rows = m.read(path / 'results.json')
        self.assertEqual(len(rows), 12)
        summary = m.read(path / 'summary.json')
        self.assertEqual(summary['actual_offline_api_usd'], 0)
        for model in m.MODELS:
            self.assertEqual(summary[model]['completed'], 6)
            self.assertEqual(summary[model]['abstained'], 18)
        self.assertEqual(summary['gpt-5.6-luna']['incomplete_claims'], 3)
        for r in rows:
            q = Path(r['path'])
            body = m.read(q / 'api/generation-002-request.json')
            self.assertEqual(body['model'], r['model'])
            self.assertEqual(body['reasoning'], {'effort': 'high', 'summary': 'auto'})
            self.assertTrue(any(x.get('encrypted_content') == 'opaque-fixture' for x in body['input']))
        q = Path(rows[0]['path'])
        names = ['report.md', 'transcript.md', 'evaluation.json', 'events.jsonl']
        before = {n: (q/n).read_bytes() for n in names}
        report = (path / 'report.md').read_bytes()
        with patch.object(m.luna, 'Audit', side_effect=AssertionError('no tool on render')):
            m.luna.regenerate(q)
            m.render_campaign(path)
        self.assertEqual(before, {n: (q/n).read_bytes() for n in names})
        self.assertEqual(report, (path / 'report.md').read_bytes())

    def test_no_automatic_repeat_and_lower_cap_mode(self):
        prepared = self.prepare('1.00')
        self.assertEqual(m.read(prepared / 'manifest.json')['api_maximum_total_usd'], '12.00')
        m.luna.previous.mark_attempt(prepared / 'live-attempt.json', {})
        with self.assertRaises(FileExistsError):
            asyncio.run(m.run(prepared, 'live', gateway_factory=lambda c: m.luna.Fake()))

    def test_import_snapshot_tampering(self):
        prepared = self.prepare()
        (prepared / 'luna_results.json').write_text('[]', encoding='utf-8')
        with self.assertRaises(ValueError):
            m.load_prepared(prepared)

    def test_execution_order_is_frozen(self):
        prepared = self.prepare()
        file = prepared / 'manifest.json'
        manifest = m.read(file)
        manifest['slots'][0], manifest['slots'][1] = manifest['slots'][1], manifest['slots'][0]
        file.write_text(json_text(manifest), encoding='utf-8')
        with self.assertRaises(ValueError):
            m.load_prepared(prepared)

    def test_slot_model_mapping_and_payload_tampering(self):
        prepared = self.prepare()
        manifest = m.read(prepared / 'manifest.json')
        file = prepared / 'slots' / manifest['slots'][0]['slot'] / 'payload.json'
        payload = m.read(file)
        payload['study']['public']['report'] += ' changed'
        file.write_text(json_text(payload), encoding='utf-8')
        with self.assertRaises(ValueError):
            m.load_prepared(prepared)

    def test_expected_empty_submission_continues_untouched_slots(self):
        class Empty(m.luna.Fake):
            async def stream(self, body, metadata):
                async for e in super().stream(body, metadata):
                    if e['type'] == 'response.completed':
                        e['response']['output'] = [{'type':'message','role':'assistant','content':[{'type':'output_text','text':''}]}]
                    yield e
        prepared = self.prepare()
        count = 0
        def factory(config):
            nonlocal count
            count += 1
            return Empty() if count == 1 else m.luna.Fake()
        path = asyncio.run(m.run(prepared, 'dry-run', gateway_factory=factory))
        rows = m.read(path / 'results.json')
        self.assertEqual(len(rows), 12)
        self.assertEqual(rows[0]['termination_reason'], 'no_submission')
        self.assertTrue(all(r['termination_reason'] == 'submitted' for r in rows[1:]))

    def test_uncertain_stream_halts_and_keeps_reservation(self):
        class Broken(m.luna.Fake):
            async def stream(self, body, metadata):
                yield {'type':'response.output_text.delta','delta':'partial fixture'}
                raise ConnectionError('fixture stream failure')
        prepared = self.prepare()
        path = asyncio.run(m.run(prepared, 'dry-run', gateway_factory=lambda c: Broken()))
        rows = m.read(path / 'results.json')
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['api_budget']['unsettled_requests'])
        events, torn = read_events(rows[0]['path'])
        self.assertFalse(torn)
        self.assertTrue(any(e['kind']=='api_stream_event' for e in events))


if __name__ == '__main__':
    unittest.main()
