"""Reproducible offline numerical validation; no agents, API keys or network.

Run: python -m budgeted_science.burgers.validate
Detailed outputs contain evaluator truth and belong outside an agent workspace.
"""

import argparse
import csv
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import platform
from time import perf_counter

import numpy as np
import scipy

from budgeted_science import __version__
from .budget import Ledger, WORK_PER_CREDIT
from .cache import SimulationCache, SimulationService
from .config import (
    FORECAST_POSITIONS, LENGTH, RECORD_TIMES, REFERENCE_VERSION, SENSOR_POSITIONS,
    SOLVER_VERSION, SolverConfig,
)
from .fitting import fit_viscosity
from .numerics import solve_candidate
from .observations import ObservationService
from .reference import ReferenceOracle, reference_values
from .scoring import score_inference, score_planning
from .tools import FixedNumericalPredictor, InferenceTools, PlanningTools


def source_manifest():
    root = Path(__file__).resolve().parent.parent
    hashes = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(root.rglob("*.py"))}
    aggregate = hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"files": hashes, "aggregate_sha256": aggregate}


def contract_smokes():
    """Fixed scripts exercising contracts, not adaptive policies or model banks."""
    results, traces = {}, {}
    for kind in ("planning", "inference"):
        ledger = Ledger.shared(50) if kind == "planning" else Ledger.separate(8, 30)
        observations = ObservationService(ReferenceOracle(0.2), ledger, seed=0)
        simulations = SimulationService(ledger)
        if kind == "planning":
            tools = PlanningTools(observations, simulations, ledger)
        else:
            tools = InferenceTools(observations, {"resolution32_fixture": FixedNumericalPredictor(simulations, 32)}, ledger)
        trace = []

        def call(action, **args):
            output = tools.dispatch(action, **args)
            trace.append({"action": action, "arguments": args, "result": output,
                          "budget_after": tools.budget()})
            return output

        record_id = call("observe", sensor_id=2)[0]["record_id"]
        kwargs = {"record_ids": [record_id], "max_evaluations": 16}
        kwargs.update({"resolution": 32} if kind == "planning" else {"model_id": "resolution32_fixture"})
        fit = call("fit", **kwargs)
        if fit["viscosity"] is None:
            raise RuntimeError("contract smoke produced no complete fit")
        if kind == "planning":
            forecast = call("simulate", viscosity=fit["viscosity"], resolution=64, protocol="forecast")
            if forecast["status"] != "completed":
                raise RuntimeError("contract smoke produced no complete forecast")
            indices = np.rint(np.array(FORECAST_POSITIONS) / LENGTH * 64).astype(int)
            profile = np.array(forecast["fields"])[-1, indices].tolist()
            call("submit", profile=profile)
            score = score_planning(tools.submission, 0.2)
        else:
            call("predict", model_id="resolution32_fixture", viscosity=fit["viscosity"])
            call("submit", viscosity_estimate=fit["viscosity"])
            score = score_inference(tools.submission, 0.2)
        results[kind] = {"fit": fit, "budget": tools.budget(), "private_final_score": score,
                         "description": "scripted interface smoke; not an agent/policy comparison"}
        traces[kind] = trace
    return results, traces


def run_validation(output):
    started = perf_counter()
    timestamp = datetime.now(timezone.utc).isoformat()
    rows, reference_rows, fit_rows = [], [], []
    checks = {}
    profiles = []
    for nu in (0.1, 0.2, 0.3):
        for protocol in ("calibration", "forecast"):
            positions = SENSOR_POSITIONS + FORECAST_POSITIONS
            ref1 = reference_values(nu, protocol, positions, grid_size=1024)
            ref2 = reference_values(nu, protocol, positions, grid_size=2048)
            delta = float(np.max(np.abs(ref1 - ref2)))
            reference_rows.append({"viscosity": nu, "protocol": protocol, "max_abs_difference": delta})
            checks[f"reference_{nu}_{protocol}"] = delta < 1e-7
            truth = ref1[-1, len(SENSOR_POSITIONS):]
            errors = []
            for n in (32, 64, 128):
                result = solve_candidate(SolverConfig(nu, n, protocol))
                indices = np.rint(np.array(FORECAST_POSITIONS) / LENGTH * n).astype(int)
                values = result.fields[-1, indices]
                error = float(np.sqrt(np.mean((values - truth)**2)))
                mass = result.fields.mean(axis=1) * LENGTH
                energy = (result.fields**2).mean(axis=1) * LENGTH / 2
                drift = float(np.max(np.abs(mass - mass[0])))
                energy_increase = float(max(0.0, np.max(np.diff(energy))))
                row = {"viscosity": nu, "protocol": protocol, "resolution": n,
                       "profile_rmse": error, "normalized_profile_rmse": error / 1.5,
                       "work_units": result.work_units, "reference_solve_credits": result.work_units / WORK_PER_CREDIT,
                       "wall_seconds": result.wall_seconds, "mass_drift": drift,
                       "max_energy_increase": energy_increase, "status": result.status}
                rows.append(row)
                errors.append(error)
                checks[f"solver_{nu}_{protocol}_{n}"] = result.status == "completed" and drift < 1e-12 and energy_increase < 1e-12
                for x, actual, target in zip(FORECAST_POSITIONS, values, truth):
                    profiles.append({"viscosity": nu, "protocol": protocol, "resolution": n,
                                     "x": x, "prediction": float(actual), "reference": float(target)})
            checks[f"refinement_{nu}_{protocol}"] = errors[0] > errors[1] > errors[2]
    canonical = solve_candidate(SolverConfig(0.2, 64))
    checks["canonical_credit_normalization"] = canonical.work_units == WORK_PER_CREDIT

    for target in (0.14, 0.20, 0.26):
        ledger = Ledger.shared(10)
        observations = ObservationService(ReferenceOracle(target), ledger, noise_std=0)
        records = tuple(observations.acquire(i)[0] for i in range(3))

        def analytic_predictor(nu, acquired):
            return reference_values(nu, "calibration", [r.position for r in acquired]).T

        fitted = fit_viscosity(analytic_predictor, records)
        error = None if fitted.viscosity is None else abs(fitted.viscosity - target)
        fit_rows.append({"target_viscosity": target, **fitted.public(), "absolute_error": error,
                         "access": "analytic-reference recoverability diagnostic; not a restricted-tool baseline"})
        checks[f"recoverability_{target}"] = fitted.status == "completed" and error is not None and error < 1e-6

    output.mkdir(parents=True, exist_ok=True)
    cache = SimulationCache(output / "cache")
    cache.put(canonical)
    cold = SimulationService(Ledger.shared(Fraction(192, WORK_PER_CREDIT)))
    warm = SimulationService(Ledger.shared(Fraction(192, WORK_PER_CREDIT)), cache)
    a, b = cold.run(canonical.config), warm.run(canonical.config)
    checks["warm_cold_interruption"] = (a.status == b.status == "budget_exhausted"
                                         and cold.ledger.status() == warm.ledger.status()
                                         and np.array_equal(a.fields, b.fields))
    paid = SimulationService(Ledger.shared(1), SimulationCache(output / "cache"))
    first, repeated = paid.run(canonical.config), paid.run(canonical.config)
    checks["backend_charge_and_episode_reuse"] = first.charged_work_units == WORK_PER_CREDIT and repeated.charged_work_units == 0
    smokes, traces = contract_smokes()
    checks["both_contract_smokes"] = all(s["fit"]["viscosity"] is not None for s in smokes.values())
    summary = {
        "generated_utc": timestamp, "passed": bool(all(checks.values())), "checks": checks,
        "versions": {"package": __version__, "python": platform.python_version(),
                     "numpy": np.__version__, "scipy": scipy.__version__, "platform": platform.platform(),
                     "solver": SOLVER_VERSION, "reference": REFERENCE_VERSION},
        "source_manifest": source_manifest(),
        "configuration": {"viscosity_bounds": [0.1, 0.3], "length": LENGTH, "final_time": 1.0,
                          "record_times": RECORD_TIMES, "sensor_positions": SENSOR_POSITIONS,
                          "forecast_positions": FORECAST_POSITIONS, "noise_std_default": 0.01,
                          "record_price_default": 2.0, "work_per_credit": WORK_PER_CREDIT,
                          "score_scale": 1.5},
        "numerical_results": rows, "reference_comparisons": reference_rows,
        "recoverability": fit_rows, "contract_smokes": smokes,
        "total_wall_seconds": perf_counter() - started,
        "limitations": [
            "Controlled trusted-tool foundation; not an arbitrary-code sandbox.",
            "No trained surrogate bank, agent runs, adaptive-allocation advantage or discrepancy-resolution claim.",
            "Fast Cole-Hopf computation is a lawful shortcut; numerical simulation is not intrinsically necessary here.",
            "Credits are an illustrative work/acquisition model, not laboratory dollars or measured FLOPs.",
            "Recoverability checks are noise-free and analytic-access, not a proof of budgeted recovery with imperfect tools.",
            "Different contract-smoke scores are not a comparison of the projects or policies.",
        ],
    }
    for name, data in (("summary.json", summary), ("planning_trace.json", traces["planning"]),
                       ("inference_trace.json", traces["inference"])):
        (output / name).write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    for name, data in (("numerical_results.csv", rows), ("reference_comparisons.csv", reference_rows),
                       ("recoverability.csv", fit_rows), ("profiles.csv", profiles)):
        with (output / name).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    lines = ["# Burgers foundation: generated numerical validation", "", f"Passed: {summary['passed']}", "",
             "Offline validation only. No agent experiments or trained surrogate bank.", "",
             "| Viscosity | Protocol | Grid | Profile RMSE | Work | Credits | Seconds |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for row in rows:
        lines.append(f"| {row['viscosity']} | {row['protocol']} | {row['resolution']} | {row['profile_rmse']:.8f} | "
                     f"{row['work_units']} | {row['reference_solve_credits']:.6f} | {row['wall_seconds']:.6f} |")
    lines += ["", "## Analytic-access recoverability", "",
              "| True viscosity | Fitted viscosity | Absolute error | Predictor calls |",
              "| ---: | ---: | ---: | ---: |"]
    for row in fit_rows:
        lines.append(f"| {row['target_viscosity']} | {row['viscosity']:.12f} | {row['absolute_error']:.3g} | {row['evaluations']} |")
    lines += ["", "## Limitations", ""] + [f"- {item}" for item in summary["limitations"]]
    (output / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("tmp/burgers_foundation"),
                        help="Evaluator-only validation output directory (default: ignored repo tmp directory).")
    args = parser.parse_args()
    summary = run_validation(args.output)
    print(f"Validation {'PASSED' if summary['passed'] else 'FAILED'}: {sum(summary['checks'].values())}/{len(summary['checks'])} checks")
    print(f"18 numerical cases; 3 analytic-access recovery cases; 2 scripted contract smokes; {summary['total_wall_seconds']:.3f} s")
    print(f"Source aggregate SHA-256: {summary['source_manifest']['aggregate_sha256']}")
    print(f"Report: {(args.output / 'results.md').resolve()}")
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
