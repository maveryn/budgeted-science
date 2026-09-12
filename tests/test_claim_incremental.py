"""CPU-only incremental refinement, policy, accounting and archival checks."""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from budgeted_science.agents.records import RunLog
from budgeted_science.claim_verification.numerics import Backend, configuration, output_grid, reference, solve
from budgeted_science.claim_verification.studies import make_study, validate_study
from budgeted_science.claim_verification_incremental.environment import IncrementalEpisode, bisect_times
from budgeted_science.claim_verification_incremental.policies import convergence_estimate, random_schedule, run_policy
from budgeted_science.claim_verification_incremental import pilot


@lru_cache()
def study():
    theta = (1., .08, 1.4)
    result = make_study(1, theta, "incremental-test",
        solve(theta, configuration("Euler", dt=.08, times=output_grid(2., .25))), reference(theta), 0)
    result['private']['profile'] = 'test'
    return result


class ContractTests(unittest.TestCase):
    def test_requires_euler(self):
        bad = deepcopy(study()); bad['run']['config']['method'] = 'DOP853'
        with self.assertRaises(ValueError):
            IncrementalEpisode(bad)

    def test_bisection_preserves_nodes_and_endpoints(self):
        values = [0., .3, 1., 8.]
        result = bisect_times(values)
        self.assertEqual(result, [0., .15, .3, .65, 1., 4.5, 8.])
        self.assertEqual(len(result), 2*len(values)-1)

    def test_integration_changes_only_timestep(self):
        ep = IncrementalEpisode(study())
        row = ep.tools.refine_integration(study()['run_id'])
        expected = deepcopy(study()['run']['config']); expected['dt'] /= 2
        self.assertEqual(ep.runs[row['run_id']]['config'], expected)
        self.assertEqual((row['charge'], row['remaining']), (3, 5))

    def test_sampling_changes_only_output_nodes(self):
        ep = IncrementalEpisode(study())
        row = ep.tools.refine_sampling(study()['run_id'])
        expected = deepcopy(study()['run']['config'])
        expected['output_times'] = bisect_times(expected['output_times'])
        self.assertEqual(ep.runs[row['run_id']]['config'], expected)
        self.assertEqual((row['charge'], row['remaining']), (2, 6))
        # New values must be sampled from the underlying Euler trajectory.
        np.testing.assert_array_equal(ep.runs[row['run_id']]['values'],
            solve(study()['private']['theta'], expected)['values'])

    def test_composition_and_diagnostic_configs_agree(self):
        configs = []
        for actions in [('refine_integration', 'refine_sampling'), ('refine_sampling', 'refine_integration')]:
            ep = IncrementalEpisode(study()); run_id = study()['run_id']
            for action in actions:
                run_id = ep.tools.call(action, {'run_id':run_id})['run_id']
            configs.append(ep.runs[run_id]['config'])
            self.assertEqual(ep.spent, 5)
        self.assertEqual(configs[0], configs[1])
        self.assertEqual(configs[0], pilot.refine_config(study()['run']['config'], 1, 1))

    def test_duplicate_call_and_purchased_reuse(self):
        ep = IncrementalEpisode(study()); args = {'run_id':study()['run_id']}
        first = ep.tools.call('refine_integration', args, 'a')
        self.assertEqual(first, ep.tools.call('refine_integration', args, 'a'))
        self.assertEqual(ep.tools.call('refine_integration', args, 'b')['charge'], 0)
        self.assertEqual(ep.spent, 3)
        self.assertEqual(ep.tools.call('refine_sampling', args, 'a')['status'], 'invalid')

    def test_shared_backend_does_not_share_purchases(self):
        backend = Backend()
        a, b = IncrementalEpisode(study(), backend=backend), IncrementalEpisode(study(), backend=backend)
        first = a.tools.refine_integration(study()['run_id'])
        second = b.tools.refine_integration(study()['run_id'])
        self.assertEqual(first['q'], second['q'])
        self.assertTrue(second['backend_cache_hit'])
        self.assertEqual((a.spent,b.spent), (3,3))

    def test_invalid_unaffordable_and_free_submission(self):
        ep = IncrementalEpisode(study(), credits=2)
        self.assertEqual(ep.tools.refine_integration(study()['run_id'])['status'], 'unaffordable')
        self.assertEqual(ep.tools.refine_sampling('unknown')['status'], 'invalid')
        self.assertEqual(ep.spent, 0)
        ep.tools.refine_sampling(study()['run_id'])
        ep.tools.submit('ABSTAIN', 'insufficient checking', [], 'Uncertain numerical residual.')
        self.assertTrue(ep.evaluate()['abstained'])

    def test_failed_purchase_still_charged_and_cached(self):
        ep = IncrementalEpisode(study())
        def failure(theta, config):
            return {'status':'failed', 'config':config}, False
        with patch.object(ep.backend, 'get', side_effect=failure) as get:
            first = ep.tools.refine_integration(study()['run_id'])
            second = ep.tools.refine_integration(study()['run_id'])
        self.assertEqual(first['status'], 'failed')
        self.assertEqual((ep.spent, second['charge'], get.call_count), (3,0,1))

    def test_public_budget_does_not_include_reference(self):
        ep = IncrementalEpisode(study())
        result = json.dumps(ep.tools.budget())
        for key in ('reference_q', 'theta', 'claim_valid', 'seed'):
            self.assertNotIn(key, result)
        self.assertEqual(ep.tools.call('reference', {})['status'], 'invalid')
        validate_study(study())


class PolicyTests(unittest.TestCase):
    def test_schedules_and_charges(self):
        for name, sequence, spent in [('fixed_IIS', ['I','I','S'], 8), ('fixed_ISS', ['I','S','S'], 7)]:
            ep = IncrementalEpisode(study())
            result = run_policy(ep.tools.call, name)
            self.assertEqual(result['actions'], sequence)
            self.assertEqual(ep.spent, spent)
            self.assertTrue(ep.evaluate()['valid_submission'])

    def test_random_reproducibility_and_affordability(self):
        for seed in range(30):
            a = random_schedule(seed)
            self.assertEqual(a, random_schedule(seed))
            spent = sum(3 if x=='I' else 2 for x in a)
            self.assertIn(spent, (7,8))
        ep = IncrementalEpisode(study())
        result = run_policy(ep.tools.call, 'random', 18)
        self.assertEqual(result['actions'], random_schedule(18))

    def test_adaptation_responds_only_to_public_changes(self):
        for qvalues, expected in [([100,90,89,88], 'I'), ([100,99,90,89], 'S')]:
            values = iter(qvalues[1:]); executed=[]
            def call(name, args):
                if name=='budget': return {'original_run_id':'r0'}
                if name=='list_artifacts': return {'artifacts':[{'role':'analysis','id':'a'}]}
                if name=='read_artifact': return {'content':'Result: 100\n'}
                if name=='recompute_peak': return {'q':qvalues[0]}
                if name=='submit': return {'status':'submitted'}
                executed.append(name)
                return {'status':'success','q':next(values),'run_id':f'r{len(executed)}'}
            result = run_policy(call, 'adaptive_change')
            self.assertEqual(result['actions'], ['I','S',expected])

    def test_extrapolation_known_linear_model(self):
        levels = [(0,0),(1,0),(1,1),(2,1)]
        records=[{'levels':list(v),'q':100+12*2**(-v[0])-8*4**(-v[1])} for v in levels]
        out=convergence_estimate(records)
        self.assertAlmostEqual(out['q'],100)
        self.assertEqual(out['axes_extrapolated'],[0,1])
        self.assertFalse(out['certified'])

    def test_no_extrapolation_without_refinement(self):
        self.assertIsNone(convergence_estimate([]))
        self.assertIsNone(convergence_estimate([{'levels':[0,0],'q':100}]))
        out=convergence_estimate([{'levels':[0,0],'q':104},{'levels':[1,0],'q':102}])
        self.assertAlmostEqual(out['q'],100)
        self.assertEqual(out['axes_extrapolated'],[0])

    def test_failure_abstains_without_reference(self):
        ep=IncrementalEpisode(study(),credits=2)
        result=run_policy(ep.tools.call,'fixed_IIS')
        self.assertEqual(result['failure'],'unaffordable')
        self.assertIsNone(result['extrapolated_verdict'])
        self.assertTrue(ep.evaluate()['abstained'])

    def test_margin_diagnostic_is_sufficient_not_certificate(self):
        for reported in np.linspace(90,110,41):
            for q in np.linspace(90,110,101):
                data={'reported_q':reported,'private':{'reference_q':100}}
                check=pilot.check_diagnostic(data,q)
                if check['margin_resolving']:
                    truth='ACCEPT' if abs(reported-100)<=5 else 'REJECT'
                    self.assertEqual(check['direct_verdict'],truth)

    def test_offline_render_and_archives(self):
        with tempfile.TemporaryDirectory() as directory:
            log=RunLog(Path(directory),'test')
            path=log.path
            frozen={'budget':8,'policies':['fixed_IIS'],'diagnostic_budgets':[8],'seeds':[1]}
            log.write_json('manifest.json',frozen)
            log.write_json('private/catalog.json',{'studies':[study()],'failures':[]})
            q=study()['private']['reference_q']
            log.write_json('private/reachable_checks.json',[
                {'case_id':study()['case_id'],'i':2,'s':1,'cost':8,'status':'success',**pilot.check_diagnostic(study(),q)}])
            pilot.evaluate_policy(log,study(),'fixed_IIS',0,Backend())
            log.close()
            with patch.object(Backend,'get',side_effect=AssertionError('render cannot run solver')):
                first=pilot.render(path)
                report=(path/'report.md').read_bytes()
                self.assertEqual(first,pilot.render(path))
                self.assertEqual(report,(path/'report.md').read_bytes())
            self.assertEqual(first['policies']['fixed_IIS']['episodes'],1)
            events=(path/'events.jsonl').read_text(encoding='utf-8')
            self.assertIn('tool_call',events)
            self.assertIn('tool_result',events)
            self.assertEqual(len(list((path/'episodes/000').glob('run-*.json'))),3)


if __name__=='__main__':
    unittest.main()
