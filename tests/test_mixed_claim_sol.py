"""Sol support changes only model selection, pricing and report labeling."""
import asyncio
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from budgeted_science.agents import mixed_claim_audit as a
from budgeted_science.agents.records import RunLog
from budgeted_science.agents.spending import ApiBudget, ApiLimit


class MixedSolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.study = a.build_study()

    def test_exact_model_budget_and_original_default(self):
        self.assertEqual(a.Config().model, 'gpt-5.6-luna')
        sol = a.Config(model='gpt-5.6-sol')
        self.assertEqual((sol.reasoning_effort, sol.scientific_budget, sol.api_ceiling_usd), ('high',32,'1.00'))
        with self.assertRaises(ValueError): a.Config(model='gpt-5.6-sol',scientific_budget=52)
        with self.assertRaises(ValueError): a.prepare(config=a.Config(scientific_budget=52))
        ledger=ApiBudget('1.00',model='gpt-5.6-sol')
        ledger.reserve('one',10000,32768)
        self.assertEqual(str(ledger.status()['committed_upper_usd']),'0.70536')
        with self.assertRaises(ApiLimit): ledger.reserve('two',10000,32768)

    def test_identical_scientific_prompts_schemas_and_historical_study(self):
        historical = a.ROOT/'demos/mixed_claim_audit/runs/20260913T023121Z-mixed-prepared-4df55c3128'
        with tempfile.TemporaryDirectory() as root:
            prompts=[]
            for model in ('gpt-5.6-luna','gpt-5.6-sol'):
                log=RunLog(root,'test')
                try:
                    cfg=a.Config(model=model)
                    ep=a.Episode(cfg,a.Instance(self.study),log)
                    prompts.append(a.prompts(cfg,ep))
                finally: log.close()
            self.assertEqual(prompts[0],prompts[1])
            self.assertEqual(a.tool_definitions(a.Config()),a.tool_definitions(a.Config(model='gpt-5.6-sol')))
            if historical.exists():
                self.assertEqual(prompts[1],a.read_json(historical/'prompts.json'))
                self.assertEqual(self.study,a.read_json(historical/'payload.json')['study'])

    def test_sol_frozen_fake_run_and_offline_render(self):
        with tempfile.TemporaryDirectory() as root, patch.object(a,'build_study',return_value=deepcopy(self.study)), \
             patch('budgeted_science.agents.runner.load_api_key',side_effect=AssertionError('no credentials')):
            prepared=a.prepare(root,a.Config(model='gpt-5.6-sol'))
            payload,manifest=a.load_prepared(prepared)
            self.assertEqual(manifest['configuration']['model'],'gpt-5.6-sol')
            self.assertEqual(payload['comparisons']['correct'],4)
            path=asyncio.run(a.run(prepared,'dry-run',root))
            body=a.read_json(path/'api/generation-001-request.json')
            self.assertEqual(body['model'],'gpt-5.6-sol')
            self.assertEqual(body['reasoning']['effort'],'high')
            result=a.read_json(path/'evaluation.json')
            self.assertEqual(result['termination_reason'],'submitted')
            before=(path/'report.md').read_bytes()
            a.regenerate(path)
            self.assertEqual(before,(path/'report.md').read_bytes())

    def test_live_sol_label_without_network(self):
        with tempfile.TemporaryDirectory() as root, patch.object(a,'build_study',return_value=deepcopy(self.study)):
            prepared=a.prepare(root,a.Config(model='gpt-5.6-sol'))
            path=asyncio.run(a.run(prepared,'live',root,gateway=a.SolFake()))
            report=(path/'report.md').read_text(encoding='utf-8')
            self.assertIn('| Sol/high |',report)
            self.assertNotIn('| Luna/high |',report)
            with self.assertRaises(FileExistsError):
                asyncio.run(a.run(prepared,'live',root,gateway=a.SolFake()))

    def test_exaggerated_offline_usage_still_enforces_cap(self):
        with tempfile.TemporaryDirectory() as root, patch.object(a,'build_study',return_value=deepcopy(self.study)):
            prepared=a.prepare(root,a.Config(model='gpt-5.6-sol'))
            path=asyncio.run(a.run(prepared,'dry-run',root,gateway=a.legacy.Fake()))
            self.assertEqual(a.read_json(path/'evaluation.json')['termination_reason'],'api_ceiling')


if __name__=='__main__':
    unittest.main()
