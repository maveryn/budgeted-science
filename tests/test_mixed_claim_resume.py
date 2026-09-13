"""Continuation uses prior evidence and ledgers; fixtures never contact APIs."""
import asyncio
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from budgeted_science.agents import mixed_claim_audit as a
from budgeted_science.agents import mixed_claim_resume as r
from budgeted_science.agents.records import RunLog, digest
from budgeted_science.agents.runner import StopEpisode


class Actions(a.SolFake):
    def __init__(self, actions, prefix):
        super().__init__()
        self.actions, self.prefix, self.index = actions, prefix, 0

    async def count(self, body, metadata):
        if self.index >= len(self.actions):
            raise StopEpisode('offline_pause')
        return await super().count(body, metadata)

    async def stream(self, body, metadata):
        self.requests.append(deepcopy(body))
        name, args = self.actions[self.index]
        self.index += 1
        ident = f'{self.prefix}-{self.index}'
        yield {'type': 'response.completed', 'response': {
            'status': 'completed', 'id': ident, 'model': body['model'], 'service_tier': 'default',
            'output': [{'type': 'reasoning', 'id': 'r-'+ident, 'summary': [], 'encrypted_content': 'opaque'},
                       {'type': 'function_call', 'call_id': ident, 'name': name, 'arguments': json.dumps(args)}],
            'usage': {'input_tokens': self.input_tokens, 'output_tokens': 100,
                      'input_tokens_details': {'cached_tokens': 0}, 'output_tokens_details': {'reasoning_tokens': 20}}}}


class ResumeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.study = a.build_study()

    def parent(self, root, legacy=False):
        config = a.Config(model='gpt-5.6-sol')
        compare = a.run_cpu(self.study, Path(root)/'cpu', config)
        actions = [('simulate_high', {'theta': [1,.08,1.4]}), ('measure_target', {'variable': 'x', 'time': 4.5})]
        runner = a.run_episode(a.ROOT, root, mode='dry-run', config=config,
            instance=a.Instance(self.study, compare), adapter=a.Adapter, gateway=Actions(actions,'initial'))
        if legacy:
            with patch.object(a.Episode, 'checkpoint', a.legacy.Episode.checkpoint):
                path, reason = asyncio.run(runner)
        else:
            path, reason = asyncio.run(runner)
        self.assertEqual(reason, 'offline_pause')
        return path

    def test_full_offline_continuation_and_no_duplicate_child(self):
        with tempfile.TemporaryDirectory() as root:
            parent = self.parent(root)
            original = {p.name: p.read_bytes() for p in parent.iterdir() if p.is_file()}
            prepared = r.prepare_resume(parent, mode='dry-run', api_ceiling_usd='1.50')
            money_before = Decimal(prepared['money'].status()['known_cost_upper_usd'])
            # A duplicated earlier ID must not repurchase the high simulation.
            gateway = Actions([('simulate_high', {'theta':[1,.08,1.4]}),
                ('submit', {'verdicts':{f'C{i}':'ABSTAIN' for i in range(1,7)},
                            'evidence_ids':['simulation-1','observation-5'], 'explanation':'Offline fixture.'})], 'initial')
            # The second call must be unique (not the old measurement ID).
            original_stream = gateway.stream
            async def stream(body, metadata):
                if gateway.index == 1:
                    gateway.prefix = 'continuation'
                async for event in original_stream(body, metadata):
                    yield event
            gateway.stream = stream
            with patch('budgeted_science.resource_planning.environment._solve_high', side_effect=AssertionError('unpaid solve')), \
                 patch('budgeted_science.resource_planning.environment._solve_low', side_effect=AssertionError('unpaid solve')), \
                 patch('budgeted_science.agents.runner.load_api_key', side_effect=AssertionError('credential read')):
                child = asyncio.run(r.run(parent, mode='dry-run', api_ceiling_usd='1.50', root=root, gateway=gateway))
            result = a.read_json(child/'evaluation.json')
            self.assertEqual(result['termination_reason'],'submitted')
            self.assertEqual(result['evaluation']['scientific_status']['spent'],20)
            self.assertEqual(result['evaluation']['abstained'],6)
            self.assertEqual(result['model_responses'],4)
            self.assertGreater(Decimal(result['api_budget']['known_cost_upper_usd']),money_before)
            self.assertEqual(result['api_budget']['ceiling_usd'],'1.50')
            self.assertEqual(gateway.requests[0]['input'], prepared['history'])
            self.assertEqual(gateway.requests[0]['reasoning']['effort'],'high')
            self.assertEqual(gateway.requests[0]['max_output_tokens'],32768)
            for name, data in original.items():
                self.assertEqual((parent/name).read_bytes(),data)
            self.assertTrue((child/'public/study.json').is_file())
            before=(child/'transcript.md').read_bytes()
            a.regenerate(child)
            self.assertEqual(before,(child/'transcript.md').read_bytes())
            with self.assertRaises(ValueError): r.prepare_resume(parent,mode='dry-run')
            with self.assertRaises(ValueError): r.prepare_resume(child,mode='dry-run')

    def test_legacy_migration_no_solver_and_cached_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            parent=self.parent(root,legacy=True)
            with patch('budgeted_science.resource_planning.environment._solve_high',side_effect=AssertionError('solver')):
                resumed=r.prepare_resume(parent,mode='dry-run',api_ceiling_usd='1.50')
                log=RunLog(root,'restore')
                try:
                    ep=r.restore(resumed['config'],resumed['instance'],log,None,resumed['saved'])
                    self.assertEqual(ep.environment.status()['remaining'],12)
                    result=ep.execute('new-free-repeat','measure_target',json.dumps({'variable':'x','time':4.5}))
                    self.assertEqual(result['charge'],0)
                    self.assertEqual(result['record_id'],'observation-5')
                    self.assertEqual(ep.request_count,3)
                    self.assertEqual(ep.artifact_number,1)
                finally: log.close()

    def test_unsafe_configuration_and_mode_rejected(self):
        for kwargs in ({'api_ceiling_usd':'2'}, {'scientific_budget':52}, {'model':'gpt-5.6-luna'},
                       {'reasoning_effort':'medium'}, {'max_responses':31}):
            with self.assertRaises(ValueError): r.ResumeConfig(model='gpt-5.6-sol',**{k:v for k,v in kwargs.items() if k!='model'}) if 'model' not in kwargs else r.ResumeConfig(**kwargs)
        with self.assertRaises(ValueError): a.Config(model='gpt-5.6-sol',api_ceiling_usd='1.50')
        with tempfile.TemporaryDirectory() as root:
            parent=self.parent(root)
            with self.assertRaises(ValueError): r.prepare_resume(parent,mode='live')

    def test_bad_checkpoint_pending_tools_and_limits_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            parent=self.parent(root)
            cp=a.read_json(parent/'checkpoint.json')
            original=r.read_json
            for change in ('hash','pending','limit'):
                altered=deepcopy(cp)
                if change=='hash': altered['payload_hash']='bad'
                if change=='pending': altered['last_sequence']=0
                if change=='limit':
                    altered['payload']['request_count']=60
                    altered['payload_hash']=digest(altered['payload'])
                def read(p, rel):
                    return altered if str(rel)=='checkpoint.json' else original(p,rel)
                with patch.object(r,'read_json',side_effect=read), self.assertRaises(ValueError):
                    r.prepare_resume(parent,mode='dry-run')

    def test_real_parent_read_only_when_available(self):
        parent=a.RUNS/'20260913T024618Z-live-7c755f7e8c'
        if not parent.exists() or (parent/'resume_claim.json').exists():
            self.skipTest('optional historical unresumed parent not available')
        with patch('budgeted_science.resource_planning.environment._solve_high',side_effect=AssertionError('solver')):
            data=r.prepare_resume(parent,mode='live',api_ceiling_usd='1.50')
        self.assertEqual(data['responses'],7)
        self.assertEqual(data['saved']['request_count'],7)
        self.assertEqual(sum(x['charge'] for x in data['saved']['environment']['ledger']),31)
        self.assertEqual(data['money'].status()['known_cost_upper_usd'],'0.346635')
        self.assertEqual(data['next_generation'],9)


if __name__=='__main__':
    unittest.main()
