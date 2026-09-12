"""Offline adapter, matched snapshot, logging and explicit-resume checks."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from budgeted_science.agents.records import RunLog, digest, read_events
from budgeted_science.agents.runner import run_episode
from budgeted_science.agents.verification import VerificationConfig
from budgeted_science.agents.verification_fake import VerificationGateway
from budgeted_science.agents.verification_incremental import (
    IncrementalConfig, IncrementalInstance, IncrementalAgentEpisode, IncrementalAdapter,
    prompts, tool_definitions, prepare_resume)
from budgeted_science.agents.verification_incremental_catalog import (
    ROOT, CATALOG, read_catalog, render, run_catalog)
from budgeted_science.claim_verification.numerics import Backend
from budgeted_science.claim_verification.studies import make_study
from budgeted_science.claim_verification_incremental.environment import IncrementalEpisode
from budgeted_science.claim_verification_incremental.policies import run_policy
from test_claim_incremental import study


def fixture():
    first=deepcopy(study())
    first['private']['cohort']='fresh'
    first['private']['category']='integration_valid'
    second=make_study(2,first['private']['theta'],'fixture',first['run'],
        {'q':first['private']['reference_q'],'checks':first['private']['reference_checks']},1)
    second['private'].update(cohort='fresh',category='integration_valid')
    cases=[first,second]; comparisons={}
    for s in cases:
        comparisons[s['case_id']]={}
        for policy in ('fixed_IIS','fixed_ISS','random','adaptive_change'):
            ep=IncrementalEpisode(s)
            diagnostics=run_policy(ep.tools.call,policy,estimator='extrapolation')
            comparisons[s['case_id']][policy]={'evaluation':ep.evaluate(),'diagnostics':diagnostics}
    return cases,comparisons,{'path':'fixture','catalog_digest':'fixture','omitted_slots':[],'file_hashes':{}}


class ContractTests(unittest.TestCase):
    def test_frozen_configuration_and_old_defaults(self):
        c=IncrementalConfig()
        self.assertEqual((c.model,c.reasoning_effort,c.scientific_budget),('gpt-5.6-luna','high',8))
        self.assertEqual(c.max_output_tokens,32768)
        self.assertEqual(VerificationConfig().scientific_budget,5)
        for kwargs in ({'scientific_budget':5},{'model':'gpt-5.6-sol'},{'reasoning_effort':'low'},
                       {'api_ceiling_usd':'4'},{'require_full_budget':True}):
            with self.assertRaises(ValueError):
                IncrementalConfig(**kwargs)

    def test_tools_have_incremental_semantics_without_oracle(self):
        tools=tool_definitions()
        text=json.dumps(tools)
        self.assertIn('halve',text); self.assertIn('bisect',text)
        self.assertNotIn('DOP853',text); self.assertNotIn('0.0025',text)
        self.assertEqual(len(tools),8)
        self.assertFalse({'reference','fit','extrapolate','python'} & {t['name'] for t in tools})

    def test_public_prompt_and_actual_refinement_agree(self):
        with tempfile.TemporaryDirectory() as folder:
            log=RunLog(folder,'test')
            try:
                ep=IncrementalAgentEpisode(IncrementalConfig(),IncrementalInstance(study()),log)
                text=json.dumps(prompts(IncrementalConfig(),ep))
                self.assertIn('8 audit credits',text); self.assertNotIn('5 audit credits',text)
                self.assertIn('halves the current Euler timestep',text)
                for private in ('reference_q','claim_valid','selection_order','theta','fixed_IIS'):
                    self.assertNotIn(private,text)
                a=ep.execute('a','refine_integration',json.dumps({'run_id':study()['run_id']}))
                b=ep.execute('b','refine_integration',json.dumps({'run_id':a['result']['run_id']}))
                self.assertEqual(b['budget_after']['spent'],6)
                self.assertEqual(b['result']['numerical_settings']['dt'],study()['run']['config']['dt']/4)
                same=ep.execute('b','refine_integration',json.dumps({'run_id':a['result']['run_id']}))
                self.assertEqual(same['budget_after']['spent'],6)
                saved=ep.checkpoint()
                with patch.object(Backend,'get',side_effect=AssertionError('restore ran solver')):
                    restored=IncrementalAgentEpisode.restore(IncrementalConfig(),IncrementalInstance(study()),None,None,saved)
                self.assertEqual(restored.environment.remaining,2)
            finally:
                log.close()

    def test_real_saved_catalog_is_matched_and_complete(self):
        if not CATALOG.exists():
            self.skipTest('local raw CPU pilot is intentionally untracked')
        studies,comparisons,source=read_catalog(CATALOG)
        self.assertEqual(len(studies),35)
        self.assertEqual(len(source['omitted_slots']),1)
        self.assertTrue(all(s['private']['cohort']=='fresh' for s in studies))
        self.assertTrue(all(len(v)==4 for v in comparisons.values()))
        self.assertTrue(all(v['fixed_IIS']['evaluation']['correct'] for v in comparisons.values()))


class RunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_case_campaign_no_credentials_and_offline_render(self):
        data=fixture()
        with tempfile.TemporaryDirectory() as folder:
            with patch('budgeted_science.agents.verification_incremental_catalog.read_catalog',return_value=data), \
                 patch('budgeted_science.agents.runner.load_api_key',side_effect=AssertionError('credential access')):
                path=await run_catalog('fixture',folder,mode='dry-run')
            summary=render(path)
            self.assertEqual(summary['overall']['attempts'],2)
            self.assertEqual(summary['overall']['audit_credits'],10)
            self.assertEqual(len(list((path/'slots').glob('*.json'))),2)
            original=(path/'report.md').read_bytes()
            with patch.object(Backend,'get',side_effect=AssertionError('render ran solver')):
                self.assertEqual(render(path),summary)
            self.assertEqual(original,(path/'report.md').read_bytes())
            for p in Path(folder).glob('*-dry-run-*/evaluation.json'):
                report=(p.parent/'report.md').read_text()
                self.assertIn('Scientific budget: 8',report)
                self.assertNotIn('Fixed two-check verifier',report)

    async def test_failed_stream_not_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('budgeted_science.agents.verification_incremental_catalog.read_catalog',return_value=fixture()):
                path=await run_catalog('fixture',folder,mode='dry-run',
                    gateway_factory=lambda i:VerificationGateway(fail_turn=1) if i==0 else VerificationGateway())
            summary=render(path)['overall']
            self.assertEqual((summary['attempts'],summary['incomplete']),(2,1))
            self.assertGreater(float(summary['uncertain_reserved_usd']),0)
            self.assertEqual(len(list((path/'slots').glob('*.json'))),2)

    async def test_explicit_resume_preserves_eight_credit_contract_and_money(self):
        cases,comparisons,source=fixture()
        instance=IncrementalInstance(cases[0],comparison=comparisons[cases[0]['case_id']]['fixed_IIS'])
        with tempfile.TemporaryDirectory() as folder:
            parent,reason=await run_episode(ROOT,folder,mode='dry-run',config=IncrementalConfig(),instance=instance,
                adapter=IncrementalAdapter(),gateway=VerificationGateway(fail_turn=2))
            self.assertEqual(reason,'request_or_runner_error')
            with patch.object(Backend,'get',side_effect=AssertionError('prepare resume ran solver')):
                saved=prepare_resume(parent,'dry-run')
            self.assertEqual(sum(e['charge'] for e in saved['saved']['environment']['ledger']),3)
            child,reason=await run_episode(ROOT,folder,mode='dry-run',config=saved['config'],instance=saved['instance'],
                adapter=IncrementalAdapter(),gateway=VerificationGateway(),resume=saved)
            self.assertEqual(reason,'submitted')
            result=json.loads((child/'evaluation.json').read_text())
            self.assertEqual(result['evaluation']['scientific_status']['remaining'],3)
            self.assertGreater(float(result['api_budget']['uncertain_reserved_usd']),0)
            self.assertEqual(json.loads((child/'manifest.json').read_text())['public_configuration']['scientific_budget'],8)
            with self.assertRaises(ValueError):
                prepare_resume(parent,'dry-run')

    async def test_live_gateway_override_rejected(self):
        with self.assertRaises(ValueError):
            await run_catalog('unused','unused',mode='live',gateway_factory=lambda i:VerificationGateway())


if __name__=='__main__':
    unittest.main()
