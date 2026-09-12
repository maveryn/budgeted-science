"""Offline diagnostic and finite-universe ambiguity contracts; no live APIs."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from budgeted_science.agents.records import RunLog,digest,read_events
from budgeted_science.verification_diagnostics import rescore as r,ambiguity as a


def fixture_source(root):
    source=RunLog(root,"source")
    catalog=[]
    for i,(claim,verdict,check) in enumerate(((101.,"ACCEPT",102.),(140.,"REJECT",150.),(101.,"ABSTAIN",None))):
        original={"experiment":"prediction","status":"complete","q":claim,"theta":[1.,.08,1.4],"method":"dop_tight","work":5}
        case={"id":str(i),"public":{"claim":{"value":claim,"tolerance":.03}},"reference":{"q":100.},"prediction":original,"private":{"family":"fixture"}}
        catalog.append(case)
        child=RunLog(source.path/"episodes","test")
        child.write_json("originals.json",{"prediction":original})
        evidence=[]
        if check is not None:
            record={**original,"q":check,"method":"dop_loose"}
            child.write_json("numerical/run-test.json",record)
            child.event("tool_result",name="predict",result={"result_id":"run-test",**record})
            evidence=["run-test"]
        sub={"verdict":verdict,"evidence_ids":evidence,"justification":"fixture"}
        child.event("tool_request",name="submit",arguments=sub)
        child.write_json("result.json",{"case_id":str(i),"budget":4,"policy":"test","path":child.path.relative_to(source.path).as_posix(),
            "submission":sub,"evaluation":{"reference":100.,"valid":claim==101.,"verdict":verdict,
                "correct":verdict in ("ACCEPT","REJECT"),"spent":1.}})
        child.close()
    source.write_json("catalog.json",catalog)
    source.write_json("manifest.json",{"catalog_hash":digest(catalog),"cases":[{"id":c["id"],"hash":digest(c)} for c in catalog],"budgets":[4],"policies":["test"]})
    source.close()
    return source.path


class RescoreTests(unittest.TestCase):
    def test_hand_checked_metrics_and_no_solver(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=fixture_source(tmp)
            before={p:p.read_bytes() for p in source.rglob("*") if p.is_file()}
            with patch.object(a,"solve",side_effect=AssertionError("solver")),patch.object(a.Audit,"call",side_effect=AssertionError("tool")):
                rows,hashes=r.analyze(source)
            m=r.metrics(rows)["4"]["test"]
            self.assertEqual((m["count"],m["verdict_correct"],m["check_available"],m["joint"]),(3,2,2,1))
            self.assertEqual(m["correct_verdict_bad_check"],1)
            self.assertAlmostEqual(m["mean_check_error"],.26)
            self.assertTrue(hashes)
            self.assertTrue(all(p.read_bytes()==b for p,b in before.items()))

    def test_tampered_catalog_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=fixture_source(tmp)
            p=source/"catalog.json"
            rows=json.loads(p.read_text()); rows[0]["reference"]["q"]=200
            p.write_text(json.dumps(rows))
            with self.assertRaisesRegex(ValueError,"catalog provenance"):
                r.analyze(source)

    def test_tampered_forecast_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=fixture_source(tmp)
            p=next(source.glob("episodes/*/numerical/run-test.json"))
            record=json.loads(p.read_text()); record["q"]=999
            p.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError,"forecast artifact"):
                r.analyze(source)

    def test_missing_episode_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=fixture_source(tmp)
            p=source/"manifest.json"
            value=json.loads(p.read_text()); value["policies"].append("missing")
            p.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,"missing episode"):
                r.analyze(source)

    def test_ambiguous_cited_forecasts_not_best_of_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=fixture_source(tmp)
            child=next(p for p in source.glob("episodes/*/result.json") if json.loads(p.read_text())["submission"]["verdict"]!="ABSTAIN")
            value=json.loads(child.read_text())
            if value["submission"]["verdict"]=="ABSTAIN": self.fail("unexpected fixture order")
            # Duplicate citation is also ambiguous; it must not improve the score.
            value["submission"]["evidence_ids"].append("run-test")
            child.write_text(json.dumps(value))
            path=child.parent/"events.jsonl"
            events=[json.loads(x) for x in path.read_text().splitlines()]
            events[-1]["arguments"]=value["submission"]
            path.write_text("\n".join(json.dumps(x) for x in events)+"\n")
            with self.assertRaisesRegex(ValueError,"multiple cited"):
                r.analyze(source)

    def test_offline_rescore_render_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=fixture_source(tmp)
            target=r.run(source,Path(tmp)/"output")
            before=(target/"report.md").read_bytes()
            with patch.object(r,"analyze",side_effect=AssertionError("source reread")):
                r.render(target)
            self.assertEqual(before,(target/"report.md").read_bytes())


class AmbiguityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases=a.commission()
        cls.sparse,cls.rich=cls.cases

    def test_reference_ambiguity_and_matched_nominal(self):
        self.assertEqual(len(a.GRID),125)
        self.assertEqual(self.sparse["public"]["claim_interval"],self.rich["public"]["claim_interval"])
        self.assertEqual(self.sparse["original"]["forecast"]["q"],self.rich["original"]["forecast"]["q"])
        self.assertEqual(len(self.sparse["private"]["feasible"]),4)
        self.assertEqual(len(self.rich["private"]["feasible"]),1)
        self.assertFalse(self.sparse["private"]["valid"])
        self.assertTrue(self.rich["private"]["valid"])
        for c in self.cases: self.assertLess(c["private"]["max_solver_disagreement"],1e-5)

    def test_reference_rejection_has_actual_counterexample(self):
        cid=self.sparse["private"]["outside"][0]
        bank=self.sparse["private"]["bank"][str(cid)]
        self.assertTrue(a.consistent(bank["sparse"],self.sparse["public"]))
        self.assertFalse(a.inside(bank["q"],self.sparse["public"]["claim_interval"]))

    def test_sparse_solver_stops_at_observed_horizon(self):
        s=a.solve(0,"calibration",a.SPECS["sparse"])
        t=a.solve(0,"calibration",a.SPECS["rich"])
        self.assertEqual(s["times"], [.5])
        self.assertEqual(t["times"][-1],4.)
        self.assertLess(s["work"],t["work"])

    def test_catalog_hash_survives_json_and_loaded_case_can_be_scored(self):
        restored=json.loads(json.dumps(self.cases))
        self.assertEqual(digest(self.cases),digest(restored))
        with tempfile.TemporaryDirectory() as tmp:
            log=RunLog(tmp,"catalog")
            log.write_json("catalog.json",self.cases)
            log.close()
            self.assertEqual(digest(self.cases),digest(json.loads((log.path/"catalog.json").read_text())))
        audit=a.Audit(restored[1],0)
        a.policy(audit.call,"nominal_only")
        self.assertTrue(audit.evaluate()["correct"])

    def test_actual_rhs_calls_metered(self):
        with patch.object(a.n,"rhs",wraps=a.n.rhs) as calls:
            result=a.solve(0,"calibration",a.SPECS["sparse"])
        self.assertEqual(calls.call_count,result["work"])

    def test_numerical_interruption_no_fabrication(self):
        result=a.solve(0,"forecast",a.SPECS["sparse"],cap=7)
        self.assertEqual(result["status"],"budget_exhausted")
        self.assertEqual(result["work"],7)
        self.assertIsNone(result["q"])
        self.assertEqual(result["values"],[])

    def test_invalid_requests_uncharged(self):
        audit=a.Audit(self.sparse,32)
        for args in ({"candidate":True,"stage":"forecast"},{"candidate":125,"stage":"forecast"},{"candidate":0,"stage":"reference"}):
            self.assertIn("error",audit.call("check",args))
        self.assertEqual(audit.spent,0)
        with self.assertRaises(ValueError): a.Audit(self.sparse,-1)

    def test_private_data_not_in_public_tools(self):
        audit=a.Audit(self.sparse,32)
        result=audit.call("describe")
        text=json.dumps(result)
        for key in ('"bank"','"feasible"','"outside"','"valid"','"forecast_range"','"private"'):
            self.assertNotIn(key,text)
        result["study"]["data"][0]=999
        self.assertNotEqual(audit.case["public"]["data"][0],999)

    def test_original_record_is_free(self):
        audit=a.Audit(self.sparse,0)
        out=audit.call("check",{"candidate":a.NOMINAL,"stage":"forecast"})
        self.assertEqual(out["charged_work"],0)
        self.assertTrue(out["reuse"])

    def test_dedup_cache_and_independent_ledgers(self):
        first,second=a.Audit(self.sparse,32),a.Audit(self.sparse,32)
        args={"candidate":0,"stage":"calibration"}
        out=first.call("check",args,"once")
        self.assertEqual(first.call("check",args,"once"),out)
        spent=first.spent
        self.assertEqual(first.call("check",args)["charged_work"],0)
        self.assertEqual(second.call("check",args)["charged_work"],spent)
        with self.assertRaises(ValueError): first.call("describe",{},"once")

    def test_failed_solve_charged_and_reused(self):
        audit=a.Audit(self.sparse,32)
        failed={"candidate":0,"stage":"calibration","status":"failed","work":11,"q":None,"measurements":None}
        with patch.object(a,"solve",return_value=failed):
            audit.call("check",{"candidate":0,"stage":"calibration"})
            out=audit.call("check",{"candidate":0,"stage":"calibration"})
        self.assertEqual(audit.spent,11)
        self.assertTrue(out["reuse"])

    def test_unaccounted_failure_retains_reservation(self):
        audit=a.Audit(self.sparse,1)
        with patch.object(a,"solve",side_effect=RuntimeError("synthetic")):
            with self.assertRaises(RuntimeError): audit.call("check",{"candidate":0,"stage":"forecast"})
        self.assertEqual(audit.spent,256)
        self.assertTrue(audit.closed)

    def test_exhausted_budget_allows_submit(self):
        audit=a.Audit(self.sparse,1)
        audit.call("check",{"candidate":0,"stage":"forecast"})
        audit.call("submit",{"verdict":"ABSTAIN","witness":None})
        result=audit.evaluate()
        self.assertTrue(result["abstained"])
        self.assertFalse(result["incomplete"])
        self.assertFalse(result["evidence_backed_correct"])

    def test_guessing_right_label_not_evidence(self):
        audit=a.Audit(self.sparse,0)
        cid=self.sparse["private"]["outside"][0]
        audit.call("submit",{"verdict":"REJECT","witness":cid})
        self.assertTrue(audit.evaluate()["correct"])
        self.assertFalse(audit.evaluate()["witness_valid"])

    def test_purchased_counterexample_is_evidence(self):
        audit=a.Audit(self.sparse,32)
        cid=self.sparse["private"]["outside"][0]
        for stage in ("calibration","forecast"):
            audit.call("check",{"candidate":cid,"stage":stage})
        audit.call("submit",{"verdict":"REJECT","witness":cid})
        self.assertTrue(audit.evaluate()["evidence_backed_correct"])

    def test_bad_check_cannot_certify_correct_rejection(self):
        audit=a.Audit(self.sparse,32)
        cid=self.sparse["private"]["outside"][0]
        for stage in ("calibration","forecast"):
            audit.call("check",{"candidate":cid,"stage":stage})
        audit.runs[audit.cache[cid,"forecast"]]["q"]*=2
        audit.call("submit",{"verdict":"REJECT","witness":cid})
        self.assertTrue(audit.evaluate()["correct"])
        self.assertFalse(audit.evaluate()["evidence_backed_correct"])

    def test_accurate_point_does_not_cover_all_candidates(self):
        audit=a.Audit(self.rich,0)
        a.policy(audit.call,"nominal_only")
        result=audit.evaluate()
        self.assertTrue(result["correct"])
        self.assertFalse(result["acceptance_covered"])
        self.assertEqual(result["covered_candidates"],1)

    def test_exhaustive_acceptance_finite_only(self):
        audit=a.Audit(self.rich,256)
        with patch.object(a,"commission",side_effect=AssertionError("hidden reference")):
            a.policy(audit.call,"screened")
        result=audit.evaluate()
        self.assertTrue(result["acceptance_covered"])
        self.assertTrue(result["evidence_backed_correct"])
        self.assertEqual(result["covered_candidates"],125)
        self.assertLessEqual(audit.spent,256*256)

    def test_deterministic_policy_and_no_reference_access(self):
        results=[]
        for _ in range(2):
            audit=a.Audit(self.sparse,32)
            with patch.object(a,"commission",side_effect=AssertionError("hidden reference")):
                a.policy(audit.call,"screened")
            results.append((audit.submission,audit.spent,list(audit.cache)))
        self.assertEqual(results[0],results[1])

    def test_logs_and_offline_regeneration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=RunLog(tmp,"test")
            root.write_json("manifest.json",{"cases":[self.sparse["id"]],"budgets":[32],"policies":["screened"]})
            child=RunLog(root.path/"episodes","test")
            audit=a.Audit(self.sparse,32,child)
            a.policy(audit.call,"screened")
            row={"case_id":self.sparse["id"],"regime":"sparse","budget":32,"policy":"screened","evaluation":audit.evaluate(),"path":child.path.relative_to(root.path).as_posix()}
            child.write_json("result.json",row)
            child.close(); root.close()
            events,torn=read_events(child.path)
            self.assertFalse(torn)
            self.assertEqual(sum(v["charged_work"] for v in events if v["kind"]=="solver_finished"),audit.spent)
            with patch.object(a,"solve",side_effect=AssertionError("solver")),patch.object(a.Audit,"call",side_effect=AssertionError("tool")):
                first=a.render(root.path)
                before=(child.path/"transcript.md").read_bytes()
                second=a.render(root.path)
            self.assertEqual(first,second)
            self.assertEqual(before,(child.path/"transcript.md").read_bytes())


if __name__=="__main__": unittest.main()
