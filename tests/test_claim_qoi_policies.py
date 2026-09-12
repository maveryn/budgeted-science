"""Policy contracts using deterministic public calls; no numerical backend."""

import ast
from copy import deepcopy
import math
from pathlib import Path
import random
import unittest
from unittest.mock import patch

from budgeted_science.claim_verification_qoi import policies as p


def cfg(method="Euler", dt=.16, step=.32, offset=0.):
    return dict(method=method, dt=dt, output_step=step, output_offset=offset)


def run(run_id, config, height=100., peak=2., cumulative=300., **extra):
    return dict(status="success", run_id=run_id, config=deepcopy(config),
                qois=dict(peak_height=height, peak_time=peak, cumulative=cumulative), **extra)


def claim(quantity="peak_height", reported=100., kind="absolute", tolerance=.1):
    return dict(quantity=quantity, reported=reported, tolerance_kind=kind, tolerance=tolerance)


def sample_times(config):
    step, offset = config["output_step"], config["output_offset"]
    times = [0., 8.]
    for k in range(math.ceil(8 / step) + 1):
        value = (k + offset) * step
        if 0 < value < 8:
            times.append(value)
    return sorted(set(times))


class FakeCall:
    """Manufactured tables/qois with work priced by the public formula."""
    def __init__(self, quantity=None, factory=None, original=None, run_status="success",
                 bad_quotes=False, bad_budget=False, check_read_failure=False):
        self.claim = quantity or claim()
        self.original = original or cfg()
        self.factory = factory or (lambda c: dict(peak_height=100. + c["dt"], peak_time=2., cumulative=300.))
        self.run_status = run_status
        self.bad_quotes, self.bad_budget = bad_quotes, bad_budget
        self.check_read_failure = check_read_failure
        self.calls, self.purchases = [], []
        self.spent_work, self.submission = 0, None
        self.runs = {"original": self.make_run("original", self.original)}
        self.cache = {self.key(self.original): "original"}

    @staticmethod
    def key(config):
        return tuple(config[k] for k in ("method", "dt", "output_step", "output_offset"))

    @staticmethod
    def work(config):
        stages = 1 if config["method"] == "Euler" else 2
        return stages * round(8 / config["dt"]) + len(sample_times(config))

    def make_run(self, run_id, config):
        times = sample_times(config)
        return dict(status="success", run_id=run_id, config=deepcopy(config), times=times,
                    values=[[10. + t, 5.] for t in times], qois=self.factory(config))

    def __call__(self, name, args):
        if self.submission is not None:
            raise AssertionError("tool called after terminal submission")
        self.calls.append((name, deepcopy(args)))
        result = {"status": "success", "remaining": (800 - self.spent_work) / 100}
        if name == "describe":
            result.update(claim=deepcopy(self.claim), original_run_id="original",
                          original_config=deepcopy(self.original), scientific_budget=8)
        elif name == "budget":
            if self.bad_budget:
                result["status"] = "failed"
        elif name == "read_run":
            run_id = args["run_id"]
            if self.check_read_failure and run_id != "original":
                result["status"] = "failed"
            elif run_id not in self.runs or self.runs[run_id]["status"] != "success":
                result["status"] = "invalid"
            else:
                result.update(deepcopy(self.runs[run_id]))
        elif name == "quote_check":
            work = self.work(args)
            result.update(work=work, credits=work / 100, episode_reuse=self.key(args) in self.cache)
            if self.bad_quotes:
                result["status"] = "invalid"
        elif name == "run_check":
            key = self.key(args)
            if key in self.cache:
                result.update(deepcopy(self.runs[self.cache[key]]), charge=0, episode_reuse=True)
            else:
                work = self.work(args)
                if work > 800 - self.spent_work:
                    result.update(status="unaffordable", charge=0)
                elif self.run_status in ("invalid", "unaffordable"):
                    result.update(status=self.run_status, charge=0)
                else:
                    self.spent_work += work
                    run_id = "check-" + str(len(self.purchases) + 1)
                    record = self.make_run(run_id, args)
                    record["status"] = self.run_status
                    if self.run_status != "success":
                        record["qois"] = None
                    self.cache[key] = run_id
                    self.runs[run_id] = record
                    self.purchases.append(deepcopy(args))
                    result.update(deepcopy(record), charge=work / 100, episode_reuse=False,
                                  remaining=(800 - self.spent_work) / 100)
        elif name == "submit":
            assert args["verdict"] in ("ACCEPT", "REJECT", "ABSTAIN")
            assert args["diagnosis"] and args["justification"]
            assert len(args["evidence_ids"]) == len(set(args["evidence_ids"]))
            assert set(args["evidence_ids"]) <= set(self.runs)
            self.submission = deepcopy(args)
        else:
            raise AssertionError("non-public or unsupported call: " + name)
        return result


class EstimatorTests(unittest.TestCase):
    def test_manufactured_richardson_known_orders(self):
        for method, order in (("Euler", 1), ("RK2", 2)):
            for quantity in ("peak_height", "cumulative"):
                with self.subTest(method=method, quantity=quantity):
                    a = run("original", cfg(method, .16, .02))
                    b = run("check", cfg(method, .08, .02))
                    a["qois"][quantity] = 100 + 10 * .16 ** order
                    b["qois"][quantity] = 100 + 10 * .08 ** order
                    before = deepcopy([a, b])
                    result = p.estimate_claim(claim(quantity, tolerance=1e-8), [a, b], "original")
                    self.assertAlmostEqual(result["estimate"], 100)
                    self.assertEqual(result["verdict"], "ACCEPT")
                    self.assertEqual(result["richardson"]["order"], order)
                    self.assertFalse(result["richardson"]["validated"])
                    self.assertEqual([a, b], before)

    def test_richardson_cannot_cross_method_schedule_or_phase(self):
        fine = run("check", cfg("RK2", .04, .04), height=101.)
        for original in (cfg("Euler", .08, .04), cfg("RK2", .08, .08), cfg("RK2", .08, .04, .25)):
            with self.subTest(original=original):
                result = p.estimate_claim(claim(), [run("original", original, height=110), fine], "original")
                self.assertIsNone(result["richardson"])
                self.assertEqual(result["estimate"], 101.)

    def test_small_stored_sample_table_remains_unmodified(self):
        table = run("check", cfg("RK2", .04, 2), height=9., peak=2., cumulative=44.,
                    times=[0., 2., 4., 6., 8.], values=[[1., 0.], [9., 0.], [8., 0.], [4., 0.], [1., 0.]])
        before = deepcopy(table)
        for quantity, expected in (("peak_height", 9.), ("peak_time", 2.), ("cumulative", 44.)):
            result = p.estimate_claim(claim(quantity, expected), [table], "original")
            self.assertEqual(result["estimate"], expected)
            self.assertEqual(result["verdict"], "ACCEPT")
        self.assertEqual(table, before)

    def test_peak_time_is_never_richardson_extrapolated(self):
        records = [run("original", cfg("RK2", .08, .16), peak=2.16),
                   run("check", cfg("RK2", .04, .16), peak=2.08)]
        result = p.estimate_claim(claim("peak_time", 2., tolerance=.04), records, "original")
        self.assertIsNone(result["richardson"])
        self.assertEqual(result["estimate"], 2.08)
        self.assertEqual(result["verdict"], "REJECT")

    def test_absolute_and_relative_tolerance_and_boundary(self):
        records = [run("check", cfg("RK2", .04, .04))]
        relative = p.estimate_claim(claim(reported=104, kind="relative", tolerance=.05), records, "original")
        absolute = p.estimate_claim(claim(reported=104, kind="absolute", tolerance=.05), records, "original")
        self.assertEqual(relative["absolute_tolerance"], 5.)
        self.assertEqual(relative["verdict"], "ACCEPT")
        self.assertEqual(absolute["verdict"], "REJECT")
        boundary = p.estimate_claim(claim(reported=105, kind="relative", tolerance=.05), records, "original")
        self.assertEqual(boundary["verdict"], "ACCEPT")
        zero = p.estimate_claim(claim(reported=0, kind="relative"), [run("check", cfg(), height=0)], "original")
        self.assertEqual(zero["verdict"], "ABSTAIN")

    def test_selection_ignores_agreement_with_printed_claim(self):
        records = [run("original", cfg(), height=100), run("check", cfg("RK2", .04, .04), height=110)]
        a = p.estimate_claim(claim(reported=100), records, "original")
        b = p.estimate_claim(claim(reported=110), records, "original")
        self.assertEqual(a["selected_run_id"], "check")
        self.assertEqual(a["ranking"], b["ranking"])
        self.assertEqual(a["estimate"], b["estimate"])
        self.assertEqual((a["verdict"], b["verdict"]), ("REJECT", "ACCEPT"))

    def test_original_alone_or_failed_check_is_not_verification(self):
        original = run("original", cfg())
        failed = run("bad", cfg("RK2", .02, .02))
        failed["status"] = "failed"
        for records in ([], [original], [original, failed], [original, run("duplicate", cfg())]):
            self.assertEqual(p.estimate_claim(claim(), records, "original")["verdict"], "ABSTAIN")
        self.assertEqual(p.estimate_claim(claim(tolerance=0), [original])["verdict"], "ABSTAIN")


class PolicyTests(unittest.TestCase):
    def test_peak_time_uses_first_order_integration_for_both_methods(self):
        for method, order in (("Euler", 1), ("RK2", 2)):
            with self.subTest(method=method):
                config = cfg(method)
                self.assertAlmostEqual(p._quality(config, "peak_time"), .16 / 8 + .32 / 8)
                for quantity in ("peak_height", "cumulative"):
                    self.assertAlmostEqual(p._quality(config, quantity), (.16 / 8) ** order + (.32 / 8) ** 2)
                tool = FakeCall(quantity=claim("peak_time", 2.), original=config,
                                factory=lambda c: dict(peak_height=100., peak_time=2.+100*c["dt"], cumulative=300.))
                result = p.run_policy(tool, "adaptive")
                refinements = [a for d in result["decisions"] if d["stage"] == "adaptive"
                               for a in d["ranked"] if a["axis"] == "integration" and a["direction"] == "refine"]
                self.assertTrue(refinements)
                self.assertTrue(all(a["refinement_fraction"] == .5 for a in refinements))

    def test_fixed_parameterized_checks_cost_601_and_share_estimator(self):
        for policy, expected in (("fixed_rk2", cfg("RK2", .04, .04)),
                                 ("fixed_euler", cfg("Euler", .02, .04)),
                                 ("fixed_dense_output", cfg("RK2", .08, .02))):
            with self.subTest(policy=policy):
                tool = FakeCall()
                result = p.run_policy(tool, policy)
                self.assertEqual([args for name, args in tool.calls if name == "run_check"], [expected])
                self.assertEqual(tool.spent_work, 601)
                self.assertTrue(result["submitted"])
                self.assertEqual(result["estimator"], p.estimate_claim(tool.claim, result["runs"], "original"))
                self.assertEqual(tool.submission["evidence_ids"], result["estimator"]["evidence_ids"])
                self.assertEqual(result["trace"][-1]["name"], "submit")

    def test_all_policies_preserve_trace_and_share_estimator(self):
        for policy in p.POLICIES:
            with self.subTest(policy=policy):
                tool = FakeCall()
                result = p.run_policy(tool, policy, seed=7)
                self.assertEqual([(e["name"], e["arguments"]) for e in result["trace"]], tool.calls)
                self.assertEqual(result["estimator"], p.estimate_claim(tool.claim, result["runs"], "original"))
                self.assertLessEqual(tool.spent_work, 800)
                self.assertEqual(sum(name == "submit" for name, _ in tool.calls), 1)
                self.assertTrue(result["acquisitions"])
                for a in result["acquisitions"]:
                    self.assertIn("quote", a)
                    self.assertIn("response", a)
                self.assertEqual(len(tool.purchases), len({tool.key(c) for c in tool.purchases}))

    def test_random_plan_precedes_evidence_and_is_invariant_to_values(self):
        a = FakeCall()
        b = FakeCall(factory=lambda c: dict(peak_height=999., peak_time=7., cumulative=1.))
        original_random = random.Random
        def initialize(seed):
            self.assertEqual(a.calls, [])
            return original_random(seed)
        with patch.object(p.random, "Random", side_effect=initialize):
            ra = p.run_policy(a, "random", seed=41)
        rb = p.run_policy(b, "random", seed=41)
        self.assertEqual(ra["random_plan"], rb["random_plan"])
        self.assertEqual(a.purchases, b.purchases)
        self.assertEqual(len(ra["random_plan"]), 140)
        other = p.run_policy(FakeCall(), "random", seed=42)
        self.assertNotEqual(ra["random_plan"], other["random_plan"])

    def test_random_exhausts_affordable_menu_without_overdraft(self):
        tool = FakeCall()
        result = p.run_policy(tool, "random", seed=2)
        self.assertLessEqual(tool.spent_work, 800)
        for config in result["random_plan"]:
            if tool.key(config) not in tool.cache:
                self.assertGreater(tool.work(config), 800 - tool.spent_work)

    def test_adaptive_axis_changes_with_observed_claim_specific_error(self):
        choices = []
        for axis in ("dt", "output_step"):
            tool = FakeCall(factory=lambda c, axis=axis: dict(peak_height=100 + 100*c[axis], peak_time=2., cumulative=300.))
            result = p.run_policy(tool, "adaptive")
            decision = next(d for d in result["decisions"] if d["stage"] == "adaptive" and d["ranked"])
            choices.append(decision["ranked"][0]["axis"])
            self.assertTrue(decision["observed_pairs"])
            self.assertTrue(all("score" in a and "quote" in a for a in decision["ranked"]))
        self.assertEqual(choices, ["integration", "sampling"])

    def test_adaptive_uses_selected_quantity_and_can_crosscheck_method(self):
        def values(c):
            return dict(peak_height=100+100*c["dt"], peak_time=2., cumulative=300+100*c["output_step"])
        axes = []
        for quantity in ("peak_height", "cumulative"):
            result = p.run_policy(FakeCall(quantity=claim(quantity), factory=values), "adaptive")
            first = next(d for d in result["decisions"] if d["stage"] == "adaptive" and d["ranked"])
            axes.append(first["ranked"][0]["axis"])
        self.assertEqual(axes, ["integration", "sampling"])
        tool = FakeCall(factory=lambda c: dict(peak_height=100. if c["method"] == "RK2" else 110., peak_time=2., cumulative=300.))
        result = p.run_policy(tool, "adaptive")
        first = next(d for d in result["decisions"] if d["stage"] == "adaptive" and d["ranked"])
        self.assertEqual(first["ranked"][0]["axis"], "method")

    def test_failed_invalid_unaffordable_checks_abstain(self):
        for status in ("failed", "invalid", "unaffordable"):
            tool = FakeCall(run_status=status)
            result = p.run_policy(tool, "fixed_rk2")
            self.assertEqual(result["estimator"]["verdict"], "ABSTAIN")
            self.assertEqual(result["acquisitions"][0]["response"]["status"], status)
            self.assertEqual(sum(name == "run_check" for name, _ in tool.calls), 1)

    def test_failure_does_not_erase_prior_success_and_never_retries(self):
        tool = FakeCall()
        def fail_later(name, args):
            if len(tool.purchases) >= 1:
                tool.run_status = "failed"
            return tool(name, args)
        result = p.run_policy(fail_later, "adaptive")
        self.assertNotEqual(result["estimator"]["verdict"], "ABSTAIN")
        self.assertTrue(any(a["response"]["status"] == "failed" for a in result["acquisitions"]))
        configs = [tool.key(args) for name, args in tool.calls if name == "run_check"]
        self.assertEqual(len(configs), len(set(configs)))

    def test_missing_quote_budget_or_table_are_safe(self):
        for kwargs in ({"bad_quotes": True}, {"bad_budget": True}):
            tool = FakeCall(**kwargs)
            result = p.run_policy(tool, "fixed_euler")
            self.assertEqual(result["estimator"]["verdict"], "ABSTAIN")
            self.assertEqual(tool.spent_work, 0)
        tool = FakeCall(check_read_failure=True)
        result = p.run_policy(tool, "fixed_euler")
        self.assertNotEqual(result["estimator"]["verdict"], "ABSTAIN")
        self.assertEqual(result["acquisitions"][0]["read_status"], "failed")

    def test_reused_original_is_not_independent_verification(self):
        tool = FakeCall(original=cfg("RK2", .04, .04))
        result = p.run_policy(tool, "fixed_rk2")
        self.assertEqual(tool.spent_work, 0)
        self.assertEqual(result["estimator"]["verdict"], "ABSTAIN")
        self.assertEqual(sum(name == "run_check" for name, _ in tool.calls), 1)

    def test_invalid_quote_cost_never_runs(self):
        tool = FakeCall()
        def bad_quote(name, args):
            response = tool(name, args)
            if name == "quote_check":
                response["credits"] = .01
            return response
        result = p.run_policy(bad_quote, "fixed_rk2")
        self.assertEqual(result["estimator"]["verdict"], "ABSTAIN")
        self.assertEqual(tool.spent_work, 0)

    def test_unknown_policy_fails_before_any_call(self):
        tool = FakeCall()
        with self.assertRaises(ValueError):
            p.run_policy(tool, "oracle")
        self.assertEqual(tool.calls, [])

    def test_no_solver_reference_or_file_dependencies(self):
        tree = ast.parse(Path(p.__file__).read_text(encoding="utf-8"))
        allowed_imports = {"copy", "math", "numbers", "random"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(all(n.name in allowed_imports for n in node.names))
            if isinstance(node, ast.ImportFrom):
                self.assertIn(node.module, allowed_imports)
            if isinstance(node, ast.Name):
                self.assertNotIn(node.id, {"open", "eval", "exec", "__import__"})


if __name__ == "__main__":
    unittest.main()
