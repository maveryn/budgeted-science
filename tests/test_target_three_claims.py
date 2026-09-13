"""Offline scientific/interface/regression checks; never paid API calls."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from budgeted_science.agents import target_three_claims as a
from budgeted_science.agents.records import RunLog, digest, read_events
from budgeted_science.paired_claim_audit import target_three as science
from budgeted_science.paired_claim_audit import target_three_policy as policy


class TargetThree(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = a.read(a.previous.PREPARED / 'catalog.json')
        cls.catalog = science.build_catalog(cls.original)

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
        return self.episode.execute(f'c-{self.episode.request_count+1}', name, json.dumps(args))

    def test_catalog_only_three_target_claims_and_replay(self):
        self.assertEqual(science.build_catalog(self.original), self.catalog)
        self.assertEqual(len(self.catalog['cases']), 6)
        for new, old in zip(self.catalog['cases'], self.original['cases']):
            s = new['study']
            self.assertEqual(s['private']['target_parameters'], old['study']['private']['target_parameters'])
            self.assertEqual(s['private']['noise_seed'], old['study']['private']['noise_seed'])
            self.assertEqual({c['kind'] for c in s['public']['claims']},
                {'target_parameter_accuracy', 'target_integral', 'target_late_recovery'})
            self.assertTrue(all(c['scope'] == 'fixed_target' for c in s['public']['claims']))
            self.assertNotIn('candidate_fits', s['public'])
            self.assertNotIn('intervention_parameters', s['public'])

    def test_public_pair_equality_and_private_isolation(self):
        for i in range(0, 6, 2):
            left, right = [type('E', (), {'environment': a.Audit(c['study'])})()
                           for c in self.catalog['cases'][i:i+2]]
            self.assertEqual(a.prompts(a.Config(), left), a.prompts(a.Config(), right))
        material = json.dumps(a.prompts(a.Config(), self.episode))
        for key in ('target_parameters', 'pair_index', 'noise_seed', 'member', 'reference_value', 'criterion_margin'):
            self.assertNotIn(key, material)
        self.assertNotIn('six claims', material)
        self.assertEqual(self.episode.environment.status()['spent'], 0)

    def test_author_fit_depends_only_on_public_observations(self):
        evidence = self.episode.environment.evidence()
        first = science.fit_report(evidence)
        evidence['unrelated_private_fixture'] = {'target_parameters': [9, 9, 9]}
        second = science.fit_report(evidence)
        self.assertEqual(first[0], second[0])
        self.assertEqual(first[2], second[2])
        records = first[2]['evaluations']
        self.assertTrue(records)
        self.assertTrue(all(r['time'] == 1 and r['theta'][1] == .08 for r in records))

    def test_report_original_really_computed(self):
        for case in self.catalog['cases']:
            public = case['study']['public']
            actual = science.core.old._solve_low(public['report_parameters'], science.core.old.harder_config(32))
            np.testing.assert_array_equal(actual.sample(public['original']['times']), public['original']['values'])

    def test_truth_and_threshold_boundaries(self):
        for case in self.catalog['cases']:
            s = case['study']
            for c in s['public']['claims']:
                q = (science.parameter_error(c['reported_parameters'], s['private']['target_parameters'])
                     if c['kind'] == 'target_parameter_accuracy' else
                     science.followup_core.target_quantity(c['kind'], s['private']['references']['target']))
                self.assertEqual(science.classify(c, q)['verdict'], s['private']['truth'][c['id']]['verdict'])
        c = {'kind': 'target_parameter_accuracy', 'threshold': .05}
        self.assertEqual(science.classify(c, .05)['verdict'], 'ACCEPT')
        self.assertEqual(science.classify(c, .05001)['verdict'], 'REJECT')
        with self.assertRaises(ValueError):
            science.parameter_error([1, 2, 3], [0, 1, 2])

    def test_exact_three_schema_and_scoring(self):
        schema = a.tool_definitions()[-1]['parameters']['properties']['verdicts']
        self.assertEqual(schema['required'], ['C1', 'C2', 'C3'])
        verdicts = {k: v['verdict'] for k, v in self.study['private']['truth'].items()}
        verdicts['C1'] = 'ABSTAIN'
        verdicts['C2'] = 'REJECT' if verdicts['C2'] == 'ACCEPT' else 'ACCEPT'
        result = self.call('submit', verdicts=verdicts, evidence_ids=['report'], explanation='fixture')
        self.assertEqual(result['status'], 'submitted')
        r = self.episode.evaluate()
        self.assertEqual((r['correct'], r['wrong'], r['abstained'], r['utility']), (1, 1, 1, -1))

    def test_dedup_free_original_and_budget(self):
        self.assertEqual(self.call('simulate_low', theta=self.study['public']['report_parameters'])['charge'], 0)
        args = json.dumps({'variable': 'x', 'time': 4.})
        first = self.episode.execute('same', 'measure_target', args)
        self.assertEqual(first, self.episode.execute('same', 'measure_target', args))
        self.assertEqual(self.call('measure_target', variable='x', time=4.)['charge'], 0)
        self.call('measure_target', variable='y', time=6.)
        self.call('simulate_high', theta=self.study['public']['report_parameters'])
        self.assertEqual(self.episode.environment.status()['spent'], 32)
        self.assertEqual(self.call('simulate_low', theta=[1., .1, 1.5])['status'], 'unaffordable')
        self.assertEqual(self.call('submit', verdicts={f'C{i}': 'ABSTAIN' for i in range(1, 4)},
                                   evidence_ids=[], explanation='fixture')['status'], 'submitted')

    def test_invalid_no_charge_and_no_implicit_solver(self):
        self.assertEqual(self.call('measure_target', variable='x', time=1.1)['status'], 'invalid')
        self.assertEqual(self.call('simulate_low', theta=[float('nan'), .08, 1.])['status'], 'invalid')
        self.assertEqual(self.call('submit', verdicts={'C1': 'ACCEPT'}, evidence_ids=[], explanation='x')['status'], 'invalid')
        with patch('budgeted_science.resource_planning.environment._solve_high', side_effect=AssertionError('unpaid')):
            self.call('evidence')
            self.call('compare_cached_candidates')
            a.prompts(a.Config(), self.episode)
        self.assertEqual(self.episode.environment.status()['spent'], 0)

    def test_continuous_cpu_completes_and_has_no_two_fit_assumption(self):
        result = a.run_cpu(self.study, self.root)
        self.assertTrue(result['completed'])
        self.assertEqual(result['scientific_status']['spent'], 32)
        events, torn = read_events(result['path'])
        self.assertFalse(torn)
        self.assertTrue(any(e['kind'] == 'continuous_audit_fit' for e in events))
        self.assertNotIn('candidate_fits', Path(policy.__file__).read_text())
        before = (Path(result['path']) / 'transcript.md').read_bytes()
        a.regenerate(result['path'])
        self.assertEqual(before, (Path(result['path']) / 'transcript.md').read_bytes())

    def test_analysis_does_not_run_physical_solver(self):
        from budgeted_science.resource_planning.local_policy import LocalFit
        for theta in ([1, .08, 1.4], [.9, .08, 1.4], [1, .07, 1.4], [1, .08, 1.2]):
            self.call('simulate_low', theta=theta)
        tools = policy.Tools(lambda n, **k: self.call(n, **k), self.study['public'], self.log.event)
        evidence = tools.evidence()
        with patch('budgeted_science.resource_planning.environment._solve_high', side_effect=AssertionError('unpaid')), \
             patch('budgeted_science.resource_planning.environment._solve_low', side_effect=AssertionError('unpaid')):
            fit = LocalFit(evidence, tools.public_config)
            _, point = fit.proposals()[0]
            tools.submit((fit.lower + point * fit.width).tolist())

    def prepare_fixture(self):
        def cpu(study, root):
            env = a.Audit(study)
            env.dispatch('submit', {'verdicts': {f'C{i}': 'ABSTAIN' for i in range(1, 4)},
                                   'evidence_ids': [], 'explanation': 'fixture'})
            return {**env.evaluate(), 'path': str(self.root)}
        with patch.object(a, 'run_cpu', side_effect=cpu):
            return a.prepare(self.root, source_catalog=self.original)

    def test_offline_rehearsal_history_and_regeneration(self):
        prepared = self.prepare_fixture()
        with patch('budgeted_science.agents.runner.load_api_key', side_effect=AssertionError('offline credential')):
            path = asyncio.run(a.run(prepared, 'dry-run'))
        summary = a.read(path / 'summary.json')
        self.assertEqual((summary['completed'], summary['abstained'], summary['actual_offline_api_usd']), (6, 18, 0))
        result = a.read(path / 'results.json')[0]
        episode = Path(result['path'])
        request = a.read(episode / 'api/generation-002-request.json')
        self.assertTrue(any(x.get('encrypted_content') == 'opaque-fixture' for x in request['input']))
        self.assertEqual(request['reasoning']['effort'], 'high')
        names = ('transcript.md', 'report.md', 'evaluation.json', 'events.jsonl')
        before = {n: (episode / n).read_bytes() for n in names}
        with patch.object(a, 'Audit', side_effect=AssertionError('render solver')):
            a.regenerate(episode)
            a.render_campaign(path)
        self.assertTrue(all((episode / n).read_bytes() == value for n, value in before.items()))

    def test_freeze_and_exclusive_attempt(self):
        for kwargs in ({'model': 'gpt-5.6-sol'}, {'scientific_budget': 24}, {'api_ceiling_usd': '3'}):
            with self.assertRaises(ValueError):
                a.Config(**kwargs)
        prepared = self.prepare_fixture()
        a.load_prepared(prepared)
        a.previous.mark_attempt(prepared / 'live-attempt.json', {})
        with self.assertRaises(FileExistsError):
            asyncio.run(a.run(prepared, 'live', gateway_factory=a.Fake))
        manifest = a.read(prepared / 'manifest.json')
        file = prepared / 'slots' / manifest['slots'][0]['slot'] / 'payload.json'
        payload = a.read(file)
        payload['study']['public']['report'] += ' changed'
        file.write_text(json.dumps(payload), encoding='utf-8')
        with self.assertRaises(ValueError):
            a.load_prepared(prepared)

    def test_interrupted_stream_is_not_retried(self):
        class Broken(a.Fake):
            async def stream(self, body, metadata):
                yield {'type': 'response.output_text.delta', 'delta': 'saved partial fixture'}
                raise ConnectionError('fixture interrupted')
        prepared = self.prepare_fixture()
        path = asyncio.run(a.run(prepared, 'dry-run', gateway_factory=Broken))
        rows = a.read(path / 'results.json')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['termination_reason'], 'request_or_runner_error')
        self.assertTrue(rows[0]['api_budget']['unsettled_requests'])
        events, _ = read_events(rows[0]['path'])
        self.assertTrue(any(e['kind'] == 'api_stream_event' for e in events))


if __name__ == '__main__':
    unittest.main()
