"""CPU-only MMS tests; no optional SDK, credentials or network."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from budgeted_science.agents.records import RunLog, digest, read_events
from budgeted_science.mms_verification import numerics as num
from budgeted_science.mms_verification.catalog import make_catalog, public_original_data, public_study, relevant_family
from budgeted_science.mms_verification.environment import Audit, score
from budgeted_science.mms_verification.experiment import aggregate, artifact_hashes, render, run_cpu
from budgeted_science.mms_verification.policies import order_verdict, qoi_verdict, run_policy


class MMSNumerics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validation = num.validate()

    def test_all_numerical_contracts(self):
        self.assertLess(self.validation["checks"]["max_laplacian_disagreement"], 1e-10)
        self.assertEqual(len(self.validation["convergence"]), 9)

    def test_inactive_feature(self):
        self.assertEqual(self.validation["checks"]["inactive_upwind_max_difference"], 0)

    def test_independent_assembly_is_separate(self):
        with patch.object(num, "assemble", side_effect=AssertionError("audited assembly called")):
            r = num.solve(num.PROBLEMS["mixed"], num.DIAGNOSTIC, 16, kernel="independent")
        self.assertEqual(r["status"], "complete")
        self.assertLess(num.errors(r, num.DIAGNOSTIC)["rms_error"], .1)

    def test_affine_exact_including_mixed_corner(self):
        profile = num.Profile(amplitude=0)
        for problem in num.PROBLEMS.values():
            for kernel in ("audited", "independent"):
                r = num.solve(problem, profile, 8, kernel=kernel)
                self.assertLess(num.errors(r, profile)["max_error"], 1e-11)

    def test_invalid_grids_and_coefficients(self):
        for n in (True, 8., 0, 9, 128):
            with self.assertRaises(ValueError):
                num.charge_units(n)
        for k in (-1., 0., float("nan")):
            with self.assertRaises(ValueError):
                num.Problem(k, 0, 0)

    def test_order_band_boundaries_and_numerical_floor(self):
        self.assertTrue(num.order_pass([1.7, 2.3]))
        self.assertFalse(num.order_pass([]))
        self.assertFalse(num.order_pass([2, float("nan")]))
        self.assertEqual(num.orders([.16, .04, .01]), [2., 2.])
        with self.assertRaises(ValueError):
            num.orders([0, 0, 0])

    def test_input_arrays_omit_interior_exact_values(self):
        data = num.inputs(num.PROBLEMS["mixed"], num.DIAGNOSTIC, 8)
        self.assertEqual(set(data), {"forcing", "boundary_values", "right_derivative", "top_derivative"})
        self.assertTrue(np.all(data["boundary_values"][1:, 1:] == 0))

    def test_dirichlet_inputs_do_not_reveal_neumann_data(self):
        data = num.inputs(num.PROBLEMS["diffusion"], num.DIAGNOSTIC, 8)
        self.assertEqual(set(data), {"forcing", "boundary_values"})


class MMSContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = make_catalog()
        cls.case = cls.catalog["cases"][0]

    def test_separate_truths_and_catalog_size(self):
        self.assertEqual(len(self.catalog["cases"]), 6)
        self.assertEqual({(c["private"]["qoi_truth"], c["private"]["order_truth"])
                          for c in self.catalog["cases"]}, {(True, True), (False, True), (False, False), (True, False)})
        self.assertEqual(len(self.catalog["study_sweep"]), 36)

    def test_harmless_control_matches_exactly(self):
        a, b = self.catalog["cases"][0], self.catalog["cases"][-1]
        self.assertEqual(a["reported_q"], b["reported_q"])
        self.assertEqual(a["original"]["field"], b["original"]["field"])

    def test_budget_commissioned_above_complete_path(self):
        for row in self.catalog["feasibility"]:
            self.assertLess(row["path_credits"], 10)
            self.assertLess(row["independent_32_q_error"], .005)

    def test_public_views_omit_truth_and_fault_flags(self):
        audit = Audit(self.case, 10)
        response = audit.call("a", "run_study", grid=32)
        public = json.dumps([audit.describe(), response, audit.artifacts(), public_original_data(self.case)])
        for key in ("q_error", "reference_q", "qoi_truth", "order_truth", "flavor", "category", "study_profile"):
            self.assertNotIn('"'+key+'"', public)

    def test_public_mms_exact_errors_allowed(self):
        r = Audit(self.case, 10).call("a", "run_mms", family="diffusion", grid=8)
        self.assertIn("diagnostic_errors", r["result"])

    def test_exact_charging_duplicate_and_free_record(self):
        audit = Audit(self.case, 1)
        first = audit.call("a", "run_mms", family="diffusion", grid=16)
        self.assertEqual(first["budget"]["remaining"], 0)
        self.assertEqual(audit.call("a", "run_mms", family="diffusion", grid=16), first)
        reuse = audit.call("b", "run_mms", family="diffusion", grid=16)
        self.assertEqual(reuse["result"]["charge"], 0)
        full = audit.call("c", "record", result_id=first["result"]["id"])
        self.assertEqual(len(full["result"]["field"]), 17)
        with self.assertRaises(ValueError):
            audit.call("a", "run_mms", family="mixed", grid=8)

    def test_invalid_and_unaffordable_requests_free(self):
        audit = Audit(self.case, 0)
        for args in ({"grid": 8}, {"grid": 8, "family": "other"}, {"grid": True, "family": "diffusion"}):
            self.assertFalse(audit.call(str(args), "run_mms", **args)["ok"])
        self.assertEqual(audit.status()["spent"], 0)
        self.assertTrue(audit.call("original", "run_study", grid=16)["ok"])
        self.assertTrue(audit.call("s", "submit", qoi="ABSTAIN", order="ABSTAIN", evidence_ids=[])["ok"])

    def test_failed_solve_charged_cached_and_reused(self):
        backend = {}
        with patch("builtins.print"):
            def fail(*args):
                raise RuntimeError("numerical failure")
            a = Audit(self.case, 2, backend=backend, executor=fail)
            r = a.call("a", "run_mms", family="diffusion", grid=16)
            self.assertEqual(r["result"]["status"], "failed")
            self.assertEqual(a.status()["spent"], 1)
            a.call("b", "run_mms", family="diffusion", grid=16)
            self.assertEqual(a.status()["spent"], 1)
            def forbidden(*args):
                raise AssertionError("warm backend executed")
            b = Audit(self.case, 1, backend=backend, executor=forbidden)
            r = b.call("c", "run_mms", family="diffusion", grid=16)
            self.assertEqual(r["result"]["status"], "failed")
            self.assertEqual(b.status()["spent"], 1)

    def test_warm_cold_cache_budget_and_science_equivalence(self):
        backend = {}
        a, b = Audit(self.case, 1, backend=backend), Audit(self.case, 1, backend=backend)
        ra = a.call("a", "run_mms", family="mixed", grid=16)
        rb = b.call("a", "run_mms", family="mixed", grid=16)
        self.assertEqual(ra["budget"], rb["budget"])
        self.assertEqual(ra["result"]["q"], rb["result"]["q"])
        self.assertEqual(ra["result"]["diagnostic_errors"], rb["result"]["diagnostic_errors"])
        self.assertFalse(b.call("b", "run_mms", family="mixed", grid=32)["ok"])

    def test_no_reference_or_parameter_action(self):
        audit = Audit(self.case, 10)
        self.assertFalse(audit.call("a", "reference")["ok"])
        self.assertFalse(audit.call("b", "run_study", grid=8, theta=[1, 2])["ok"])
        self.assertFalse(audit.call("c", "run_study", grid=8, family="mixed")["ok"])
        self.assertEqual(audit.status()["spent"], 0)

    def test_submission_validation_and_private_score(self):
        audit = Audit(self.case, 0)
        self.assertFalse(audit.call("a", "submit", qoi="ACCEPT", order="ACCEPT", evidence_ids=["unknown"])["ok"])
        self.assertFalse(audit.call("b", "submit", qoi="bad", order="ACCEPT", evidence_ids=[])["ok"])
        result = audit.call("c", "submit", qoi="ACCEPT", order="ABSTAIN", evidence_ids=["original"])
        self.assertNotIn("truth", json.dumps(result))
        e = score(audit.submission, self.case)
        self.assertTrue(e["qoi"]["correct"])
        self.assertFalse(e["order"]["correct"])
        self.assertTrue(e["complete"])
        self.assertFalse(score(None, self.case)["complete"])

    def test_rules_depend_on_public_inputs_not_category(self):
        self.assertEqual(relevant_family({"boundary": "mixed", "vx": 0, "vy": 0}), "mixed")
        self.assertEqual(relevant_family({"boundary": "dirichlet", "vx": 1, "vy": 0}), "advection")
        changed = deepcopy(self.case)
        changed["category"] = "irrelevant label"
        changed["private"] = {}
        audit = Audit(changed, 10)
        run_policy("study_aware", audit.describe(), audit.call)
        self.assertIsNotNone(audit.submission)

    def test_irrelevant_mms_cannot_certify_order(self):
        records = [{"kind": "mms", "family": "diffusion", "kernel": "audited", "status": "complete",
                    "grid": n, "diagnostic_errors": {"rms_error": 1/n**2}} for n in (8, 16, 32)]
        self.assertEqual(order_verdict(records, "mixed")[0], "ABSTAIN")
        self.assertEqual(order_verdict(records, "diffusion")[0], "ACCEPT")

    def test_early_falsification_and_partial_positive_abstention(self):
        records = [{"kind": "mms", "family": "advection", "kernel": "audited", "status": "complete",
                    "grid": n, "diagnostic_errors": {"rms_error": 1/n}} for n in (8, 16)]
        self.assertEqual(order_verdict(records, "advection")[0], "REJECT")
        for r in records:
            r["diagnostic_errors"]["rms_error"] **= 2
        self.assertEqual(order_verdict(records, "advection")[0], "ABSTAIN")

    def test_qoi_estimator_no_extra_solver(self):
        p = public_study(self.case)
        records = [{"id": "r", "kind": "study", "status": "complete", "kernel": "independent", "grid": 32, "q": p["reported_q"]}]
        with patch.object(num, "solve", side_effect=AssertionError("unpaid solve")):
            self.assertEqual(qoi_verdict(p, records, "independent")[0], "ACCEPT")

    def test_interrupt_persists_purchase_before_work(self):
        events = []
        def interrupt(*args):
            raise KeyboardInterrupt()
        audit = Audit(self.case, 1, sink=lambda kind, **data: events.append((kind, data)), executor=interrupt)
        with self.assertRaises(KeyboardInterrupt):
            audit.call("a", "run_mms", family="diffusion", grid=16)
        self.assertEqual(audit.status()["spent"], 1)
        self.assertEqual(events[-1][0], "purchase")

    def test_aggregate_hand_checked_and_offline_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = RunLog(tmp, "fixture")
            ep = RunLog(log.path/"episodes", "fixture")
            audit = Audit(self.case, 0, sink=ep.event)
            audit.call("a", "submit", qoi="ACCEPT", order="ABSTAIN", evidence_ids=["original"])
            submission = audit.submission
            row = {"study_id": self.case["id"], "budget": 10, "policy": "fixture", "spent": 0, "seconds": .1,
                   "submission": submission, "evaluation": score(submission, self.case), "directory": ep.path.relative_to(log.path).as_posix()}
            ep.write_json("result.json", row)
            ep.close()
            groups = aggregate([row])
            self.assertEqual(groups[0]["qoi"]["correct"], 1)
            self.assertEqual(groups[0]["order"]["abstentions"], 1)
            summary = {"cases": [{k:v for k,v in self.case.items() if k != "original"}], "results": [row], "aggregate": groups}
            manifest = {"version": "fixture"}
            log.write_json("manifest.json", manifest)
            log.write_json("private/catalog.json", {"cases": [self.case]})
            log.write_json("summary.json", summary)
            log.close()
            completion = {"summary_sha256": digest(summary), "manifest_sha256": digest(manifest),
                          "artifact_sha256": artifact_hashes(log.path)}
            log.write_json("completion.json", completion)
            with patch.object(num, "solve", side_effect=AssertionError("render executed solver")):
                target = render(log.path)
            self.assertIn("1/1", target.read_text(encoding="utf-8"))
            self.assertTrue((ep.path/"transcript.md").is_file())
            self.assertFalse(read_events(ep.path)[1])
            # Even if a corrupted event file's checksum is updated, reconciliation
            # rejects a verdict that contradicts the saved accepted submission.
            events, _ = read_events(ep.path)
            for event in events:
                if event["kind"] == "request":
                    event["arguments"]["qoi"] = "REJECT"
            (ep.path/"events.jsonl").write_text("\n".join(json.dumps(e) for e in events)+"\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "integrity"):
                render(log.path)
            completion["artifact_sha256"] = artifact_hashes(log.path)
            log.write_json("completion.json", completion, replace=True)
            with self.assertRaisesRegex(ValueError, "submission or ledger"):
                render(log.path)

    def test_interrupted_batch_renders_attempted_not_unattempted(self):
        with tempfile.TemporaryDirectory() as tmp:
            def interrupt(name, public, call):
                call("a", "run_mms", family="diffusion", grid=16)
                raise KeyboardInterrupt()
            with patch("budgeted_science.mms_verification.experiment.validate", return_value={}), patch(
                "budgeted_science.mms_verification.experiment.make_catalog", return_value=self.catalog
            ), patch("budgeted_science.mms_verification.experiment.run_policy", side_effect=interrupt):
                path = run_cpu(tmp)
            summary = json.loads((path/"summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "interrupted")
            self.assertEqual(summary["unattempted"], 59)
            self.assertEqual(len(summary["results"]), 1)
            self.assertFalse(summary["results"][0]["evaluation"]["complete"])
            self.assertEqual(summary["results"][0]["spent"], 1)
            self.assertTrue((path/"report.md").exists())

    def test_source_mismatch_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("budgeted_science.mms_verification.experiment.provenance", side_effect=[
                {"source_sha256": {"x": "before"}}, {"source_sha256": {"x": "after"}}
            ]), patch("budgeted_science.mms_verification.experiment.validate", side_effect=KeyboardInterrupt):
                path = run_cpu(tmp)
            summary = json.loads((path/"summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "source_mismatch")
            self.assertFalse(summary["source_freeze_matches"])
            self.assertEqual(summary["unattempted"], 60)


if __name__ == "__main__":
    unittest.main()
