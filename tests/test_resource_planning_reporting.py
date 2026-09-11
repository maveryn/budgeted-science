"""Offline orchestration, freeze and reporting contracts with synthetic failures."""

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import random
from statistics import mean
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

from budgeted_science.agents.records import RunLog, digest, read_events
from budgeted_science.resource_planning import experiment
from budgeted_science.resource_planning.reporting import load_attempts, paired_bootstrap, regenerate, summarize


def fixture(targets=2, seeds=(0, 1, 2)):
    rows = []
    for target in range(targets):
        for seed in seeds:
            for policy in ("random", "adaptive"):
                error = .5 + .1 * seed + .2 * target - .1 * (policy == "adaptive")
                rows.append({"attempt_id": f"target-{target}-s{seed}-{policy}", "target_id": f"target-{target}",
                             "target_seed": 2000 + target, "policy_seed": seed, "policy": policy,
                             "status": "completed", "started": True, "valid": True, "success": True,
                             "score": 1., "objective_successes": [True] * 3,
                             "parameter_error": error, "parameter_errors": [error] * 3,
                             "resources": {"credits_spent": 40, "simulate_low_count": 12}, "elapsed_seconds": 2.})
    return rows


def saved_fixture(root, rows, *, missing=(), finished=True):
    log = RunLog(root, "fixture")
    attempts = [{**experiment._identity(row), "result_path": f"attempts/{row['attempt_id']}/result.json"} for row in rows]
    log.write_json("manifest.json", {"schema_version": 1, "phase": "pilot", "policy_seeds": [0, 1, 2],
                                    "attempts": attempts, "source_hashes": {}, "versions": {},
                                    "PRIVATE_harness_only": {"targets": "never copy this into a report"}})
    for row, spec in zip(rows, attempts):
        if row["attempt_id"] in missing:
            continue
        log.event("attempt_started", attempt_id=row["attempt_id"])
        log.write_json(spec["result_path"], row)
        log.event("attempt_finished", result=row)
    if finished:
        log.event("experiment_finished")
    log.close()
    return log.path


def hanging_worker(spec, config, root, deadline):
    log = RunLog(root, "hang")
    log.event("public_status", public_status={"spent": 8, "remaining": 32})
    log.event("diagnostic", partial="saved before uncooperative work", thread_limits={k: os.environ[k] for k in experiment.THREAD_LIMITS})
    time.sleep(30)


def crashing_worker(spec, config, root, deadline):
    log = RunLog(root, "crash")
    log.event("diagnostic", partial="retained")
    log.close()
    raise RuntimeError("synthetic worker failure")


class ReportingTests(unittest.TestCase):
    def test_worst_error_regression_survives_saved_report_regeneration(self):
        value = {"status": "submitted", "valid": True, "errors": [.2, 1.7, .2],
                 "successes": [True, False, True], "parameter_error": 1.7,
                 "success": False, "all_success": False, "score": 0}
        canonical = experiment._evaluation_fields(value, "completed")
        self.assertEqual(canonical["parameter_error"], 1.7)
        self.assertFalse(canonical["success"])
        self.assertEqual(canonical["score"], 0)
        rows = fixture(1)
        for row in rows:
            row.update(canonical)
        with tempfile.TemporaryDirectory() as tmp:
            path = saved_fixture(tmp, rows)
            result = regenerate(path, repetitions=10)
            random_result = result["policies"]["random"]
            self.assertEqual(random_result["parameter_error_valid_only"]["mean"], 1.7)
            self.assertEqual(random_result["mean_score_all_attempts"], 0)
            self.assertEqual(random_result["failure_counts"], {"tolerance_not_met": 3})
            self.assertIn("MAXIMUM", (path / "report/report.md").read_text())

    def test_failures_count_in_denominator_but_not_error(self):
        rows = fixture()
        rows[0].update(status="timeout", valid=False, success=False, score=0, parameter_error=None)
        report = summarize(rows, repetitions=40)
        random_result = report["policies"]["random"]
        self.assertEqual(random_result["attempts"], 6)
        self.assertEqual(random_result["valid_submissions"], 5)
        self.assertEqual(random_result["success_rate_all_attempts"], 5 / 6)
        self.assertEqual(random_result["mean_score_all_attempts"], 5 / 6)
        self.assertEqual(random_result["failure_counts"], {"timeout": 1})
        self.assertEqual(random_result["elapsed_seconds"]["count"], 6)
        paired = report["paired_bootstrap"]["metrics"]
        self.assertEqual(paired["parameter_error"]["paired_observations"], 5)
        self.assertEqual(paired["success"]["paired_observations"], 6)
        self.assertAlmostEqual(paired["success"]["difference"], 1 / 6)

    def test_partial_objectives_do_not_earn_primary_success(self):
        rows = fixture(1)
        rows[0].update(score=0, success=False, objective_successes=[True, False, True],
                       parameter_errors=[.5, 1.5, .5], parameter_error=1.5)
        result = summarize(rows, repetitions=10)["policies"]["random"]
        self.assertAlmostEqual(result["mean_score_all_attempts"], 2 / 3)
        self.assertEqual(result["success_rate_all_attempts"], 2 / 3)
        self.assertEqual(result["objective_success_rates_all_attempts"], [1, 2 / 3, 1])

    def test_timeout_cannot_retain_claimed_success_or_error(self):
        rows = fixture(1)
        rows[0]["status"] = "timeout"  # Even a malformed saved success cannot count.
        result = summarize(rows, repetitions=10)["policies"]["random"]
        self.assertEqual(result["valid_submissions"], 2)
        self.assertEqual(result["successes"], 2)

    def test_target_cluster_bootstrap_keeps_all_three_seeds(self):
        rows = fixture(3)
        effects = [-2., 1., 7.]
        for row in rows:
            target = int(row["target_id"].split("-")[-1])
            row["elapsed_seconds"] = 20 + row["policy_seed"] + (effects[target] if row["policy"] == "adaptive" else 0)
        result = paired_bootstrap(rows, repetitions=111, seed=42)
        rng = random.Random(42)
        # Independent reference: choose three target effects per draw; each
        # target's three seeds repeat the same effect and cannot be split up.
        draws = sorted(mean(effects[rng.randrange(3)] for _ in range(3)) for _ in range(111))
        def quantile(q):
            at = q * (len(draws) - 1)
            lo = int(at)
            return draws[lo] + (draws[min(lo + 1, len(draws) - 1)] - draws[lo]) * (at - lo)
        metric = result["metrics"]["elapsed_seconds"]
        self.assertAlmostEqual(metric["difference"], 2.)
        self.assertEqual(metric["ci95"], [quantile(.025), quantile(.975)])
        self.assertEqual(result["policy_seeds_retained"], [0, 1, 2])
        self.assertEqual(result["direction"], "adaptive minus random")

    def test_all_failure_errors_are_null_and_no_nan(self):
        rows = fixture()
        for row in rows:
            row.update(status="worker_crash", valid=False, success=False, parameter_error=None, resources={}, elapsed_seconds=None)
        summary = summarize(rows, repetitions=20)
        metric = summary["paired_bootstrap"]["metrics"]["parameter_error"]
        self.assertIsNone(metric["difference"])
        self.assertIsNone(metric["ci95"])
        self.assertEqual(metric["undefined_bootstrap_replicates"], 20)
        self.assertNotIn("NaN", json.dumps(summary, allow_nan=False))

    def test_invalid_numeric_error_does_not_count(self):
        rows = fixture(1)
        rows[0]["parameter_error"] = float("nan")
        report = summarize(rows, repetitions=10)
        self.assertEqual(report["policies"]["random"]["valid_submissions"], 2)
        json.dumps(report, allow_nan=False)

    def test_duplicates_missing_seed_and_unknown_policy_rejected(self):
        rows = fixture()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            paired_bootstrap(rows + [rows[0]])
        with self.assertRaisesRegex(ValueError, "every paired policy seed"):
            paired_bootstrap(rows[1:])
        rows[0]["policy"] = "invented"
        with self.assertRaisesRegex(ValueError, "unknown policy"):
            paired_bootstrap(rows)

    def test_deterministic_offline_regeneration_preserves_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = saved_fixture(tmp, fixture())
            originals = {p: p.read_bytes() for p in path.rglob("*") if p.is_file()}
            with patch("budgeted_science.resource_planning.environment._solve_high", side_effect=AssertionError("no solver")), \
                 patch.dict("sys.modules", {"openai": None}):
                first = regenerate(path, repetitions=100, seed=18)
                rendered = {p.name: p.read_bytes() for p in (path / "report").iterdir()}
                second = regenerate(path, repetitions=100, seed=18)
            self.assertEqual(first, second)
            self.assertEqual(rendered, {p.name: p.read_bytes() for p in (path / "report").iterdir()})
            self.assertEqual(originals, {p: p.read_bytes() for p in originals})
            for name in ("paired_errors.svg", "paired_resources.svg"):
                ET.fromstring(rendered[name])
            self.assertNotIn("never copy", rendered["summary.json"].decode())
            self.assertIn("Adaptive minus random", rendered["report.md"].decode())

    def test_full_pilot_missing_results_still_has_120_attempts(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = fixture(20)
            path = saved_fixture(tmp, rows, missing=[r["attempt_id"] for r in rows[3:]], finished=False)
            manifest, loaded, recovery = load_attempts(path)
            self.assertEqual(len(loaded), 120)
            self.assertEqual(sum(r["status"] == "not_started" for r in loaded), 117)
            report = regenerate(path, repetitions=10)
            self.assertEqual(report["attempts"], 120)
            self.assertFalse(recovery["experiment_finished"])

    def test_event_fallback_and_torn_tail_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = fixture(1)
            path = saved_fixture(tmp, rows)
            (path / "attempts" / rows[0]["attempt_id"] / "result.json").unlink()
            with (path / "events.jsonl").open("ab") as stream:
                stream.write(b'{"sequence":')
            _, loaded, recovery = load_attempts(path)
            self.assertEqual(loaded[0], rows[0])
            self.assertTrue(recovery["torn_final_event"])

    def test_result_event_disagreement_and_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = fixture(1)
            path = saved_fixture(tmp, rows)
            target = path / "attempts" / rows[0]["attempt_id"] / "result.json"
            changed = deepcopy(rows[0])
            changed["status"] = "timeout"
            target.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "disagree"):
                load_attempts(path)
            manifest = json.loads((path / "manifest.json").read_text())
            manifest["attempts"][0]["result_path"] = "../escape.json"
            (path / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "escapes"):
                load_attempts(path)


class SupervisorTests(unittest.TestCase):
    def test_spawn_timeout_retains_partial_events_and_no_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = experiment.supervise(fixture(1)[0], None, Path(tmp) / "attempt", timeout_seconds=2., worker=hanging_worker)
            self.assertEqual(result["status"], "timeout")
            self.assertFalse(result["success"])
            self.assertIsNone(result["parameter_error"])
            self.assertLess(result["elapsed_seconds"], 6.)
            self.assertEqual(result["resources"]["credits_spent"], 8)
            trace = Path(tmp) / "attempt" / result["trace_path"]
            events, torn = read_events(trace)
            self.assertEqual(events[1]["thread_limits"], experiment.THREAD_LIMITS)
            self.assertFalse(torn)

    def test_worker_crash_remains_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = experiment.supervise(fixture(1)[0], None, Path(tmp) / "attempt", timeout_seconds=3., worker=crashing_worker)
            self.assertEqual(result["status"], "worker_crash")
            self.assertIsNone(result["evaluation"])
            self.assertIsNotNone(result["trace_path"])

    def test_no_timeout_above_hard_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                experiment.supervise(fixture(1)[0], None, Path(tmp) / "attempt", timeout_seconds=301)

    def test_real_config_serializes_and_scoring_uses_private_evaluation(self):
        from budgeted_science.resource_planning.config import Config
        from budgeted_science.resource_planning.emulator import GPSettings
        config = experiment.configuration(Config())
        self.assertEqual(config["emulator"], GPSettings().to_dict())
        self.assertEqual(config["public"]["costs"], {"low": 1, "high": 8, "measurement": 12})
        value = {"status": "submitted", "valid": True, "errors": [.1, 1.5, .4], "successes": [True, False, True],
                 "score": 0, "success": False, "all_success": False, "parameter_error": 1.5}
        result = experiment._evaluation_fields(value, "completed")
        self.assertTrue(result["valid"])
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["parameter_error"], 1.5)
        self.assertFalse(result["success"])
        self.assertFalse(experiment._evaluation_fields(value, "timeout")["valid"])

    def test_pilot_checks_freeze_before_sampling_or_creating_run(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(experiment, "verify_freeze", side_effect=ValueError("bad freeze")), \
             patch.object(experiment, "target_set", side_effect=AssertionError("must not generate targets")) as targets:
            with self.assertRaisesRegex(ValueError, "bad freeze"):
                experiment.run_experiment("pilot", tmp, freeze="missing.json")
            targets.assert_not_called()
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_debug_development_pilot_sampling_design(self):
        from budgeted_science.resource_planning.config import Config
        config = Config()
        self.assertEqual(experiment.target_set("debug", config)[0]["theta"], [1, .08, 1.4])
        dev = experiment.target_set("development", config)
        pilot = experiment.target_set("pilot", config)
        self.assertEqual([r["target_seed"] for r in dev], list(range(1000, 1008)))
        self.assertEqual([r["target_seed"] for r in pilot], list(range(2000, 2020)))
        self.assertEqual(dev, experiment.target_set("development", config))


class FreezeTests(unittest.TestCase):
    def test_freeze_complete_development_allows_scientific_failure_not_code_changes(self):
        from budgeted_science.resource_planning.config import Config
        config = Config()
        hashes = {"policies.py": "a"}
        with tempfile.TemporaryDirectory() as tmp, patch.object(experiment, "_check_implementation"), \
             patch.object(experiment, "source_hashes", return_value=hashes) as hash_function:
            log = RunLog(tmp, "development-fixture")
            rows = fixture(8, seeds=(0,))
            specs = []
            for row in rows:
                row["target_id"] = f"development-{1000 + row['target_seed'] - 2000}"
                row["target_seed"] -= 1000
                row.update(success=False, score=0, parameter_error=1.7)
                spec = {**experiment._identity(row), "result_path": f"attempts/{row['attempt_id']}/result.json"}
                specs.append(spec)
                log.write_json(spec["result_path"], row)
                log.event("attempt_finished", result=row)
            log.write_json("manifest.json", {"phase": "development", "attempts": specs,
                                            "source_hashes": hashes, "configuration": experiment.configuration(config),
                                            "versions": experiment.versions()})
            log.write_json("completion.json", {"complete": True, "source_unchanged": True})
            log.event("experiment_finished")
            log.close()
            frozen = experiment.freeze_development(log.path, Path(tmp) / "freeze.json")
            self.assertEqual(frozen["development_attempts"], 16)
            hash_function.return_value = {"policies.py": "changed"}
            with self.assertRaisesRegex(ValueError, "changed since development"):
                experiment.freeze_development(log.path, Path(tmp) / "other.json")

    def test_hashes_include_package_tests_config_exclude_docs_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = ["shared/budgeted_science/resource_planning/policies.py", "shared/budgeted_science/resource_planning/emulator.py",
                     "tests/test_x.py", "pyproject.toml", "docs/guide.md", "openaiapi.txt"]
            for name in paths:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("synthetic")
            self.assertEqual(set(experiment.source_hashes(root)), set(paths[:4]))

    def test_freeze_tamper_code_settings_and_versions_are_rejected(self):
        from budgeted_science.resource_planning.config import Config
        settings = experiment.configuration(Config())
        value = {"phase": "development-freeze", "source_hashes": {"policies.py": "a"}, "configuration": settings,
                 "versions": experiment.versions(), "development_attempts": 16,
                 "evaluation_design": {"target_seeds": list(range(2000, 2020)), "policy_seeds": [0, 1, 2],
                                       "policies": ["random", "adaptive"], "attempts": 120}}
        with tempfile.TemporaryDirectory() as tmp, patch.object(experiment, "_check_implementation"), \
             patch.object(experiment, "source_hashes", return_value={"policies.py": "a"}):
            path = Path(tmp) / "freeze.json"
            def save(payload):
                payload = deepcopy(payload)
                payload["digest"] = digest(payload)
                path.write_text(json.dumps(payload))
            save(value)
            self.assertEqual(experiment.verify_freeze(path)["development_attempts"], 16)
            for key, changed in (("source_hashes", {}), ("configuration", {}), ("versions", {})):
                with self.subTest(key=key):
                    altered = deepcopy(value)
                    altered[key] = changed
                    save(altered)
                    with self.assertRaises(ValueError):
                        experiment.verify_freeze(path)
            save(value)
            altered = json.loads(path.read_text())
            altered["development_attempts"] = 0
            path.write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError, "digest"):
                experiment.verify_freeze(path)


class NumericalValidationTests(unittest.TestCase):
    def test_absolute_error_gate_cannot_be_replaced_by_relative_error(self):
        import numpy as np
        from budgeted_science.resource_planning import validate
        high = SimpleNamespace(sample=lambda times: np.full((len(times), 2), 1e8), artifact=lambda: {})
        radau = SimpleNamespace(success=True, status=0, message="synthetic", nfev=1, njev=1, nlu=1,
                                t=np.linspace(0, 8, 161), y=np.full((2, 161), 1e8 + 1e-4))
        with patch("budgeted_science.resource_planning.environment._solve_high", return_value=high), \
             patch("budgeted_science.resource_planning.environment._solve_low", return_value=high), \
             patch("scipy.integrate.solve_ivp", return_value=radau) as solve, \
             patch.object(validate, "_recover", return_value={"recovered_from_any_start": True}):
            result = validate.run_validation(starts=2)
        self.assertFalse(result["complete"])
        self.assertFalse(result["all_numeric_pass"])
        comparison = result["targets"][0]["high_vs_radau"]
        self.assertLess(comparison["maximum_relative_error"], 1e-6)
        self.assertGreater(comparison["maximum_absolute_error"], 1e-6)
        self.assertFalse(comparison["within_1e_6_absolute"])
        self.assertEqual(solve.call_args.kwargs["rtol"], 1e-10)
        self.assertEqual(solve.call_args.kwargs["atol"], 1e-12)


if __name__ == "__main__":
    unittest.main()
