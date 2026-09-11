"""Terra selection, accounting, matched campaign and continuation: offline only."""

import asyncio
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from budgeted_science.agents import campaign as c
from budgeted_science.agents import terra_campaign as t
from budgeted_science.agents.records import RunLog, read_events
from budgeted_science.agents.resource import ResourceEpisode, ResourceAdapter, tool_definitions
from budgeted_science.agents.resource_fake import ResourceScriptedGateway
from budgeted_science.agents.resume import prepare_resume
from budgeted_science.agents.runner import run_episode
from budgeted_science.agents.spending import ApiBudget, ApiLimit, AccountingUnavailable, pricing_for_model


class TerraTests(unittest.TestCase):
    def test_explicit_model_and_unchanged_limits(self):
        config=c.configuration(t.MODEL)
        self.assertEqual(config.model,'gpt-5.6-terra')
        self.assertEqual((config.reasoning_effort,config.scientific_budget,config.api_ceiling_usd),('high',32,'3.00'))
        self.assertEqual((config.max_responses,config.max_output_tokens,config.deadline_seconds),(30,32768,1200))
        self.assertEqual(tool_definitions(config),tool_definitions(c.configuration()))

    def test_terra_pricing_and_reservations(self):
        ledger=ApiBudget('3.00',model=t.MODEL)
        self.assertEqual(ledger.reserve('a',1000,1000),Decimal('.0145'))
        ledger.settle('a',{'input_tokens':1000,'output_tokens':100,
                          'input_tokens_details':{'cached_tokens':200},'output_tokens_details':{'reasoning_tokens':80}})
        self.assertEqual(ledger.known_upper,Decimal('.0037'))
        self.assertEqual(Decimal(ledger.measured[0]['standard_cost_lower_usd']),Decimal('.00284'))
        self.assertEqual(pricing_for_model(t.MODEL)['input_upper_per_million_usd'],'2.50')
        self.assertEqual(pricing_for_model(t.MODEL)['output_per_million_usd'],'12.00')
        with self.assertRaises(ApiLimit): ledger.reserve('long',256001,1)
        with self.assertRaises(ApiLimit): ApiBudget('.001',model=t.MODEL).reserve('a',1000,32768)

    def test_unknown_usage_preserved_model_cannot_change(self):
        ledger=ApiBudget('3.00',model=t.MODEL)
        ledger.reserve('a',2000,32768)
        with self.assertRaises(AccountingUnavailable): ledger.settle('a',None)
        spec={'a':{'input_tokens':2000,'max_output_tokens':32768}}
        self.assertEqual(ApiBudget.restore(ledger.status(),spec,model=t.MODEL).status(),ledger.status())
        with self.assertRaises(AccountingUnavailable): ApiBudget.restore(ledger.status(),spec,model=c.MODELS[0])
        self.assertEqual(t.spending({str(i):{'status':'started'} for i in range(5)}),Decimal(15))

    def test_prompt_guard_and_no_comparison_execution(self):
        instance=c.ResourceInstance.from_seed(5000)
        with tempfile.TemporaryDirectory() as temp:
            log=RunLog(temp,'test')
            try:
                episode=ResourceEpisode(c.configuration(t.MODEL),instance,log)
                expected=t.scientific_prompts(c.configuration(),episode)
                adapter=t.TerraAdapter(instance,{},expected)
                self.assertEqual(adapter.prompts(c.configuration(t.MODEL),episode),expected)
                adapter.expected_prompt=[]
                with self.assertRaises(ValueError): adapter.prompts(c.configuration(t.MODEL),episode)
            finally: log.close()

    def test_terra_interruption_and_explicit_resume_state(self):
        class Interrupted(ResourceScriptedGateway):
            async def stream(self,body,metadata):
                if self.requests:
                    yield {'type':'response.output_text.delta','delta':'offline Terra fixture'}
                    raise ConnectionError('synthetic stream failure')
                async for event in super().stream(body,metadata): yield event
        with tempfile.TemporaryDirectory() as temp, patch.object(ResourceAdapter,'run_comparisons',return_value={}):
            instance=c.ResourceInstance.from_seed(5000)
            path,reason=asyncio.run(run_episode(c.REPO,temp,mode='dry-run',config=c.configuration(t.MODEL),
                instance=instance,adapter=ResourceAdapter(),gateway=Interrupted()))
            self.assertEqual(reason,'request_or_runner_error')
            saved=prepare_resume(path,mode='dry-run')
            self.assertEqual(saved['config'].model,t.MODEL)
            self.assertEqual(saved['money'].model,t.MODEL)
            self.assertGreater(saved['money'].reserved,0)
            self.assertEqual(saved['instance'],instance)

    def test_complete_extension_and_safe_continuation(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch('budgeted_science.agents.runner.load_api_key',side_effect=AssertionError('offline only')), \
             patch.object(c,'cpu_episode',side_effect=AssertionError('no new baseline')):
            root=t.prepare(temp,rehearsal=True)
            calls=[]
            def factory(seed):
                calls.append(seed)
                return ResourceScriptedGateway(require_full_budget=True)
            summary=asyncio.run(t.execute(root,mode='dry-run',gateway_factory=factory))
            self.assertTrue(summary['complete'])
            self.assertEqual(calls,list(c.SEEDS))
            self.assertEqual(len(summary['rows']),35)
            self.assertEqual(sum(r['method']==t.MODEL for r in summary['rows']),5)
            for slot in c.state(root).values():
                r=slot['result']
                self.assertEqual(r['scientific_status']['spent'],32)
                self.assertEqual(r['api_budget']['model'],t.MODEL)
                report=(Path(r['path'])/'report.md').read_text(encoding='utf-8')
                self.assertIn('Model: gpt-5.6-terra; reasoning: high;',report)
                self.assertIn('SCRIPTED OFFLINE FIXTURE',report)
            before=[(root/p).read_bytes() for p in ('report.md','summary.json','events.jsonl')]
            t.render(root)
            self.assertEqual(before,[(root/p).read_bytes() for p in ('report.md','summary.json','events.jsonl')])
            with patch.object(t,'run_episode',side_effect=AssertionError('duplicate Terra')):
                asyncio.run(t.execute(root,mode='dry-run',continuation=True))
            self.assertEqual(calls,list(c.SEEDS))
            bad=deepcopy(c.provenance(c.REPO)); bad['source_hashes']['changed']='bad'
            with patch.object(t,'provenance',return_value=bad),self.assertRaises(ValueError): t.verify(root)


if __name__=='__main__': unittest.main()
