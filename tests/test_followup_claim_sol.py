"""Matched Sol adapter tests; all transport is scripted and unbilled."""
import asyncio
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from budgeted_science.agents import followup_claim_sol as s
from budgeted_science.agents.records import RunLog, digest, read_events
from budgeted_science.agents.spending import ApiBudget
from budgeted_science.paired_claim_audit.followup_core import build_catalog


class SolFollowup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = build_catalog()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self, ceiling='3.00'):
        slots, payloads, results = [], [], []
        for i, case in enumerate(self.catalog['cases']):
            env = s.luna.Audit(case['study'])
            env.dispatch('submit', {'verdicts': {f'C{j}': 'ABSTAIN' for j in range(1, 7)},
                                   'evidence_ids': [], 'explanation': 'Offline fixture'})
            result = env.evaluate()
            slot = f'{i+1:02d}-{case["case_id"]}'
            payloads.append({'study': deepcopy(case['study']),
                             'comparisons': {m: deepcopy(result) for m in s.luna.COMPARISONS}})
            slots.append({'slot': slot, 'case_id': case['case_id']})
            results.append({'slot': slot, 'case_id': case['case_id'], 'evaluation': result,
                            'path': str(self.root / 'prior-luna' / slot)})
        imported = {'tools_hash': digest(s.luna.tool_definitions()), 'results_hash': digest(results)}
        with patch.object(s, 'import_luna', return_value=(slots, payloads, results, imported)):
            return s.prepare(self.root, s.Config(api_ceiling_usd=ceiling))

    def test_only_model_and_dollar_cap_differ(self):
        for ceiling in ('1.00', '3.00'):
            config = s.Config(api_ceiling_usd=ceiling)
            expected = {**s.luna.Config().public(), 'model': 'gpt-5.6-sol', 'api_ceiling_usd': ceiling}
            self.assertEqual(config.public(), expected)
        for kw in ({'model': 'gpt-5.6-luna'}, {'api_ceiling_usd': '2.00'},
                   {'reasoning_effort': 'medium'}, {'scientific_budget': 24}, {'max_output_tokens': 8192}):
            with self.assertRaises(ValueError):
                s.Config(**kw)

    def test_prompt_equality_and_independent_initial_ledger(self):
        for case in self.catalog['cases']:
            log = RunLog(self.root, 'test')
            try:
                episode = s.Adapter.create_episode(s.Config(), s.luna.Instance(case['study']), log)
                before = s.luna.prompts(s.luna.Config(), episode)
                after = s.prompts(s.Config(), episode)
                after[1]['content'] = after[1]['content'].replace('a separate $3 API ceiling', 'a separate $1 API ceiling')
                self.assertEqual(before, after)
                self.assertEqual(episode.environment.status()['spent'], 0)
                self.assertEqual(s.Adapter.tool_definitions(s.Config()), s.luna.tool_definitions())
            finally:
                log.close()

    def test_reservations_use_sol_rates(self):
        ledger = ApiBudget('3.00', model='gpt-5.6-sol')
        self.assertEqual(ledger.reserve('one', 1000, 32768), Decimal('0.66036'))
        self.assertEqual(ledger.status()['ceiling_usd'], '3.00')

    def test_full_dry_run_and_exact_regeneration(self):
        prepared = self.prepare()
        with patch('budgeted_science.agents.runner.load_api_key', side_effect=AssertionError('offline key access')):
            path = asyncio.run(s.run(prepared, 'dry-run'))
        results = s.read(path / 'results.json')
        self.assertEqual(len(results), 6)
        self.assertTrue(all(r['termination_reason'] == 'submitted' for r in results))
        self.assertEqual(s.read(path / 'summary.json')['abstained'], 36)
        episode = Path(results[0]['path'])
        request = s.read(episode / 'api/generation-002-request.json')
        self.assertEqual(request['model'], 'gpt-5.6-sol')
        self.assertEqual(request['reasoning'], {'effort': 'high', 'summary': 'auto'})
        self.assertTrue(any(x.get('encrypted_content') for x in request['input']))
        before = {name: (episode / name).read_bytes() for name in ('report.md', 'transcript.md', 'evaluation.json', 'events.jsonl')}
        summary_before = (path / 'report.md').read_bytes()
        with patch.object(s.luna, 'Audit', side_effect=AssertionError('no tools in render')):
            s.regenerate(episode)
            s.render_campaign(path)
        self.assertTrue(all((episode / n).read_bytes() == b for n, b in before.items()))
        self.assertEqual((path / 'report.md').read_bytes(), summary_before)
        self.assertIn('# Sol/high:', summary_before.decode())
        self.assertIn('Matched saved Luna outcomes', summary_before.decode())

    def test_frozen_budget_and_original_snapshot_tampering_rejected(self):
        prepared = self.prepare()
        frozen, config, _ = s.load_prepared(prepared)
        self.assertEqual(frozen['api_maximum_total_usd'], '18.00')
        self.assertEqual(config.api_ceiling_usd, '3.00')
        # Test-only corruption of a disposable snapshot.
        (prepared / 'luna_results.json').write_text('[]', encoding='utf-8')
        with self.assertRaises(ValueError):
            s.load_prepared(prepared)

    def test_one_dollar_mode_and_duplicate_launch_guard(self):
        prepared = self.prepare('1.00')
        self.assertEqual(s.read(prepared / 'manifest.json')['api_maximum_total_usd'], '6.00')
        s.luna.mark_attempt(prepared / 'live-attempt.json', {'maximum_usd': '6.00'})
        with self.assertRaises(FileExistsError):
            asyncio.run(s.run(prepared, 'live', gateway_factory=s.luna.mixed.SolFake))

    def test_interrupted_usage_stops_campaign_without_retry(self):
        class Broken(s.luna.mixed.SolFake):
            async def stream(self, body, metadata):
                yield {'type': 'response.output_text.delta', 'delta': 'partial fixture'}
                raise ConnectionError('synthetic transport failure')
        prepared = self.prepare()
        path = asyncio.run(s.run(prepared, 'dry-run', gateway_factory=Broken))
        results = s.read(path / 'results.json')
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]['api_budget']['unsettled_requests'])
        self.assertEqual(results[0]['termination_reason'], 'request_or_runner_error')
        events, torn = read_events(results[0]['path'])
        self.assertFalse(torn)
        self.assertTrue(any(e['kind'] == 'api_stream_event' for e in events))


if __name__ == '__main__':
    unittest.main()
