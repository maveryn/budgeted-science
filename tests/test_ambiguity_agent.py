"""Offline adapter tests; synthetic cases, no credentials or API calls."""
import asyncio
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from budgeted_science.agents import ambiguity_agent as agent
from budgeted_science.agents.records import RunLog, digest, read_events
from budgeted_science.agents.runner import run_episode, StopEpisode
from budgeted_science.agents.transport_verification import TransportInstance
from budgeted_science.verification_diagnostics import ambiguity as science


def fixture():
    spec = [[.5, 0]]
    original = {s: science.solve(62, s, spec) for s in ("calibration", "forecast")}
    q = original["forecast"]["q"]
    public = {"candidates": deepcopy(science.GRID), "nominal_candidate": 62, "spec": spec,
        "data": original["calibration"]["measurements"], "error_bounds": [.1], "claim_interval": [.97*q, 1.03*q]}
    bank = {str(i): {"sparse": [999.], "q": 999.} for i in range(125)}
    for i in (0, 27, 62):
        bank[str(i)] = {"sparse": science.solve(i, "calibration", spec)["measurements"],
                        "q": science.solve(i, "forecast", spec)["q"]}
    return {"id": "synthetic-case", "public": public, "original": original,
        "private": {"regime": "sparse", "valid": False, "outside": [27], "feasible": [27, 62], "bank": bank}}


def comparisons(case, budget):
    e = science.Audit(case, budget).evaluate()
    e.update(verdict="ABSTAIN", incomplete=False, abstained=True)
    return {p: {"case_id": case["id"], "budget": budget, "policy": p,
                "evaluation": deepcopy(e), "failure": None} for p in science.POLICIES}


class AmbiguityAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case = fixture()

    def instance(self, budget=32):
        return TransportInstance(deepcopy(self.case), comparisons(self.case, budget))

    def make_episode(self, root, budget=32):
        log = RunLog(root, "test")
        self.addCleanup(log.close)
        return agent.AmbiguityEpisode(agent.AmbiguityConfig(scientific_budget=budget), self.instance(budget), log)

    def test_config_and_schemas(self):
        cfg = agent.AmbiguityConfig()
        for change in ({"model": "gpt-5.6-sol"}, {"scientific_budget": 33}, {"api_ceiling_usd": "3"}, {"reasoning_effort": "low"}):
            with self.assertRaises(ValueError):
                replace(cfg, **change)
        for t in agent.tool_definitions():
            self.assertTrue(t["strict"])
            self.assertEqual(set(t["parameters"]["required"]), set(t["parameters"]["properties"]))

    def test_public_prompt_no_private_bank(self):
        with tempfile.TemporaryDirectory() as root:
            ep = self.make_episode(root)
            text = json.dumps(agent.prompts(ep.config, ep))
            for key in ('"bank"', '"outside"', '"feasible"', '"private"', '"regime"', 'screened'):
                self.assertNotIn(key, text)
            self.assertIn("125", text)
            with patch.object(science, "solve", side_effect=AssertionError("unpaid solve")):
                self.assertTrue(ep.execute("d", "describe", "{}")['ok'])
                self.assertTrue(ep.execute("b", "budget", "{}")['ok'])
            ep.log.close()

    def test_batch_matches_single_and_duplicate_is_free(self):
        with tempfile.TemporaryDirectory() as root:
            ep = self.make_episode(root)
            args = {"checks": [{"candidate": 27, "stage": s} for s in ("calibration", "forecast")]}
            result = ep.execute("batch", "check_batch", json.dumps(args))
            spent = ep.environment.spent
            other = science.Audit(self.case, 32)
            for i, check in enumerate(args["checks"]):
                expected = other.call("check", check)
                self.assertEqual(result['result']['checks'][i]['run']['q'], expected['run']['q'])
            self.assertEqual(spent, other.spent)
            ep.execute("batch", "check_batch", json.dumps(args))
            self.assertEqual(ep.environment.spent, spent)
            self.assertFalse(ep.execute("batch", "budget", "{}")['ok'])
            for r in result['result']['checks']:
                self.assertNotIn('values', r['run'])
                full = ep.execute('record-'+r['id'], 'record', json.dumps({'id':r['id']}))
                self.assertEqual(full['result']['record']['q'], r['run']['q'])
            self.assertEqual(ep.environment.spent, spent)
            ep.log.write_json('checkpoint-test.json', ep.checkpoint())
            ep.log.close()

    def test_all_batch_arguments_validated_before_purchase(self):
        with tempfile.TemporaryDirectory() as root:
            ep = self.make_episode(root)
            for checks in ([], [{"candidate": 0, "stage": "calibration"}]*17,
                           [{"candidate": 0, "stage": "calibration"}, {"candidate": 125, "stage": "forecast"}]):
                self.assertFalse(ep.execute(str(checks), "check_batch", json.dumps({"checks": checks}))['ok'])
            self.assertEqual(ep.environment.spent, 0)
            self.assertFalse(ep.execute('nan', 'check', '{"candidate":NaN,"stage":"forecast"}')['ok'])
            ep.log.close()

    def test_partial_batch_charging_and_free_submission(self):
        with tempfile.TemporaryDirectory() as root:
            ep = self.make_episode(root)
            ep.environment.limit = 3  # Synthetic work-cap fixture, not production configuration.
            r = ep.execute('b', 'check_batch', json.dumps({'checks':[
                {'candidate':0, 'stage':'forecast'}, {'candidate':1, 'stage':'forecast'}]}))
            self.assertEqual(ep.environment.spent, 3)
            self.assertEqual(r['result']['not_executed'], 1)
            self.assertEqual(r['result']['checks'][0]['run']['status'], 'budget_exhausted')
            self.assertTrue(ep.execute('s','submit',json.dumps({'verdict':'ABSTAIN','witness':-1,'justification':'no budget'}))['ok'])
            self.assertTrue(ep.evaluate()['abstained'])
            self.assertFalse(ep.evaluate()['incomplete'])
            ep.log.write_json('checkpoint-test.json', ep.checkpoint())
            ep.log.close()

    def test_witness_and_unsupported_verdict(self):
        with tempfile.TemporaryDirectory() as root:
            ep = self.make_episode(root)
            ep.execute('b','check_batch',json.dumps({'checks':[{'candidate':27,'stage':s} for s in ('calibration','forecast')]}))
            ep.execute('s','submit',json.dumps({'verdict':'REJECT','witness':27,'justification':'counterexample'}))
            self.assertTrue(ep.evaluate()['evidence_backed_correct'])
            other = self.make_episode(root)
            other.execute('s','submit',json.dumps({'verdict':'REJECT','witness':27,'justification':'guess'}))
            self.assertTrue(other.evaluate()['correct'])
            self.assertFalse(other.evaluate()['evidence_backed_correct'])
            ep.log.close()
            other.log.close()

    def test_deadline_and_tool_limit(self):
        with tempfile.TemporaryDirectory() as root:
            ep = self.make_episode(root)
            ep.deadline = time.monotonic()-1
            with self.assertRaises(StopEpisode): ep.execute('d','budget','{}')
            ep.deadline = None
            ep.request_count = 30
            with self.assertRaises(StopEpisode): ep.execute('d','budget','{}')
            self.assertEqual(ep.environment.spent, 0)
            ep.log.close()

    def test_logged_dry_episode_and_regeneration(self):
        with tempfile.TemporaryDirectory() as root, patch('budgeted_science.agents.runner.load_api_key', side_effect=AssertionError('key')):
            gateway = agent.AmbiguityGateway()
            path, reason = asyncio.run(run_episode(science.ROOT, Path(root), mode='dry-run', config=agent.AmbiguityConfig(), instance=self.instance(), adapter=agent.AmbiguityAdapter(), gateway=gateway))
            self.assertEqual(reason, 'submitted')
            self.assertTrue(any(i.get('encrypted_content') == 'opaque-fixture' for i in gateway.requests[1]['input']))
            before = (path/'transcript.md').read_bytes()
            with patch.object(science,'solve',side_effect=AssertionError('offline solve')):
                agent.regenerate(path)
            self.assertEqual(before,(path/'transcript.md').read_bytes())
            events, torn = read_events(path)
            self.assertFalse(torn)
            self.assertEqual(sum(e['kind']=='api_response' for e in events),2)
            self.assertEqual(sum(e['kind']=='environment_event' and e['event_kind']=='solver_finished' for e in events),2)

    def test_interrupted_stream_retains_reservation_and_event(self):
        class Broken(agent.AmbiguityGateway):
            async def stream(self,body,metadata):
                yield {'type':'response.created','response':{'id':'interrupted-fixture'}}
                raise OSError('synthetic interruption')
        with tempfile.TemporaryDirectory() as root:
            path, _ = asyncio.run(run_episode(science.ROOT,Path(root),mode='dry-run',config=agent.AmbiguityConfig(),instance=self.instance(),adapter=agent.AmbiguityAdapter(),gateway=Broken()))
            result=json.loads((path/'evaluation.json').read_text())
            self.assertTrue(result['evaluation']['incomplete'])
            self.assertGreater(float(result['api_budget']['uncertain_reserved_usd']),0)
            self.assertIn('interrupted-fixture',(path/'transcript.md').read_text())

    def test_offline_campaign_four_unique_slots(self):
        cases = [deepcopy(self.case),deepcopy(self.case)]
        cases[1]['id'] = 'second-synthetic'
        comps = {f"{c['id']}:{b}":comparisons(c,b) for c in cases for b in science.BUDGETS}
        with tempfile.TemporaryDirectory() as root, patch.object(agent,'read_catalog',return_value=(cases,comps,{})), patch('budgeted_science.agents.runner.load_api_key',side_effect=AssertionError('key')):
            path=asyncio.run(agent.run_catalog('fixture',Path(root),mode='dry-run'))
            before=(path/'report.md').read_bytes()
            with patch.object(science,'solve',side_effect=AssertionError('offline solve')), patch.object(agent,'run_episode',side_effect=AssertionError('API')):
                result=agent.render(path)
            self.assertEqual(result['attempted'],4)
            self.assertEqual(result['abstained'],4)
            self.assertEqual(result['unfinalized_attempts'],0)
            self.assertLess(float(result['batch_budget']['committed_upper_usd']),2)
            self.assertEqual(before,(path/'report.md').read_bytes())

    def test_live_gateway_override_refused(self):
        with self.assertRaises(ValueError):
            asyncio.run(agent.run_catalog('unused',mode='live',gateway_factory=lambda i:agent.AmbiguityGateway()))

    def test_catalog_integrity_and_comparison_completeness(self):
        cases = [deepcopy(self.case),deepcopy(self.case)]
        cases[1]['id'] = 'second-synthetic'
        with tempfile.TemporaryDirectory() as root:
            log=RunLog(root,'catalog-fixture')
            log.write_json('catalog.json',cases)
            log.write_json('manifest.json',{'version':science.VERSION,'sources':science.source_hashes(),
                'catalog_hash':digest(cases),'budgets':list(science.BUDGETS),'policies':list(science.POLICIES),'cases':[c['id'] for c in cases]})
            for c in cases:
                for b in science.BUDGETS:
                    for p,r in comparisons(c,b).items():
                        log.write_json(f"episodes/{c['id']}-{b}-{p}/result.json",r)
            log.close()
            loaded, comps, source=agent.read_catalog(log.path)
            self.assertEqual(loaded,cases)
            self.assertEqual(len(comps),4)
            self.assertEqual(len(source['file_hashes']),14)
            manifest=json.loads((log.path/'manifest.json').read_text())
            manifest['catalog_hash']='tampered'
            (log.path/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaises(ValueError): agent.read_catalog(log.path)


if __name__ == '__main__': unittest.main()
