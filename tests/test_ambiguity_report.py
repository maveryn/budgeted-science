"""Offline tests for the report-style condition; no paid API calls."""
import asyncio
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_ambiguity_agent import fixture, comparisons
from budgeted_science.agents import ambiguity_agent as base
from budgeted_science.agents import ambiguity_report as report
from budgeted_science.agents import ambiguity_report_catalog as campaign
from budgeted_science.agents.records import RunLog, read_events, digest
from budgeted_science.agents.runner import run_episode
from budgeted_science.agents.transport_verification import TransportInstance

science = base.science


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.study = fixture()

    def instance(self):
        return TransportInstance(deepcopy(self.study), comparisons(self.study, 32))

    def episode(self, root):
        log = RunLog(root, 'test')
        self.addCleanup(log.close)
        return report.ReportEpisode(report.ReportConfig(), self.instance(), log)

    def test_frozen_settings(self):
        for change in ({'model':'gpt-5.6-sol'}, {'reasoning_effort':'low'}, {'api_ceiling_usd':'3'}, {'scientific_budget':100}):
            with self.assertRaises(ValueError): replace(report.ReportConfig(), **change)

    def test_report_data_and_claim_endpoints_preserved(self):
        s = deepcopy(self.study)
        s['public'].update(claim='old claim',scope='old hints',cost='old cost hints')
        before = digest(s)
        v = report.public_view(s)
        for key, value in s['public'].items():
            if key not in ('claim','scope','cost'): self.assertEqual(v['study'][key], value)
        self.assertEqual(v['original'], s['original'])
        for bound in s['public']['claim_interval']: self.assertIn(format(bound,'.17g'),v['report']['text'])
        self.assertEqual(digest(s),before)
        self.assertIn('finite list',v['report']['text'])

    def test_no_strategy_or_private_hints_in_any_free_view(self):
        with tempfile.TemporaryDirectory() as root:
            ep=self.episode(root)
            with patch.object(science,'solve',side_effect=AssertionError('unpaid solve')):
                views=[report.prompts(ep.config,ep), report.tool_definitions(),
                       ep.execute('d','describe','{}'), ep.execute('r','record','{"id":"report"}'),
                       ep.execute('o','record','{"id":"observations"}')]
            text=json.dumps(views).lower()
            for hint in ('counterexample','witness','exhaustive','coverage','nominal fit','private','screened'):
                # The generic no-private-reference-access notice is allowed.
                if hint=='private': self.assertNotIn('"private"',text)
                else: self.assertNotIn(hint,text)
            for hidden in ('"bank"','"feasible"','"outside"','"regime"'):
                self.assertNotIn(hidden,text)
            self.assertEqual(ep.environment.spent,0)
            ep.log.close()

    def test_computation_and_batch_charges_match_scaffolded(self):
        with tempfile.TemporaryDirectory() as root:
            ep=self.episode(root)
            args={'checks':[{'candidate':27,'stage':s} for s in ('calibration','forecast')]}
            r=ep.execute('batch','check_batch',json.dumps(args))
            old=science.Audit(self.study,32)
            for i,check in enumerate(args['checks']):
                expected=old.call('check',check)
                self.assertEqual(r['result']['checks'][i]['run'],base.compact(expected)['run'])
            self.assertEqual(ep.environment.spent,old.spent)
            prior=ep.environment.spent
            ep.execute('batch','check_batch',json.dumps(args))
            self.assertEqual(ep.environment.spent,prior)
            self.assertFalse(ep.execute('batch','budget','{}')['ok'])
            ep.log.close()

    def test_neutral_submission_and_cited_pair_diagnostic(self):
        with tempfile.TemporaryDirectory() as root:
            ep=self.episode(root)
            r=ep.execute('b','check_batch',json.dumps({'checks':[{'candidate':27,'stage':s} for s in ('calibration','forecast')]}))
            ids=[v['id'] for v in r['result']['checks']]
            args={'verdict':'REJECT','evidence_ids':ids,'justification':'numerical discrepancy'}
            self.assertTrue(ep.execute('s','submit',json.dumps(args))['ok'])
            self.assertEqual(ep.submission,args)
            with patch.object(science,'solve',side_effect=AssertionError('evaluator solve')):
                e=ep.evaluate()
            self.assertTrue(e['correct'])
            self.assertTrue(e['evidence_backed_correct'])
            self.assertEqual(e['diagnostic_candidates_from_cited_pairs'],[27])
            self.assertIsNone(ep.environment.submission['witness'])
            self.assertNotIn('witness',ep.submission)
            ep.log.write_json('test-checkpoint.json',ep.checkpoint())
            ep.log.close()

    def test_uncited_checks_do_not_become_cited_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            ep=self.episode(root)
            ep.execute('b','check_batch',json.dumps({'checks':[{'candidate':27,'stage':s} for s in ('calibration','forecast')]}))
            ep.execute('s','submit',json.dumps({'verdict':'REJECT','evidence_ids':['report'],'justification':'guess'}))
            self.assertTrue(ep.evaluate()['correct'])
            self.assertFalse(ep.evaluate()['evidence_backed_correct'])
            self.assertEqual(ep.evaluate()['diagnostic_candidates_from_cited_pairs'],[])
            ep.log.close()

    def test_unknown_evidence_and_legacy_witness_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            ep=self.episode(root)
            for args in ({'verdict':'REJECT','witness':27,'justification':'old'},
                         {'verdict':'REJECT','evidence_ids':['private-reference'],'justification':'bad'}):
                self.assertFalse(ep.execute(json.dumps(args),'submit',json.dumps(args))['ok'])
                self.assertIsNone(ep.submission)
            self.assertTrue(ep.execute('s','submit',json.dumps({'verdict':'ABSTAIN','evidence_ids':[],'justification':'uncertain'}))['ok'])
            self.assertFalse(ep.evaluate()['incomplete'])
            self.assertTrue(ep.evaluate()['abstained'])
            ep.log.close()

    def test_invalid_batch_free_and_interrupted_work_charged(self):
        with tempfile.TemporaryDirectory() as root:
            ep=self.episode(root)
            self.assertFalse(ep.execute('b','check_batch',json.dumps({'checks':[{'candidate':0,'stage':'forecast'},{'candidate':125,'stage':'forecast'}]}))['ok'])
            self.assertEqual(ep.environment.spent,0)
            ep.environment.limit=3
            r=ep.execute('c','check_batch',json.dumps({'checks':[{'candidate':0,'stage':'forecast'},{'candidate':1,'stage':'forecast'}]}))
            self.assertEqual(ep.environment.spent,3)
            self.assertEqual(r['result']['not_executed'],1)
            ep.execute('s','submit',json.dumps({'verdict':'ABSTAIN','evidence_ids':['report'],'justification':'exhausted'}))
            self.assertTrue(ep.evaluate()['abstained'])
            ep.log.close()

    def test_logged_dry_run_replay_and_offline_regeneration(self):
        with tempfile.TemporaryDirectory() as root, patch('budgeted_science.agents.runner.load_api_key',side_effect=AssertionError('key')):
            gateway=report.ReportGateway()
            path,reason=asyncio.run(run_episode(science.ROOT,Path(root),mode='dry-run',config=report.ReportConfig(),instance=self.instance(),adapter=report.ReportAdapter(),gateway=gateway))
            self.assertEqual(reason,'submitted')
            self.assertTrue(any(i.get('encrypted_content')=='opaque-fixture' for i in gateway.requests[1]['input']))
            before=(path/'transcript.md').read_bytes()
            with patch.object(science,'solve',side_effect=AssertionError('offline solve')): report.regenerate(path)
            self.assertEqual(before,(path/'transcript.md').read_bytes())
            self.assertFalse(read_events(path)[1])

    def test_failed_stream_retains_unknown_reservation(self):
        class Broken(report.ReportGateway):
            async def stream(self,body,metadata):
                yield {'type':'response.created','response':{'id':'partial-report-fixture'}}
                raise OSError('synthetic failure')
        with tempfile.TemporaryDirectory() as root:
            path,_=asyncio.run(run_episode(science.ROOT,Path(root),mode='dry-run',config=report.ReportConfig(),instance=self.instance(),adapter=report.ReportAdapter(),gateway=Broken()))
            e=json.loads((path/'evaluation.json').read_text())
            self.assertTrue(e['evaluation']['incomplete'])
            self.assertGreater(float(e['api_budget']['uncertain_reserved_usd']),0)
            self.assertIn('partial-report-fixture',(path/'transcript.md').read_text())

    def test_four_slot_campaign_no_api_and_paired_report(self):
        cases=[deepcopy(self.study),deepcopy(self.study)]
        cases[1]['id']='second-fixture'
        cpu={f"{c['id']}:{b}":comparisons(c,b) for c in cases for b in science.BUDGETS}
        old={key:rows['screened'] for key,rows in cpu.items()}
        with tempfile.TemporaryDirectory() as root, patch.object(base,'read_catalog',return_value=(cases,cpu,{})), patch.object(campaign,'read_scaffolded',return_value=(old,{})), patch('budgeted_science.agents.runner.load_api_key',side_effect=AssertionError('key')):
            path=asyncio.run(campaign.run_catalog('cpu','old',Path(root),mode='dry-run'))
            before=(path/'report.md').read_bytes()
            with patch.object(science,'solve',side_effect=AssertionError('offline solve')):
                result=campaign.render(path)
            self.assertEqual(result['attempted'],4)
            self.assertEqual(result['abstained'],4)
            self.assertEqual(result['incomplete'],0)
            self.assertEqual(before,(path/'report.md').read_bytes())
            self.assertLess(float(result['batch_budget']['committed_upper_usd']),2)

    def test_scaffolded_import_frozen_cases_and_hashes(self):
        cases=[deepcopy(self.study),deepcopy(self.study)]
        cases[1]['id']='second-fixture'
        with tempfile.TemporaryDirectory() as root:
            log=RunLog(root,'fixture')
            log.write_json('manifest.json',{'mode':'live','config':base.AmbiguityConfig().public()})
            for i,(c,b) in enumerate((c,b) for c in cases for b in science.BUDGETS):
                ep=RunLog(root,'episode-fixture')
                ep.write_json('manifest.json',{'public_configuration':base.AmbiguityConfig(scientific_budget=b).public()})
                for file in ('prompts.json','tools.json','evaluation.json'): ep.write_json(file,{})
                ep.close()
                log.write_json(f'results/{i}.json',{'case_id':c['id'],'budget':b,'study_hash':digest(c),'run':str(ep.path),'termination_reason':'submitted'})
            log.close()
            result,source=campaign.read_scaffolded(log.path,cases)
            self.assertEqual(len(result),4)
            self.assertEqual(len(source['file_hashes']),21)
            cases[1]['id']='changed'
            with self.assertRaises(ValueError): campaign.read_scaffolded(log.path,cases)

    def test_live_gateway_override_refused(self):
        with self.assertRaises(ValueError):
            asyncio.run(campaign.run_catalog('unused','unused',mode='live',gateway_factory=lambda i:report.ReportGateway()))


if __name__=='__main__': unittest.main()
