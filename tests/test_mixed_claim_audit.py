"""Heterogeneous claim contracts, accounting and offline runner; no live API."""
import asyncio
from copy import deepcopy
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from budgeted_science.multi_claim_audit import core as old, mixed as c
from budgeted_science.agents import mixed_claim_audit as a
from budgeted_science.agents.records import RunLog, read_events


class MixedClaims(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.study = c.build_study()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.log = RunLog(self.root, "test")
        self.episode = a.Episode(a.Config(), a.Instance(self.study), self.log)
        self.counter = 0

    def tearDown(self):
        self.log.close()
        self.temp.cleanup()

    def call(self, name, **args):
        self.counter += 1
        return self.episode.execute(f"call-{self.counter}", name, json.dumps(args))

    def verdicts(self):
        return {f"C{i}": "ABSTAIN" for i in range(1,7)}

    def test_six_distinct_claims_and_reproducible_shuffle(self):
        study = c.build_study()
        self.assertEqual(study, self.study)
        claims = study["public"]["claims"]
        self.assertEqual(len({v["kind"] for v in claims}), 6)
        self.assertEqual([v["id"] for v in claims], [f"C{i}" for i in range(1,7)])
        self.assertEqual([v["kind"] for v in claims], ["target_agreement", "numerical_point", "cumulative_abundance", "intervention_effect", "target_composition", "target_recovery"])
        self.assertEqual(study["private"]["permutation"], np.random.default_rng(c.SHUFFLE_SEED).permutation(6).tolist())

    def test_report_is_derived_from_actual_euler_outputs(self):
        low = self.study["public"]["original"]
        alt = self.study["private"]["intervention_original_table"]
        for claim in self.study["public"]["claims"]:
            self.assertIn(claim["text"], self.study["public"]["report"])
            kind = claim["kind"]
            if kind in ("numerical_point", "cumulative_abundance"):
                self.assertEqual(claim["reported_value"], c.printed(c.quantity(kind, low)))
            elif kind == "target_agreement":
                self.assertEqual(claim["reported_value"], c.printed(c.table_value(low, "x", 4)))
            elif kind == "target_composition":
                self.assertEqual(claim["reported_value"], c.printed(c.table_value(low,"y",6)/c.table_value(low,"x",6)))
            elif kind == "intervention_effect":
                self.assertEqual(claim["threshold"], math.floor(100*c.quantity(kind, low, alt))/100)

    def test_quantities_against_hand_calculations(self):
        table = {"times": list(c.GRID[1:]), "values": [[10.,5.]]*16}
        intervention = {"times": list(c.GRID[1:]), "values": [[8.,5.]]*16}
        self.assertEqual(c.quantity("cumulative_abundance", table), 80.)
        # Initial prey remains 10 in both trajectories and is included in peak.
        self.assertEqual(c.quantity("intervention_effect", table, intervention), 0.)
        table["values"] = [[20.,5.]]*16
        self.assertEqual(c.quantity("intervention_effect", table, intervention), .5)
        obs = {("x",4.):10., ("x",6.):15., ("y",6.):3.}
        self.assertEqual(c.quantity("target_recovery", observations=obs), .5)
        self.assertEqual(c.quantity("target_composition", observations=obs), .2)
        self.assertIsNone(c.quantity("target_composition", observations={("x",6.):15.}))
        self.assertIsNone(c.quantity("target_recovery", observations={("x",4.):-1.,("x",6.):2.}))
        with self.assertRaises(ValueError):
            c.field({"times":[1.],"values":[[1.,1.]]})

    def test_reference_agreement_and_intervention_changes_only_theta2(self):
        self.assertEqual(c.INTERVENTION_THETA, (1.,.088,1.4))
        self.assertAlmostEqual(c.INTERVENTION_THETA[1]/c.REPORT_THETA[1],1.1)
        for ref in self.study["private"]["references"].values():
            self.assertLess(ref["max_solver_disagreement"],1e-7)
            self.assertLess(ref["max_service_disagreement"],1e-6)
        claim = next(x for x in self.study["public"]["claims"] if x["kind"]=="intervention_effect")
        cheap = self.study["public"]["intervention_summary"]["estimated_peak_reduction"]
        accurate = self.study["private"]["truth"][claim["id"]]["reference_value"]
        self.assertEqual(c.classify(claim,cheap)["verdict"],"ACCEPT")
        self.assertEqual(c.classify(claim,accurate)["verdict"],"REJECT")

    def test_operator_boundaries_and_finite_validation(self):
        q = {"operator":"relative_error_le","reported_value":105.,"relative_tolerance":.05}
        self.assertEqual(c.classify(q,100)["verdict"],"ACCEPT")
        q["reported_value"]=105.001
        self.assertEqual(c.classify(q,100)["verdict"],"REJECT")
        q = {"operator":"ge","threshold":.2}
        self.assertEqual(c.classify(q,.2)["verdict"],"ACCEPT")
        self.assertEqual(c.classify(q,.1999)["verdict"],"REJECT")
        for v in (float('nan'),float('inf'),None,True):
            with self.assertRaises(ValueError): c.classify(q,v)

    def test_target_and_noise_match_existing_planning_and_audit(self):
        prior = old.build_study()
        self.assertEqual(prior["private"]["target_parameters"], self.study["private"]["target_parameters"])
        baseline = old.Audit(prior)
        for variable,t in (("x",4.),("x",6.)):
            self.assertEqual(self.call("measure_target",variable=variable,time=t)["value"],
                             baseline.dispatch("measure_target",{"variable":variable,"time":t})["value"])

    def test_same_prices_and_cache_reuse(self):
        self.assertEqual(self.call("simulate_low",theta=list(c.REPORT_THETA))["charge"],0)
        high=self.call("simulate_high",theta=list(c.REPORT_THETA))
        self.assertEqual(high["charge"],8)
        self.assertEqual(self.call("simulate_high",theta=list(c.REPORT_THETA))["charge"],0)
        self.assertEqual(self.call("simulate_low",theta=list(c.INTERVENTION_THETA))["charge"],1)
        first=self.call("measure_target",variable="x",time=4.)
        again=self.call("measure_target",variable="x",time=4.)
        self.assertEqual((first["charge"],again["charge"]),(12,0))
        self.assertEqual(first["value"],again["value"])
        self.assertEqual(self.episode.environment.status()["spent"],21)

    def test_invalid_and_unaffordable_are_uncharged(self):
        for name,args in [("measure_target",{"variable":"x","time":1.1}),
                          ("simulate_high",{"theta":[5.,.08,1.4]}),
                          ("simulate_high",{"theta":[1.,.08,float('nan')]}),
                          ("reference",{})]:
            self.assertEqual(self.call(name,**args)["status"],"invalid")
        c.fixed_policy(self.call,self.study["public"])
        self.assertEqual(self.episode.environment.status()["spent"],32)
        events,_=read_events(self.log.path)
        unaffordable=[e for e in events if e["kind"]=="tool_result" and e['output']['status']=='unaffordable']
        self.assertEqual(len(unaffordable),2)

    def test_duplicates_do_not_repurchase_and_failed_solves_charged(self):
        args=json.dumps({"theta":[1.01,.08,1.4]})
        with patch("budgeted_science.resource_planning.environment._solve_low",side_effect=ValueError("synthetic failure")) as solver:
            r=self.episode.execute("same","simulate_low",args)
            duplicate=self.episode.execute("same","simulate_low",args)
            cached=self.episode.execute("different","simulate_low",args)
        self.assertEqual(r,duplicate)
        self.assertEqual((r['status'],r['charge'],cached['charge']),('failed',1,0))
        self.assertEqual(solver.call_count,1)

    def test_independent_budgets_and_free_retrieval(self):
        self.call('simulate_high',theta=list(c.REPORT_THETA))
        other=c.Audit(self.study)
        self.assertEqual(other.dispatch('simulate_high',{'theta':list(c.REPORT_THETA)})['charge'],8)
        for t in (4.,6.): self.call('measure_target',variable='x',time=t)
        self.assertEqual(self.call('get_status')['remaining'],0)
        with patch('budgeted_science.resource_planning.environment._solve_high',side_effect=AssertionError('unpaid')):
            self.assertEqual(self.call('evidence')['status'],'success')
            self.assertEqual(self.call('compare_cached_candidates')['status'],'success')
        self.assertEqual(self.call('submit',verdicts=self.verdicts(),evidence_ids=[],explanation='Unresolved')['status'],'submitted')

    def test_fixed_cpu_32_and_complete_evidence_52(self):
        for budget,expected in ((32,(4,0,2)),(52,(6,0,0))):
            r=a.run_cpu(self.study,self.root,a.Config(scientific_budget=budget))
            self.assertEqual((r['correct'],r['wrong'],r['abstained']),expected)
            self.assertEqual(r['scientific_status']['spent'],budget)
        r=a.read_json(Path(r['path'])/'evaluation.json')
        self.assertEqual(r['scientific_status']['ledger'][-1]['kind'],'measure_target')

    def test_fixed_policy_ignores_presentation_order(self):
        other=deepcopy(self.study)
        other['public']['claims'].reverse()
        one=a.run_cpu(self.study,self.root)
        two=a.run_cpu(other,self.root)
        self.assertEqual(one['submission'],two['submission'] | {'explanation':one['submission']['explanation']})
        self.assertEqual(one['scientific_status']['ledger'],two['scientific_status']['ledger'])

    def test_classical_arithmetic_calls_no_solver(self):
        table=self.study['public']['original']
        with patch('budgeted_science.resource_planning.environment._solve_high',side_effect=AssertionError('unpaid')), \
             patch('budgeted_science.resource_planning.environment._solve_low',side_effect=AssertionError('unpaid')):
            self.assertIsNotNone(c.quantity('cumulative_abundance',table))
            self.assertIsNotNone(c.quantity('intervention_effect',table,table))

    def test_privacy_and_no_dependency_or_reference_tool(self):
        material=json.dumps([a.prompts(a.Config(),self.episode),a.tool_definitions(),
                             self.call('evidence'),self.call('get_status'),self.call('compare_cached_candidates')])
        for key in ('target_parameters','target_seed','noise_seed','shuffle_seed','radau_values','reference_value','permutation','private'):
            # Developer text mentions private evaluator access; structured data may not.
            if key!='private': self.assertNotIn(key,material)
        for value in self.study['private']['target_parameters']: self.assertNotIn(str(value),material)
        self.assertNotIn('dependency',material)

    def test_scoring_incomplete_abstain_and_wrong(self):
        self.assertEqual(self.episode.evaluate()['incomplete_claims'],6)
        verdicts={k:v['verdict'] for k,v in self.study['private']['truth'].items()}
        verdicts['C2']='REJECT'
        verdicts['C1']='ABSTAIN'
        self.call('submit',verdicts=verdicts,evidence_ids=['report'],explanation='Fixture')
        r=self.episode.evaluate()
        self.assertEqual((r['correct'],r['wrong'],r['abstained']),(4,1,1))
        self.assertFalse(r['explanations_semantically_graded'])

    def test_submission_validation(self):
        for verdicts,ids in [({'C1':'ACCEPT'},[]),(self.verdicts(),['unknown'])]:
            self.assertEqual(self.call('submit',verdicts=verdicts,evidence_ids=ids,explanation='x')['status'],'invalid')
        self.assertIsNone(self.episode.submission)

    def test_model_config_frozen(self):
        for kwargs in ({'model':'gpt-5.6-sol'},{'reasoning_effort':'low'},{'api_ceiling_usd':'2'}, {'scientific_budget':40}):
            with self.assertRaises(ValueError): a.Config(**kwargs)
        self.assertEqual(a.Config().scientific_budget,32)

    def test_offline_rehearsal_history_and_regeneration(self):
        with patch.object(a,'build_study',return_value=deepcopy(self.study)):
            prepared=a.prepare(self.root)
        with patch('budgeted_science.agents.runner.load_api_key',side_effect=AssertionError('no keys')):
            run=asyncio.run(a.run(prepared,'dry-run',self.root))
        r=a.read_json(run/'evaluation.json')
        self.assertEqual((r['termination_reason'],r['evaluation']['abstained']),('submitted',6))
        self.assertEqual(r['fixed_policy']['correct'],4)
        body=a.read_json(run/'api/generation-002-request.json')
        self.assertTrue(any(i.get('type')=='reasoning' for i in body['input']))
        self.assertEqual(body['reasoning'],{'effort':'high','summary':'auto'})
        before={name:(run/name).read_bytes() for name in ('report.md','transcript.md','evaluation.json','events.jsonl')}
        with patch.object(c,'build_study',side_effect=AssertionError('no rebuilding')):
            a.regenerate(run)
        self.assertTrue(all((run/name).read_bytes()==content for name,content in before.items()))

    def test_frozen_source_and_second_launch_protection(self):
        with patch.object(a,'build_study',return_value=deepcopy(self.study)):
            prepared=a.prepare(self.root)
        asyncio.run(a.run(prepared,'live',self.root,gateway=a.legacy.Fake()))
        with self.assertRaises(FileExistsError): asyncio.run(a.run(prepared,'live',self.root,gateway=a.legacy.Fake()))
        manifest=a.read_json(prepared/'manifest.json')
        manifest['configuration']['scientific_budget']=52
        with patch.object(a,'read_json',side_effect=lambda p: manifest if Path(p).name=='manifest.json' else a.legacy.read_json(p)):
            with self.assertRaises(ValueError): a.load_prepared(prepared)


if __name__=='__main__':
    unittest.main()
