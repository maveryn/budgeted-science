"""Offline scientific, accounting and API-adapter regression checks."""
import asyncio
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from budgeted_science.study_verification import experiment as science
from budgeted_science.study_verification.environment import Episode, Backend, analyze, process_inputs
from budgeted_science.transport_verification import numerics as num
from budgeted_science.agents.records import RunLog, read_events
from budgeted_science.agents.runner import run_episode
from budgeted_science.agents.study_verification import (StudyConfig, StudyInstance, StudyEpisode,
    StudyAdapter, StudyGateway, prompts, tool_definitions, regenerate)
from budgeted_science.agents import study_catalog as campaign


class StudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.studies = science.build_catalog()
        cls.study = cls.studies[0]

    def comparison(self, study=None):
        s = study or self.study
        e = Episode(s).evaluation()
        e.update(verdict="ACCEPT", correct=e["valid"], incomplete=False, coverage=True)
        return {p: {"evaluation": deepcopy(e)} for p in science.POLICIES}

    def instance(self):
        return StudyInstance(self.study, self.comparison())

    def test_catalog_size_labels_and_no_label_artifacts(self):
        self.assertEqual(len(self.studies), 12)
        self.assertEqual(len({s['id'] for s in self.studies}), 12)
        self.assertEqual(sum(Episode(s).evaluation()['valid'] for s in self.studies), 6)
        for s in self.studies:
            text = json.dumps(s['artifacts'])
            for key in ('private_selection', 'expected_valid', 'reference', 'harmless_input', 'family'):
                self.assertNotIn('"'+key+'"', text)
            self.assertEqual(set(s['artifacts']), set(self.study['artifacts']))
            self.assertEqual(float(format(s['original_analysis']['value'], '.10g')), s['public']['claim']['value'])

    def test_unit_conversion(self):
        actual = process_inputs({'velocity_cm_s': 60, 'diffusivity_cm2_s': 30, 'decay_per_s': .1}, 2, 3)
        np.testing.assert_allclose([actual['v'], actual['D'], actual['k']], [.9, .00225, .3])
        for value in (0, True, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                process_inputs(self.study['public']['raw_inputs'], value, 1)

    def test_analysis_exact_linear_and_window(self):
        run = {'status': 'complete', 'times': [0., .3, 1.], 'sensor': [0., .6, 2.]}
        self.assertAlmostEqual(analyze(run, .1, .8, 'trapezoid')['value'], .8**2-.1**2)
        self.assertLess(analyze(run, 0, 1, 'left')['value'], 1.)
        self.assertGreater(analyze(run, 0, 1, 'right')['value'], 1.)
        for args in ((1, 0, 'trapezoid'), (0, 2, 'left'), (0, 1, 'bad')):
            with self.assertRaises(ValueError):
                analyze(run, *args)

    def test_intended_reference_and_actual_pipeline(self):
        for s in self.studies:
            np.testing.assert_allclose(list(process_inputs(s['public']['raw_inputs'], **s['public']['intended_normalization']).values()), list(s['system'].values()))
            config = s['artifacts']['analysis']['content']['config']
            self.assertEqual(analyze(s['original'], **config), {k:v for k,v in s['original_analysis'].items() if k != 'run_id'})
            self.assertLess(s['reference']['checks']['image_fourier_max_abs'], 1e-10)

    def test_input_prepare_and_analysis_do_not_call_solver(self):
        ep = Episode(self.study)
        with patch.object(num, 'solve', side_effect=AssertionError('unpaid solve')):
            p = ep.tools.call('prepare_inputs', {'length_m': 1., 'duration_s': 1.})
            a = ep.tools.call('analyze_run', {'run_id': 'original', 'start': 0., 'end': 1., 'method': 'trapezoid'})
            self.assertIn('input_id', p)
            self.assertIn('analysis_id', a)
        self.assertEqual(ep.spent, 0)

    def test_only_input_action_changes_inputs(self):
        s = next(s for s in self.studies if s['private_selection']['family'] == 'input')
        ep = Episode(s)
        cfg = science.choose_config(s['public']['processed_inputs'], 4)
        result = ep.tools.call('run_simulation', {'input_id': 'study-input', **cfg})
        self.assertEqual(result['system_used'], s['public']['processed_inputs'])
        self.assertNotEqual(result['system_used'], s['system'])
        self.assertNotIn('qois', result)

    def test_analysis_settings_not_silently_fixed(self):
        s = next(s for s in self.studies if s['private_selection']['family'] == 'analysis')
        ep = Episode(s)
        a = ep.tools.call('analyze_run', {'run_id': 'original', 'start': 0., 'end': .875, 'method': 'trapezoid'})
        b = ep.tools.call('analyze_run', {'run_id': 'original', 'start': 0., 'end': 1., 'method': 'trapezoid'})
        self.assertLess(a['value'], b['value']*.9)

    def test_original_reuse_and_backend_accounting(self):
        shared = Backend()
        cfg = num.config(64, 1/256, output_dt=1/128)
        spends = []
        for index in range(2):
            ep = Episode(self.study, backend=shared)
            args = {'input_id': 'study-input', **cfg}
            a = ep.tools.call('run_simulation', args, 'paid')
            self.assertEqual(a, ep.tools.call('run_simulation', args, 'paid'))
            self.assertEqual(ep.tools.call('run_simulation', args, 'reuse')['charge'], 0)
            self.assertEqual(ep.tools.call('run_simulation', {'input_id': 'study-input', **self.study['original']['config']})['charge'], 0)
            self.assertEqual(a['backend_cache_hit'], bool(index))
            spends.append(ep.spent)
        self.assertEqual(spends[0], spends[1])
        self.assertGreater(spends[0], 0)

    def test_failed_work_charged_and_cached(self):
        def fail(p, cfg):
            return {'status':'failed', 'reason':'synthetic', 'config':cfg, 'times':[0.], 'sensor':[0.], 'fields':[[0.]*cfg['nx']], 'work':cfg['nx']*3, 'credits':cfg['nx']*3/num.WORK_UNIT}
        backend = Backend(solver=fail)
        for _ in range(2):
            ep = Episode(self.study, backend=backend)
            r = ep.tools.call('run_simulation', {'input_id':'study-input', **num.config()})
            self.assertEqual(r['status'], 'failed')
            self.assertEqual(ep.spent, 64*3)
            self.assertIn('error', ep.tools.call('analyze_run', {'run_id':r['run_id'], 'start':0, 'end':1, 'method':'trapezoid'}))

    def test_budget_invalid_unaffordable_and_call_conflict(self):
        ep = Episode(self.study, credits=.5)
        self.assertIn('error', ep.tools.call('run_simulation', {'input_id':'study-input', **num.config()}))
        self.assertEqual(ep.spent, 0)
        ep.tools.call('budget', {}, 'one')
        with self.assertRaises(ValueError):
            ep.tools.call('describe', {}, 'one')
        self.assertIn('error', ep.tools.call('quote', {'input_id':'missing', **num.config()}))

    def test_verdict_truth_not_injected_family(self):
        s = deepcopy(next(s for s in self.studies if s['private_selection']['family'] == 'input'))
        s['public']['claim']['value'] = s['reference']['qois']['exposure']
        ep = Episode(s)
        ep.tools.call('submit', {'verdict':'ACCEPT', 'diagnosis':'not scored', 'evidence_ids':['original'], 'justification':'synthetic cancellation fixture'})
        self.assertTrue(ep.evaluation()['correct'])

    def test_abstain_bad_evidence_and_boundaries(self):
        ep = Episode(self.study)
        self.assertIn('error', ep.tools.call('submit', {'verdict':'REJECT','diagnosis':'x','evidence_ids':['private'],'justification':'x'}))
        ep.tools.call('submit', {'verdict':'ABSTAIN','diagnosis':'x','evidence_ids':['problem'],'justification':'x'})
        self.assertTrue(ep.evaluation()['abstention'])
        self.assertFalse(ep.evaluation()['correct'])
        from budgeted_science.transport_verification.environment import within
        self.assertTrue(within(1.03,1,.03))
        self.assertFalse(within(1.031,1,.03))

    def test_cpu_controls_use_only_public_interface(self):
        class OnlyPublic:
            def __init__(self, tools): self.call = tools.call
        with patch.object(num, 'reference', side_effect=AssertionError('policy reference')):
            for p in science.POLICIES:
                ep = Episode(self.study)
                science.policy(OnlyPublic(ep.tools), p)
                self.assertFalse(ep.evaluation()['incomplete'])
                self.assertLessEqual(ep.evaluation()['spent'],4)

    def test_config_schemas_and_private_prompt(self):
        cfg = StudyConfig()
        for change in ({'model':'gpt-5.6-sol'}, {'api_ceiling_usd':'3'}, {'scientific_budget':5}):
            with self.assertRaises(ValueError): replace(cfg, **change)
        for t in tool_definitions():
            self.assertEqual(set(t['parameters']['required']),set(t['parameters']['properties']))
            self.assertTrue(t['strict'])
        with tempfile.TemporaryDirectory() as d:
            log = RunLog(d,'test')
            ep = StudyEpisode(cfg,self.instance(),log)
            text = json.dumps(prompts(cfg,ep))
            for forbidden in ('private_selection','expected_valid','end_to_end',str(self.study['reference']['qois']['exposure'])):
                self.assertNotIn(forbidden,text)
            self.assertFalse(ep.execute('bad','run_simulation','{"nx":NaN}')['ok'])
            self.assertIn('inputs',ep.checkpoint()['environment'])
            log.close()

    def test_offline_episode_and_regeneration(self):
        with tempfile.TemporaryDirectory() as d, patch('budgeted_science.agents.runner.load_api_key',side_effect=AssertionError('key')):
            gateway = StudyGateway()
            path, reason = asyncio.run(run_episode(science.ROOT,Path(d),mode='dry-run',config=StudyConfig(),instance=self.instance(),adapter=StudyAdapter(),gateway=gateway))
            self.assertEqual(reason,'submitted')
            self.assertTrue(any(i.get('encrypted_content') == 'opaque-fixture' for i in gateway.requests[1]['input']))
            before = (path/'transcript.md').read_bytes()
            with patch.object(num,'solve',side_effect=AssertionError('offline solve')):
                regenerate(path)
            self.assertEqual(before,(path/'transcript.md').read_bytes())
            events,torn = read_events(path)
            self.assertFalse(torn)
            self.assertEqual(sum(e['kind']=='api_response' for e in events),2)

    def test_interruption_retains_logs_and_reservation(self):
        class Broken(StudyGateway):
            async def stream(self,body,metadata):
                yield {'type':'response.created','response':{'id':'partial-test'}}
                raise OSError('synthetic interruption')
        with tempfile.TemporaryDirectory() as d:
            path,_ = asyncio.run(run_episode(science.ROOT,Path(d),mode='dry-run',config=StudyConfig(),instance=self.instance(),adapter=StudyAdapter(),gateway=Broken()))
            result=json.loads((path/'evaluation.json').read_text())
            self.assertTrue(result['evaluation']['incomplete'])
            self.assertGreater(float(result['api_budget']['uncertain_reserved_usd']),0)
            self.assertIn('partial-test',(path/'transcript.md').read_text())

    def test_live_override_blocked(self):
        with patch.object(campaign,'read_catalog',side_effect=AssertionError('access')):
            with self.assertRaises(ValueError):
                asyncio.run(campaign.run_catalog('unused',mode='live',gateway_factory=lambda i:StudyGateway()))

    def test_offline_batch_unique_and_no_credentials(self):
        comps = {s['id']: self.comparison(s) for s in self.studies}
        with tempfile.TemporaryDirectory() as d, patch.object(campaign,'read_catalog',return_value=(self.studies,comps,{})), patch('budgeted_science.agents.runner.load_api_key',side_effect=AssertionError('key')):
            path = asyncio.run(campaign.run_catalog('fixture',Path(d),mode='dry-run'))
            before=(path/'report.md').read_bytes()
            with patch.object(num,'solve',side_effect=AssertionError('offline solve')), patch.object(campaign,'run_episode',side_effect=AssertionError('offline API')):
                result=campaign.render(path)
            self.assertEqual(result['attempted'],12)
            self.assertEqual(result['overall']['correct'],6)
            self.assertEqual(result['unfinalized_attempts'],0)
            self.assertLess(float(result['batch_budget']['committed_upper_usd']),2)
            self.assertEqual(before,(path/'report.md').read_bytes())


if __name__ == '__main__': unittest.main()
