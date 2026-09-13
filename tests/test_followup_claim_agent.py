"""Offline checks for the frozen six-study Luna adapter; never paid calls."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from budgeted_science.agents import followup_claim_audit as a
from budgeted_science.agents.records import RunLog, digest, read_events
from budgeted_science.paired_claim_audit.followup_core import build_catalog


class FollowupAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = build_catalog()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.log = RunLog(self.root, 'test')
        self.study = deepcopy(self.catalog['cases'][0]['study'])
        self.episode = a.Episode(a.Config(), a.Instance(self.study), self.log)

    def tearDown(self):
        self.log.close()
        self.temp.cleanup()

    def call(self, name, **args):
        return self.episode.execute(f'c-{self.episode.request_count}', name, json.dumps(args))

    def prepare(self):
        comparisons = {}
        for case in self.catalog['cases']:
            audit = a.Audit(case['study'])
            audit.dispatch('submit', {'verdicts': {f'C{i}': 'ABSTAIN' for i in range(1, 7)},
                                     'evidence_ids': [], 'explanation': 'CPU snapshot fixture'})
            comparisons[case['case_id']] = {m: audit.evaluate() for m in a.COMPARISONS}
        with patch.object(a, 'import_catalog', return_value=(deepcopy(self.catalog['cases']), comparisons,
                                                           {'catalog_hash': digest(self.catalog)})):
            return a.prepare(self.root)

    def test_initial_budget_free_evidence_and_prompt(self):
        self.assertEqual(self.episode.environment.status()['spent'], 0)
        self.assertEqual(self.episode.environment.status()['remaining'], 32)
        material = json.dumps(a.prompts(a.Config(), self.episode))
        self.assertIn('+1 for a correct verdict, -2 for a wrong verdict', material)
        self.assertIn('x(8)/x(6)-1', material)
        self.assertNotIn('forced', material)
        for key in ('target_parameters', 'pair_index', 'noise_seed', 'reference_value', 'criterion_margin', 'member'):
            self.assertNotIn(key, material)
        self.assertEqual(len(a.tool_definitions()), 7)

    def test_pair_has_identical_prompts(self):
        other = type('PublicEpisode', (), {'environment': a.Audit(self.catalog['cases'][1]['study'])})()
        self.assertEqual(a.prompts(a.Config(), self.episode), a.prompts(a.Config(), other))

    def test_frozen_config(self):
        for args in ({'model': 'gpt-5.6-sol'}, {'reasoning_effort': 'low'}, {'scientific_budget': 24},
                     {'api_ceiling_usd': '2'}, {'max_responses': 31}):
            with self.assertRaises(ValueError):
                a.Config(**args)

    def test_free_original_and_deduplicated_measurement(self):
        r = self.call('simulate_low', theta=self.study['public']['report_parameters'])
        self.assertEqual(r['charge'], 0)
        args = json.dumps({'variable': 'x', 'time': 4.0})
        one = self.episode.execute('same', 'measure_target', args)
        two = self.episode.execute('same', 'measure_target', args)
        self.assertEqual(one, two)
        self.assertEqual(self.episode.environment.status()['spent'], 12)
        three = self.call('measure_target', variable='x', time=4.)
        self.assertEqual(three['charge'], 0)
        self.assertEqual(three['value'], one['value'])

    def test_scoring_actual_submission_and_abstention(self):
        verdicts = {k: v['verdict'] for k, v in self.study['private']['truth'].items()}
        verdicts['C1'] = 'ABSTAIN'
        verdicts['C2'] = 'REJECT' if verdicts['C2'] == 'ACCEPT' else 'ACCEPT'
        r = self.call('submit', verdicts=verdicts, evidence_ids=['report'], explanation='Fixture')
        self.assertEqual(r['status'], 'submitted')
        score = self.episode.evaluate()
        self.assertEqual((score['correct'], score['wrong'], score['abstained'], score['utility']), (4, 1, 1, 2))
        self.assertEqual(score['submission']['verdicts'], verdicts)

    def test_invalid_actions_do_not_charge(self):
        self.assertEqual(self.call('measure_target', variable='x', time=1.1)['status'], 'invalid')
        self.assertEqual(self.call('reference')['status'], 'invalid')
        self.assertEqual(self.episode.environment.status()['spent'], 0)

    def test_budget_exhaustion_still_allows_submission(self):
        self.call('simulate_high', theta=self.study['public']['report_parameters'])
        self.call('measure_target', variable='x', time=4.)
        self.call('measure_target', variable='y', time=6.)
        self.assertEqual(self.episode.environment.status()['remaining'], 0)
        self.assertEqual(self.call('simulate_high', theta=[1., .08, 1.4])['status'], 'unaffordable')
        result = self.call('submit', verdicts={f'C{i}': 'ABSTAIN' for i in range(1, 7)},
                           evidence_ids=[], explanation='No credits')
        self.assertEqual(result['status'], 'submitted')

    def test_no_automatic_cpu_or_acquisition(self):
        with patch('budgeted_science.resource_planning.environment._solve_high', side_effect=AssertionError('unpaid')):
            # Constructor creates hidden target once, so inspect existing facade only.
            a.prompts(a.Config(), self.episode)
            self.call('evidence')
            self.call('compare_cached_candidates')
        self.assertEqual(self.episode.environment.status()['spent'], 0)

    def test_six_slot_rehearsal_and_offline_regeneration(self):
        prepared = self.prepare()
        with patch('budgeted_science.agents.runner.load_api_key', side_effect=AssertionError('offline key access')):
            path = asyncio.run(a.run(prepared, 'dry-run'))
        results = a.read(path / 'results.json')
        self.assertEqual(len(results), 6)
        self.assertTrue(all(r['termination_reason'] == 'submitted' for r in results))
        summary = a.read(path / 'summary.json')
        self.assertEqual(summary['abstained'], 36)
        self.assertEqual(summary['api_actual_offline_expenditure_usd'], 0)
        episode = Path(results[0]['path'])
        second = a.read(episode / 'api/generation-002-request.json')
        self.assertEqual(second['reasoning'], {'effort': 'high', 'summary': 'auto'})
        self.assertTrue(any(x.get('encrypted_content') == 'opaque-fixture' for x in second['input']))
        names = ('evaluation.json', 'report.md', 'transcript.md', 'events.jsonl')
        before = {n: (episode / n).read_bytes() for n in names}
        with patch.object(a, 'Audit', side_effect=AssertionError('no solver on render')):
            a.regenerate(episode)
            a.render_campaign(path)
        self.assertTrue(all((episode / n).read_bytes() == b for n, b in before.items()))

    def test_prepared_tampering_and_attempt_marker(self):
        prepared = self.prepare()
        a.load_prepared(prepared)
        marker = prepared / 'live-attempt.json'
        a.mark_attempt(marker, {'maximum_usd': '6.00'})
        with self.assertRaises(FileExistsError):
            a.mark_attempt(marker, {})
        with self.assertRaises(FileExistsError):
            asyncio.run(a.run(prepared, 'live', gateway_factory=a.legacy.Fake))
        manifest = a.read(prepared / 'manifest.json')
        slot = manifest['slots'][0]['slot']
        payload_path = prepared / 'slots' / slot / 'payload.json'
        payload = a.read(payload_path)
        payload['study']['public']['report'] += ' changed'
        payload_path.write_text(json.dumps(payload), encoding='utf-8')
        with self.assertRaises(ValueError):
            a.load_prepared(prepared)

    def test_interrupted_stream_preserved_and_halts_untouched_slots(self):
        class Broken(a.legacy.Fake):
            async def stream(self, body, metadata):
                yield {'type': 'response.output_text.delta', 'delta': 'partial fixture'}
                raise ConnectionError('fixture interrupted stream')
        prepared = self.prepare()
        path = asyncio.run(a.run(prepared, 'dry-run', gateway_factory=Broken))
        results = a.read(path / 'results.json')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['termination_reason'], 'request_or_runner_error')
        self.assertTrue(results[0]['api_budget']['unsettled_requests'])
        events, _ = read_events(results[0]['path'])
        self.assertTrue(any(e['kind'] == 'api_stream_event' for e in events))
        self.assertFalse((path / 'states' / (a.read(prepared / 'manifest.json')['slots'][1]['slot']+'-attempt.json')).exists())


if __name__ == '__main__':
    unittest.main()
