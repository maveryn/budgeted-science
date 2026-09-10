"""CPU-only allocation pilot. Standard library only; no agents or API calls.

OCBA uses Jia, arXiv:1206.5865v1, Theorem 2, with deterministic costs.
The quadrature task and Monte Carlo selection variant are explicitly separate.
Run from repository root: python demos/planning/src/ocba_pilot.py
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path
import platform
import random
import statistics
import time
from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class Curve:
    offset: float
    slope: float = 0.0
    amplitude: float = 0.0
    center: float = 0.5
    width: float = 0.2

    def value(self, x: float) -> float:
        return self.offset + self.slope * x + self.amplitude * math.exp(
            -((x - self.center) / self.width) ** 2
        )

    def integral(self) -> float:
        return self.offset + self.slope / 2 + self.amplitude * self.width * math.sqrt(
            math.pi
        ) / 2 * (math.erf((1 - self.center) / self.width) - math.erf(-self.center / self.width))


ORIGINAL = (
    Curve(1.0, slope=0.2),
    Curve(0.2, amplitude=1, center=0.4, width=0.2),
    Curve(0.2, amplitude=4, center=0.62, width=0.035),
)
COSTS = (1, 1, 2)
SETUP_COST = 2
POLICIES = ("equal_cost", "equal_samples", "variance_mse", "ocba_cost")


@dataclass
class Moments:
    n: int = 0
    mean: float = 0.0
    m2: float = 0.0

    def add(self, y: float) -> None:
        self.n += 1
        delta = y - self.mean
        self.mean += delta / self.n
        self.m2 += delta * (y - self.mean)

    @property
    def variance(self) -> float:
        return max(0.0, self.m2 / (self.n - 1)) if self.n > 1 else 0.0


def ocba_cost_weights(means, variances, costs):
    """Target *credit*, not replication, ratios; Jia (2012), Eqs. (3)-(4).

    Non-best: r_i = variance_i * cost_i / gap_i**2.
    Best: r_b = sqrt(variance_b * cost_b * sum(r_i**2/(variance_i*cost_i))).
    Floors only stabilize ties/zero empirical variances, not hidden-peak discovery.
    No evaluator truth, curve parameters, or true variances enter this function.
    """
    k = len(means)
    if k < 2 or len(variances) != k or len(costs) != k:
        raise ValueError("Need at least two alternatives and matching vectors")
    if any(c <= 0 for c in costs) or any(v < 0 for v in variances):
        raise ValueError("Costs must be positive and variances nonnegative")
    b = min(range(k), key=lambda i: (means[i], i))
    scale = max(1.0, *(abs(x) for x in means))
    vf = max(1e-14 * scale * scale, max(variances) * 1e-12)
    v = [max(x, vf) for x in variances]
    r = [0.0] * k
    for i in range(k):
        if i != b:
            gap = max(means[i] - means[b], scale * 1e-10)
            r[i] = v[i] * costs[i] / (gap * gap)
    # Normalize before squaring to reduce overflow near ties.
    largest = max(r)
    r = [x / largest for x in r]
    r[b] = math.sqrt(v[b] * costs[b] * sum(
        r[i] ** 2 / (v[i] * costs[i]) for i in range(k) if i != b
    ))
    total = sum(r)
    return [x / total for x in r]


def constrained_targets(weights, lower, total):
    """Proportional credit targets with sunk-spend lower bounds (water filling)."""
    if total < sum(lower) - 1e-9:
        raise ValueError("Cannot recover spent credits")
    active = set(range(len(weights)))
    target = [0.0] * len(weights)
    remaining = total
    while active:
        mass = sum(weights[i] for i in active)
        proposal = {i: remaining * weights[i] / mass for i in active}
        fixed = [i for i in active if proposal[i] < lower[i]]
        if not fixed:
            for i in active:
                target[i] = proposal[i]
            break
        for i in fixed:
            target[i] = lower[i]
            remaining -= lower[i]
            active.remove(i)
    return target


@dataclass(frozen=True)
class Scenario:
    name: str
    curves: tuple[Curve, ...]
    gaussian_sd: float | None = None

    @property
    def truth(self):
        return [c.integral() for c in self.curves]


def scenarios():
    # Fixed design before running experiments: all assignments of three means.
    result = [Scenario("original", ORIGINAL)]
    for means in itertools.permutations((0.50, 0.55, 0.90)):
        shifted = tuple(replace(c, offset=c.offset + m - c.integral())
                        for c, m in zip(ORIGINAL, means))
        name = "shifted_" + "_".join(f"{m:.2f}" for m in means)
        result.append(Scenario(name, shifted))
    # Sanity control only, not a scientific curve instance: Gaussian observations.
    result.append(Scenario("gaussian_control", tuple(Curve(m) for m in (0.50, 0.55, 0.90)), 0.15))
    return result


class SamplingOracle:
    """Trusted in-process environment; not a security sandbox for untrusted code."""

    def __init__(self, scenario, seed, budget, costs=COSTS):
        self._scenario = scenario
        self.budget, self.costs = budget, tuple(costs)
        self.spent = 0
        self.counts = [0] * len(costs)
        self._rngs = []
        for i in range(len(costs)):
            key = f"ocba-pilot-v1/{scenario.name}/{seed}/{i}".encode()
            self._rngs.append(random.Random(int.from_bytes(hashlib.sha256(key).digest(), "big")))

    def sample(self, i):
        charge = self.costs[i] + (SETUP_COST if self.counts[i] == 0 else 0)
        if self.spent + charge > self.budget:
            raise ValueError("Budget exceeded")
        curve = self._scenario.curves[i]
        if self._scenario.gaussian_sd is None:
            value = curve.value(self._rngs[i].random())
        else:
            value = self._rngs[i].gauss(curve.integral(), self._scenario.gaussian_sd)
        self.spent += charge
        self.counts[i] += 1
        return value, charge


def run_sampling(scenario, seed, budget, policy, warmup=5, costs=COSTS, trace=False):
    if policy not in POLICIES or warmup < 2:
        raise ValueError("Unknown policy or insufficient warmup")
    if budget < SETUP_COST * len(costs) + warmup * sum(costs):
        raise ValueError("Budget cannot pay for the common warmup")
    oracle = SamplingOracle(scenario, seed, budget, costs)
    moments = [Moments() for _ in costs]
    history = []

    def take(i, phase):
        y, charge = oracle.sample(i)
        moments[i].add(y)
        if trace:
            history.append({"arm": i, "value": y, "charge": charge,
                            "spent": oracle.spent, "phase": phase,
                            "counts": [m.n for m in moments],
                            "means": [m.mean for m in moments]})

    for _ in range(warmup):
        for i in range(len(costs)):
            take(i, "warmup")
    while True:
        affordable = [i for i, c in enumerate(costs) if oracle.spent + c <= budget]
        if not affordable:
            break
        if policy == "equal_cost":
            i = min(affordable, key=lambda j: (moments[j].n * costs[j], j))
        elif policy == "equal_samples":
            i = min(affordable, key=lambda j: (moments[j].n, j))
        elif policy == "variance_mse":
            # Plug-in one-step decrease of sum Var(sample_mean) per credit.
            # An MSE-oriented heuristic, NOT an optimal MAE controller or OCBA.
            i = max(affordable, key=lambda j: (
                moments[j].variance / (moments[j].n * (moments[j].n + 1) * costs[j]), -j))
        else:
            weights = ocba_cost_weights([m.mean for m in moments],
                                        [m.variance for m in moments], costs)
            lower = [m.n * c for m, c in zip(moments, costs)]
            # Recompute on a small fixed two-credit lookahead; spent work cannot
            # be undone. Take one affordable replication, then update evidence.
            target = constrained_targets(weights, lower,
                min(budget - SETUP_COST * len(costs), sum(lower) + max(costs)))
            i = max(affordable, key=lambda j: ((target[j] - lower[j]) / costs[j], -j))
        take(i, "allocation")
    estimates = [m.mean for m in moments]
    # Reference truth is read ONLY after the policy has finished.
    truth = scenario.truth
    chosen = min(range(len(costs)), key=lambda j: (estimates[j], j))
    best = min(range(len(costs)), key=lambda j: truth[j])
    result = {"scenario": scenario.name, "seed": seed, "budget": budget,
              "policy": policy, "warmup": warmup, "spent": oracle.spent,
              "counts": [m.n for m in moments], "estimates": estimates,
              "chosen": chosen, "correct": int(chosen == best),
              "regret": truth[chosen] - truth[best],
              "mae": statistics.mean(abs(a - b) for a, b in zip(estimates, truth))}
    if trace:
        result["trace"] = history
    return result


@dataclass
class QuadratureOracle:
    curves: tuple[Curve, ...] = ORIGINAL
    costs: tuple[int, ...] = COSTS
    budget: int = 120
    spent: int = 0
    cache: dict = field(default_factory=dict)
    started: set = field(default_factory=set)

    def value(self, i, x):
        if not 0 <= x <= 1:
            raise ValueError("Input outside [0,1]")
        key = (i, x)
        if key not in self.cache:
            charge = self.costs[i] + (0 if i in self.started else SETUP_COST)
            if self.spent + charge > self.budget:
                raise ValueError("Budget exceeded")
            self.cache[key] = self.curves[i].value(x)
            self.started.add(i)
            self.spent += charge
        return self.cache[key]


def trapezoid(oracle, i, n):
    return (sum(oracle.value(i, j / n) for j in range(1, n))
            + (oracle.value(i, 0) + oracle.value(i, 1)) / 2) / n


def run_quadrature(policy, budget=120):
    """Two simple controllers sharing the same nested trapezoid estimator.

    Error proxy |T_n-T_(n/2)|/3 is asymptotic, NOT a certified bound. A feature
    missed on both grids can fool it. This is not a comprehensive quadrature suite.
    """
    if policy not in ("equal_cost", "adaptive_refinement"):
        raise ValueError("Unknown quadrature policy")
    oracle = QuadratureOracle(budget=budget)
    n = [8] * 3
    estimates, proxies = [], []
    for i in range(3):
        old = trapezoid(oracle, i, 4)
        new = trapezoid(oracle, i, 8)
        estimates.append(new)
        proxies.append(abs(new - old) / 3)
    history = [{"intervals": n.copy(), "spent": oracle.spent,
                "estimates": estimates.copy(), "error_proxies": proxies.copy()}]
    while True:
        affordable = [i for i in range(3) if oracle.spent + n[i] * COSTS[i] <= budget]
        if not affordable:
            break
        if policy == "equal_cost":
            i = min(affordable, key=lambda j: ((n[j] + 1) * COSTS[j], j))
        else:
            i = max(affordable, key=lambda j: (proxies[j] / (n[j] * COSTS[j]), -j))
        n[i] *= 2
        new = trapezoid(oracle, i, n[i])
        proxies[i] = abs(new - estimates[i]) / 3
        estimates[i] = new
        history.append({"refined": i, "intervals": n.copy(), "spent": oracle.spent,
                        "estimates": estimates.copy(), "error_proxies": proxies.copy()})
    truth = [c.integral() for c in ORIGINAL]
    return {"policy": policy, "budget": budget, "spent": oracle.spent,
            "intervals": n, "estimates": estimates, "truth": truth,
            "mae": statistics.mean(abs(a - b) for a, b in zip(estimates, truth)),
            "trace": history}


def wilson(successes, n):
    p, z = successes / n, 1.959963984540054
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return center - half, center + half


def summarize(rows):
    groups = {}
    for r in rows:
        key = (r["scenario"], r["budget"], r["policy"])
        groups.setdefault(key, []).append(r)
    summary = []
    for (scenario, budget, policy), group in sorted(groups.items()):
        low, high = wilson(sum(r["correct"] for r in group), len(group))
        summary.append({"scenario": scenario, "budget": budget, "policy": policy,
                        "trials": len(group), "pcs": statistics.mean(r["correct"] for r in group),
                        "pcs_low": low, "pcs_high": high,
                        "mean_regret": statistics.mean(r["regret"] for r in group),
                        "mean_mae": statistics.mean(r["mae"] for r in group),
                        "mean_spent": statistics.mean(r["spent"] for r in group),
                        "mean_counts": [statistics.mean(r["counts"][i] for r in group) for i in range(3)]})
    return summary


def paired_differences(rows):
    by_key = {(r["scenario"], r["budget"], r["seed"], r["policy"]): r for r in rows}
    groups = {}
    for r in rows:
        if r["policy"] != "ocba_cost":
            continue
        for comparator in POLICIES[:-1]:
            other = by_key[(r["scenario"], r["budget"], r["seed"], comparator)]
            groups.setdefault((r["scenario"], r["budget"], comparator), []).append(r["correct"] - other["correct"])
    result = []
    for (scenario, budget, comparator), values in sorted(groups.items()):
        avg = statistics.mean(values)
        half = 1.96 * statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else 0
        result.append({"scenario": scenario, "budget": budget, "comparator": comparator,
                       "pcs_difference": avg, "low": avg - half, "high": avg + half})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=1000)
    parser.add_argument("--budgets", nargs="+", type=int, default=[120, 240, 480])
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "runs" / "ocba_pilot")
    args = parser.parse_args()
    if args.trials < 2 or args.seed_start < 0:
        parser.error("Need at least two trials and a nonnegative seed")
    # Validate before creating outputs or starting partial runs.
    if args.warmup < 2 or min(args.budgets) < SETUP_COST * 3 + args.warmup * sum(COSTS):
        parser.error("Budgets must cover the common warmup")
    args.output.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    rows = []
    trace_examples = []
    for scenario in scenarios():
        for budget in args.budgets:
            for seed in range(args.seed_start, args.seed_start + args.trials):
                for policy in POLICIES:
                    trace = seed == args.seed_start and budget == args.budgets[0]
                    result = run_sampling(scenario, seed, budget, policy, args.warmup, trace=trace)
                    if trace:
                        trace_examples.append({**result})
                        result.pop("trace")
                    rows.append(result)
            print(f"Finished {scenario.name}, budget={budget}, trials={args.trials}", flush=True)
    elapsed = time.perf_counter() - start
    summary = summarize(rows)
    output = {"protocol_version": "ocba-pilot-v1", "python": platform.python_version(),
              "elapsed_seconds": elapsed, "api_calls": 0,
              "trials": args.trials, "budgets": args.budgets, "warmup": args.warmup,
              "seed_start": args.seed_start, "costs": COSTS, "setup_per_arm": SETUP_COST,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "scenarios": [{"name": s.name, "truth": s.truth,
                             "gaussian_sd": s.gaussian_sd} for s in scenarios()],
              "quadrature": [run_quadrature(p) for p in ("equal_cost", "adaptive_refinement")],
              "summary": summary, "paired_pcs_differences": paired_differences(rows)}
    (args.output / "summary.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    (args.output / "trace_examples.json").write_text(json.dumps(trace_examples, indent=2), encoding="utf-8")
    with (args.output / "episodes.jsonl").open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row) + "\n")
    with (args.output / "summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    print(f"{len(rows)} episodes in {elapsed:.2f}s; results: {args.output}")


if __name__ == "__main__":
    main()
