"""Offline campaign contracts; no real credentials, target screening, or API calls."""

import asyncio
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from budgeted_science.agents import campaign as c
from budgeted_science.agents.campaign_reporting import summarize
from budgeted_science.agents.records import RunLog, read_events
from budgeted_science.agents.resource import ResourceAdapter, ResourceEpisode, ResourceInstance, prompts, tool_definitions
from budgeted_science.agents.resource_fake import ResourceScriptedGateway
from budgeted_science.agents.resume import prepare_resume
from budgeted_science.agents.runner import run_episode
from budgeted_science.resource_planning.config import harder_config
from budgeted_science.resource_planning.environment import Episode
from budgeted_science.resource_planning.harder_pilot import run_random
from budgeted_science.resource_planning.local_policy import LocalFit
from budgeted_science.resource_planning.random_local import fixed_design, run_random_local


class DesignTests(unittest.TestCase):
    def test_seeded_instance_and_validation(self):
        bounds = np.asarray(harder_config().bounds)
        instance = ResourceInstance.from_seed(5000, 1)
        expected = np.random.default_rng(5000).uniform(bounds[:, 0], bounds[:, 1])
        np.testing.assert_array_equal(instance.theta, expected)
        self.assertEqual(instance.noise_seed, 50001)
        self.assertEqual(ResourceInstance.from_seed(6000).theta, ResourceInstance.first_evaluation('v2').theta)
        for seed, replicate in ((-1, 0), (True, 0), (1, -1), (1, 10), (1, True)):
            with self.assertRaises(ValueError):
                ResourceInstance.from_seed(seed, replicate)

    def test_paired_prompts_private_instance_and_noise(self):
        instance = ResourceInstance.from_seed(5000)
        with tempfile.TemporaryDirectory() as temp:
            logs = [RunLog(temp, 'test') for _ in range(2)]
            try:
                episodes = [ResourceEpisode(c.configuration(model), instance, log)
                            for model, log in zip(c.MODELS, logs)]
                messages = [prompts(c.configuration(model), episode) for model, episode in zip(c.MODELS, episodes)]
                self.assertEqual(messages[0], messages[1])
                self.assertEqual(tool_definitions(c.configuration(c.MODELS[0])), tool_definitions(c.configuration(c.MODELS[1])))
                self.assertEqual(episodes[0].initial_observations, episodes[1].initial_observations)
                for value in instance.theta:
                    self.assertNotIn(str(value), json.dumps(messages))
                for name in ('target_seed', 'noise_seed', 'target_parameters', 'selection'):
                    self.assertNotIn(name, json.dumps(messages))
                a = episodes[0].tools.measure_target('x', 2.0)
                b = episodes[1].tools.measure_target('x', 2.0)
                self.assertEqual(a, b)
                self.assertNotEqual(ResourceInstance.from_seed(5001).theta, instance.theta)
            finally:
                for log in logs:
                    log.close()

    def test_random_plan_matches_gp_and_evidence_independence(self):
        config = harder_config(32)
        plans = []
        for seed in (5000, 5001):
            instance = ResourceInstance.from_seed(seed)
            episode = Episode(instance.theta, config, noise_seed=instance.noise_seed)
            events = []
            run_random_local(episode.tools, log=lambda kind, **data: events.append((kind, data)))
            plans.append(events[0][1])
            status = episode.tools.get_status()
            self.assertEqual(status['spent'], 32)
            self.assertEqual([sum(e['kind'] == k for e in status['ledger']) for k in
                              ('simulate_low', 'simulate_high', 'measure_target')], [12, 1, 1])
            evidence = episode.tools.evidence()
            fit = LocalFit(evidence, episode.tools.public_config)
            expected = (fit.lower + np.clip(fit.proposals()[0][1], 0, 1) * fit.width).tolist()
            np.testing.assert_array_equal(episode.evaluate()['theta_hat'], expected)
        self.assertEqual(plans[0], plans[1])
        gp_events = []
        episode = Episode(ResourceInstance.from_seed(5000).theta, config, noise_seed=50000)
        run_random(episode.tools, 0, None, lambda kind, **data: gp_events.append((kind, data)))
        gp_plan = gp_events[0][1]
        for field in ('low_locations', 'high', 'measurement'):
            self.assertEqual(plans[0][field], gp_plan[field])
        self.assertNotEqual(plans[0]['measurement'][1], 1)

    def test_final_fit_makes_no_physical_calls(self):
        instance = ResourceInstance.from_seed(5000)
        episode = Episode(instance.theta, harder_config(32), noise_seed=50000)
        original = LocalFit.proposals
        calls = []
        def checked(fit):
            with patch.object(type(episode.tools), 'simulate_low', side_effect=AssertionError('unpaid solve')), \
                 patch.object(type(episode.tools), 'simulate_high', side_effect=AssertionError('unpaid solve')), \
                 patch.object(type(episode.tools), 'measure_target', side_effect=AssertionError('unpaid observation')):
                calls.append(True)
                return original(fit)
        with patch.object(LocalFit, 'proposals', checked):
            run_random_local(episode.tools)
        self.assertEqual(calls, [True])

    def test_failed_high_retains_charge_without_submission(self):
        episode = Episode(ResourceInstance.from_seed(5000).theta, harder_config(32), noise_seed=50000)
        actual = episode.tools.simulate_high
        def failed(tools, theta):
            value = actual(theta)
            return {**value, 'status': 'failed'}
        with patch.object(type(episode.tools), 'simulate_high', failed):
            with self.assertRaises(RuntimeError):
                run_random_local(episode.tools)
        self.assertEqual(episode.tools.get_status()['spent'], 20)
        self.assertFalse(episode.evaluate()['valid'])

    def test_random_policy_rejects_other_budget(self):
        with self.assertRaises(ValueError):
            fixed_design(harder_config(40).public())


class CampaignTests(unittest.TestCase):
    def prepare(self, temp):
        return c.prepare(temp, rehearsal=True)

    def test_imports_freeze_and_untouched_prior_logs(self):
        before = {m: c.tree_hashes(p) for m, p in c.ANCHORS.items()}
        with tempfile.TemporaryDirectory() as temp:
            root = self.prepare(temp)
            manifest = c.verify(root)
            self.assertEqual(len(c.state(root)), 30)
            self.assertEqual(sum(s['status'] == 'imported' for s in c.state(root).values()), 5)
            self.assertEqual(manifest['seeds'], [6000, 5000, 5001, 5002, 5003])
            self.assertEqual(manifest['live_order'][:4], ['5000-gpt-5.6-sol', '5000-gpt-5.6-luna',
                                                       '5001-gpt-5.6-luna', '5001-gpt-5.6-sol'])
            self.assertEqual(manifest['api_ceiling_usd'], '24.00')
        self.assertEqual(before, {m: c.tree_hashes(p) for m, p in c.ANCHORS.items()})

    def test_source_and_import_changes_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.prepare(temp)
            actual = c.provenance(c.REPO)
            bad = deepcopy(actual)
            bad['source_hashes']['fake'] = 'changed'
            with patch.object(c, 'provenance', return_value=bad), self.assertRaises(ValueError):
                c.verify(root)
            with patch.object(c, 'tree_hashes', return_value={}), self.assertRaises(ValueError):
                c.verify(root)

    def test_anchor_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            c.validate_anchor(c.ANCHORS[c.MODELS[0]], c.MODELS[1])

    def test_duplicate_slot_is_not_a_second_sample(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.prepare(temp)
            identifier = c.slot_id(5000, c.MODELS[0])
            with c.journal(root) as log:
                c.durable_event(log, 'slot_started', slot_id=identifier, output_root=str(root / 'missing'))
                c.durable_event(log, 'slot_started', slot_id=identifier, output_root=str(root / 'missing'))
            with self.assertRaises(ValueError):
                c.state(root)

    def test_orphaned_attempt_is_reserved_and_not_relaunched(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.prepare(temp)
            with c.journal(root) as log:
                c.durable_event(log, 'slot_started', slot_id=c.slot_id(5000, c.MODELS[0]), output_root=str(root / 'missing'))
            self.assertEqual(c.charge_bound(c.state(root)), Decimal(3))
            with patch.object(c, 'run_episode', side_effect=AssertionError('duplicate paid run')):
                with self.assertRaises(ValueError):
                    asyncio.run(c.execute(root, mode='dry-run', continuation=True))

    def test_api_limits_and_incomplete_summary(self):
        slots = {}
        for i in range(8):
            slots[str(i)] = {'method': c.MODELS[i % 2], 'status': 'started'}
        self.assertEqual(c.charge_bound(slots), Decimal(24))
        for model in c.MODELS:
            cfg = c.configuration(model)
            self.assertEqual((cfg.reasoning_effort, cfg.scientific_budget, cfg.api_ceiling_usd), ('high', 32, '3.00'))
            self.assertEqual((cfg.max_responses, cfg.max_output_tokens, cfg.deadline_seconds), (30, 32768, 1200))
        example = {'a': {'method': 'local', 'case_seed': 6000, 'status': 'finished',
                        'result': {'evaluation': {'valid': True, 'success': True, 'parameter_error': .5}, 'termination_reason': 'submitted'}},
                   'b': {'method': 'local', 'case_seed': 5000, 'status': 'finished',
                        'result': {'evaluation': {'valid': False}, 'termination_reason': 'deadline'}},
                   'c': {'method': 'local', 'case_seed': 5001, 'status': 'pending'}}
        group = next(g for g in summarize(example) if g['method'] == 'local')
        self.assertEqual((group['successes'], group['attempted'], group['incomplete'], group['pending']), (1, 2, 1, 1))
        self.assertEqual(group['median_max_relative_error_percent'], 2.5)

    def test_snapshot_mismatch_rejected(self):
        instance = ResourceInstance.from_seed(5000)
        adapter = c.CampaignAdapter(instance, {})
        with tempfile.TemporaryDirectory() as temp:
            log = RunLog(temp, 'test')
            try:
                with self.assertRaises(ValueError):
                    adapter.run_comparisons(c.configuration(), ResourceInstance.from_seed(5001), log)
            finally:
                log.close()

    def test_scoring_detects_fabricated_result(self):
        episode = Episode(ResourceInstance.from_seed(5000).theta, harder_config(32))
        episode.tools.submit([1, .08, 1.4])
        evaluation = episode.evaluate()
        c.validate_scoring(evaluation, ResourceInstance.from_seed(5000))
        evaluation['parameter_error'] = 0
        with self.assertRaises(ValueError):
            c.validate_scoring(evaluation, ResourceInstance.from_seed(5000))

    def test_explicit_instance_survives_resume(self):
        class Interrupted(ResourceScriptedGateway):
            async def stream(self, body, metadata):
                if self.requests:
                    yield {'type': 'response.output_text.delta', 'delta': 'partial fixture'}
                    raise ConnectionError('offline interrupted stream')
                async for event in super().stream(body, metadata):
                    yield event
        with tempfile.TemporaryDirectory() as temp, patch.object(ResourceAdapter, 'run_comparisons', return_value={}):
            instance = ResourceInstance.from_seed(5001, 1)
            path, reason = asyncio.run(run_episode(c.REPO, temp, mode='dry-run', config=c.configuration(c.MODELS[1]),
                instance=instance, adapter=ResourceAdapter(), gateway=Interrupted()))
            saved = prepare_resume(path, mode='dry-run')
            self.assertEqual(saved['instance'], instance)
            self.assertGreater(saved['money'].reserved, 0)
            self.assertEqual(saved['config'].api_ceiling_usd, '3.00')

    def test_missing_usage_is_retained_and_halts_campaign(self):
        class MissingUsage(ResourceScriptedGateway):
            async def stream(self, body, metadata):
                async for event in super().stream(body, metadata):
                    if event['type'] == 'response.completed':
                        event['response'].pop('usage')
                    yield event
        with tempfile.TemporaryDirectory() as temp:
            instance = ResourceInstance.from_seed(5000)
            path, reason = asyncio.run(run_episode(c.REPO, temp, mode='dry-run', config=c.configuration(c.MODELS[1]),
                instance=instance, adapter=c.CampaignAdapter(instance, {}), gateway=MissingUsage()))
            self.assertEqual(reason, 'missing_or_invalid_usage')
            row = c.agent_row(5000, c.MODELS[1], path)
            self.assertEqual(len(row['api_budget']['unsettled_requests']), 1)
            self.assertTrue(c.fatal_agent_error(path))
            self.assertGreater(Decimal(row['api_budget']['committed_upper_usd']), 0)

    def test_finalized_journal_gap_recovered_without_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.prepare(temp)
            identifier = c.slot_id(5000, 'random_local')
            output = root / 'episodes' / identifier
            with c.journal(root) as log:
                c.durable_event(log, 'slot_started', slot_id=identifier, output_root=str(output))
            row = c.cpu_episode(5000, 'random_local', output)
            with patch.object(c, 'cpu_episode', side_effect=AssertionError('must not rerun')):
                with c.journal(root) as log:
                    c.recover_finalized(log)
            self.assertEqual(c.state(root)[identifier]['result'], row)

    def test_complete_rehearsal_and_idempotent_continuation(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch('budgeted_science.agents.runner.load_api_key', side_effect=AssertionError('offline credentials')):
            root = self.prepare(temp)
            calls = []
            def gateway(model, seed):
                calls.append((seed, model))
                return ResourceScriptedGateway(require_full_budget=True)
            with patch.object(c, 'cpu_episode', wraps=c.cpu_episode) as cpu:
                summary = asyncio.run(c.execute(root, mode='dry-run', gateway_factory=gateway))
                self.assertEqual(cpu.call_count, 17)
            self.assertTrue(summary['complete'])
            self.assertEqual(len(calls), 8)
            self.assertEqual(len(set(calls)), 8)
            self.assertEqual(len(summary['rows']), 30)
            self.assertTrue(all(g['attempted'] == 5 for g in summary['all_five']))
            self.assertTrue(all(g['attempted'] == 4 for g in summary['new_four']))
            self.assertEqual(sum(row['imported'] for row in summary['rows']), 5)
            before = [(root / p).read_bytes() for p in ('report.md', 'summary.json', 'events.jsonl')]
            c.render(root)
            self.assertEqual(before, [(root / p).read_bytes() for p in ('report.md', 'summary.json', 'events.jsonl')])
            with patch.object(c, 'run_episode', side_effect=AssertionError('duplicate model')), \
                 patch.object(c, 'cpu_episode', side_effect=AssertionError('duplicate CPU')):
                asyncio.run(c.execute(root, mode='dry-run', continuation=True))
            self.assertEqual(len(calls), 8)
            first = next(r for r in summary['rows'] if r['case_seed'] == 5000 and r['method'] == c.MODELS[0])
            second = next(r for r in summary['rows'] if r['case_seed'] == 5000 and r['method'] == c.MODELS[1])
            self.assertEqual((Path(first['path']) / 'prompts.json').read_bytes(),
                             (Path(second['path']) / 'prompts.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
