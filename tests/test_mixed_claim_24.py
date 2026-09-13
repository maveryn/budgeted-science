"""Only the scientific cap changes in the Luna 24-credit condition."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from budgeted_science.agents import mixed_claim_audit as a
from budgeted_science.agents.records import RunLog


class Budget24Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.study = a.build_study()

    def test_configuration_and_exact_cap(self):
        cfg = a.Config(scientific_budget=24)
        self.assertEqual((cfg.model, cfg.reasoning_effort, cfg.api_ceiling_usd), ('gpt-5.6-luna','high','1.00'))
        with self.assertRaises(ValueError): a.Config(model='gpt-5.6-sol',scientific_budget=24)
        self.assertEqual(a.Config().scientific_budget,32)
        with tempfile.TemporaryDirectory() as root:
            log = RunLog(root,'test')
            try:
                ep = a.Episode(cfg,a.Instance(self.study),log)
                for i,theta in enumerate(([1,.08,1.4],[1,.088,1.4],[1,.10,1.4])):
                    self.assertEqual(ep.execute(str(i),'simulate_high',json.dumps({'theta':theta}))['status'],'success')
                result = ep.execute('over','simulate_low',json.dumps({'theta':[.9,.08,1.4]}))
                self.assertEqual(result['status'],'unaffordable')
                self.assertEqual(result['budget_after']['spent'],24)
                repeat = ep.execute('repeat','simulate_high',json.dumps({'theta':[1,.08,1.4]}))
                self.assertEqual(repeat['charge'],0)
                submit = ep.execute('final','submit',json.dumps({'verdicts':{f'C{i}':'ABSTAIN' for i in range(1,7)},
                    'evidence_ids':['simulation-1'], 'explanation':'Offline fixture.'}))
                self.assertEqual(submit['status'],'submitted')
            finally: log.close()

    def test_same_study_observations_and_tools(self):
        views, prompts = [], []
        with tempfile.TemporaryDirectory() as root:
            for budget in (24,32):
                log=RunLog(root,'test')
                try:
                    cfg=a.Config(scientific_budget=budget)
                    ep=a.Episode(cfg,a.Instance(self.study),log)
                    views.append(ep.environment.evidence())
                    prompts.append(a.prompts(cfg,ep))
                finally: log.close()
        # Accounting fields differ, observation values and all study facts do not.
        views[0]['study']['environment']['budget']=32.0
        for record in views[0]['observations']: record['remaining']=32.0
        self.assertEqual(views[0],views[1])
        normalized = prompts[0][1]['content'].replace('within 24 shared','within 32 shared')
        normalized = normalized.replace('"budget": 24.0','"budget": 32.0').replace('"remaining": 24.0','"remaining": 32.0')
        self.assertEqual(normalized,prompts[1][1]['content'])
        self.assertEqual(a.tool_definitions(a.Config(scientific_budget=24)),a.tool_definitions(a.Config()))

    def test_fixed_control_and_frozen_offline_run(self):
        with tempfile.TemporaryDirectory() as root, patch.object(a,'build_study',return_value=deepcopy(self.study)):
            prepared=a.prepare(root,a.Config(scientific_budget=24))
            payload,manifest=a.load_prepared(prepared)
            self.assertEqual(payload['study']['public']['environment']['budget'],24)
            self.assertEqual(payload['study']['private'],self.study['private'])
            cpu=payload['comparisons']
            self.assertEqual((cpu['correct'],cpu['wrong'],cpu['abstained']),(3,0,3))
            self.assertEqual(cpu['scientific_status']['spent'],20)
            with patch('budgeted_science.agents.runner.load_api_key',side_effect=AssertionError('no credential access')):
                run=asyncio.run(a.run(prepared,'dry-run',root))
            result=a.read_json(run/'evaluation.json')
            self.assertEqual(result['termination_reason'],'submitted')
            self.assertIn('24 scientific credits',(run/'report.md').read_text())
            before=(run/'transcript.md').read_bytes()
            a.regenerate(run)
            self.assertEqual(before,(run/'transcript.md').read_bytes())


if __name__=='__main__':
    unittest.main()
