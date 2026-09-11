"""CPU-only amplitude/viscosity development trial. No agents or API access.

Run from the repository root after the editable install. Detailed artifacts
contain private evaluator state and must not be used as an agent workspace.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
from time import perf_counter
from uuid import uuid4

import numpy as np
import scipy

from budgeted_science.burgers.budget import BudgetExceeded, Ledger, WORK_PER_CREDIT
from budgeted_science.burgers.cache import SimulationService
from budgeted_science.burgers.config import FORECAST_POSITIONS, SENSOR_POSITIONS, SolverConfig
from budgeted_science.burgers.fitting import PredictionUnavailable
from budgeted_science.burgers.joint_fitting import fit_viscosity_amplitude
from budgeted_science.burgers.observations import ObservationService
from budgeted_science.burgers.reference import ReferenceOracle, reference_values
from budgeted_science.burgers.scoring import score_planning
from budgeted_science.burgers.validate import source_manifest


POLICIES = (
    ("one_sensor_coarse_fit", (2,), 32, 48),
    ("three_sensors_coarse_fit", (0, 1, 2), 32, 48),
    ("one_sensor_medium_fit", (2,), 64, 12),
    ("three_sensors_medium_fit", (0, 1, 2), 64, 12),
)


def run_policy(observations, simulations, ledger, sensors, resolution, limit):
    """Fixed recipe sees purchased evidence, not target parameters or scores."""
    trace, records = [], []
    for sensor in sensors:
        try:
            record = observations.acquire(sensor)[0]
        except BudgetExceeded:
            trace.append({"action": "observe", "sensor_id": sensor,
                          "status": "budget_exhausted", "budget": ledger.status()})
            return {"fit": {"viscosity": None, "initial_amplitude": None,
                            "mean_squared_residual": None, "evaluations": 0,
                            "completed_evaluations": 0, "status": "not_started"},
                    "forecast_status": None, "status": "incomplete",
                    "termination_reason": "acquisition_budget_exhausted",
                    "submitted_profile": None, "budget": ledger.status(), "trace": trace}
        records.append(record)
        trace.append({"action": "observe", "record": record.public(), "budget": ledger.status()})

    def simulate(config):
        result = simulations.run(config)
        trace.append({"action": "simulate", "result": result.public(), "budget": ledger.status()})
        return result

    def predictor(nu, amplitude, acquired):
        result = simulate(SolverConfig(nu, resolution, initial_amplitude=amplitude))
        if result.status != "completed":
            raise PredictionUnavailable(result.status)
        return np.array([result.sensor_record(r.sensor_id) for r in acquired])

    fit = fit_viscosity_amplitude(predictor, records, max_evaluations=limit)
    forecast, submission = None, None
    if fit.viscosity is not None:
        forecast = simulate(SolverConfig(fit.viscosity, 64, "forecast",
                                        initial_amplitude=fit.initial_amplitude))
        if forecast.status == "completed":
            submission = forecast.forecast_profile().tolist()
    return {
        "fit": fit.public(), "forecast_status": None if forecast is None else forecast.status,
        "status": "submitted" if submission is not None else "incomplete",
        "submitted_profile": submission, "budget": ledger.status(), "trace": trace,
    }


def reference_diagnostics():
    agreement, recoverability = [], []
    for nu in (.1, .2, .3):
        for amplitude in (.8, 1.0, 1.2):
            for protocol in ("calibration", "forecast"):
                kwargs = {"initial_amplitude": amplitude}
                positions = SENSOR_POSITIONS + FORECAST_POSITIONS
                a = reference_values(nu, protocol, positions, grid_size=1024, **kwargs)
                b = reference_values(nu, protocol, positions, grid_size=2048, **kwargs)
                agreement.append({"viscosity": nu, "amplitude": amplitude, "protocol": protocol,
                                  "max_abs_difference": float(np.max(np.abs(a - b)))})
    for nu, amplitude in ((.14, .9), (.2, 1.0), (.26, 1.1)):
        observations = ObservationService(
            ReferenceOracle(nu, initial_amplitude=amplitude), Ledger.shared(6), noise_std=0,
        )
        records = tuple(observations.acquire(i)[0] for i in range(3))
        def exact_predictor(candidate_nu, candidate_amplitude, acquired):
            return reference_values(candidate_nu, "calibration", [r.position for r in acquired],
                                    initial_amplitude=candidate_amplitude).T
        fit = fit_viscosity_amplitude(exact_predictor, records, max_evaluations=96)
        recoverability.append({
            "target_viscosity": nu, "target_amplitude": amplitude, "fit": fit.public(),
            "viscosity_error": None if fit.viscosity is None else abs(fit.viscosity - nu),
            "amplitude_error": None if fit.initial_amplitude is None else abs(fit.initial_amplitude - amplitude),
        })
    passed = (all(r["max_abs_difference"] < 1e-7 for r in agreement)
              and all(r["fit"]["status"] == "completed" and r["viscosity_error"] < 1e-6
                      and r["amplitude_error"] < 1e-6 for r in recoverability))
    return {"passed": passed, "reference_agreement": agreement, "recoverability": recoverability,
            "qualification": "Noise-free reference-access recoverability, not a matched restricted-tool baseline."}


def run_trial(output, *, target_viscosity=.23, target_amplitude=1.1, seed=0,
              noise_std=.01, budget=20):
    # Validate before creating output; reserve no API budget and read no key.
    oracle = ReferenceOracle(target_viscosity, initial_amplitude=target_amplitude)
    ObservationService(oracle, Ledger.shared(budget), seed=seed, noise_std=noise_std)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    started = perf_counter()
    manifest = {
        "kind": "CPU-only two-parameter development smoke, no agent evaluation",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "public": {"viscosity_bounds": [.1, .3], "amplitude_bounds": [.8, 1.2],
                   "calibration_initial_condition": "A*sin(x)",
                   "forecast_initial_condition": "1.5*A*sin(x)",
                   "score_scale": 1.5, "scientific_budget": budget, "record_price": 2,
                   "noise_std": noise_std, "work_per_credit": WORK_PER_CREDIT,
                   "optimizer": "bounded scipy least_squares; public midpoint; diff_step=1e-4",
                   "policies": [dict(name=name, sensors=sensors, fit_resolution=n,
                                     max_predictor_evaluations=limit, forecast_resolution=64)
                                for name, sensors, n, limit in POLICIES]},
        "private_instance": {"target_viscosity": target_viscosity,
                             "target_amplitude": target_amplitude, "seed": seed},
        "versions": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
        "shared_sources": source_manifest(),
        "pilot_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    diagnostics = reference_diagnostics()
    (output / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")
    if not diagnostics["passed"]:
        raise RuntimeError("reference/recoverability check failed; inspect diagnostics.json")
    rows = []
    for name, sensors, resolution, limit in POLICIES:
        ledger = Ledger.shared(budget)
        observations = ObservationService(oracle, ledger, seed=seed, noise_std=noise_std)
        simulations = SimulationService(ledger)
        result = run_policy(observations, simulations, ledger, sensors, resolution, limit)
        score = None if result["submitted_profile"] is None else score_planning(
            result["submitted_profile"], target_viscosity, target_amplitude=target_amplitude,
        )
        result["private_evaluation"] = {"score": score, "reference_profile": oracle.forecast_profile().tolist()}
        artifact = f"{name}.json"
        (output / artifact).write_text(json.dumps(result, indent=2), encoding="utf-8")
        rows.append({"policy": name, "fit": result["fit"], "status": result["status"],
                     "credits_spent": ledger.status()["total_spent"], "score": score,
                     "artifact": artifact})
    summary = {"policies": rows, "wall_seconds": perf_counter() - started}
    (output / "results.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    lines = ["# Two-parameter Burgers CPU trial", "",
             "Development smoke only. No paid model call, agent result, or optimal baseline.", "",
             "| Fixed recipe | Fit status | Predictor calls | Credits | Normalized forecast RMSE |",
             "| --- | --- | ---: | ---: | ---: |"]
    for row in rows:
        error = "incomplete" if row["score"] is None else f'{row["score"]["normalized_profile_rmse"]:.8f}'
        lines.append(f'| {row["policy"]} | {row["fit"]["status"]} | {row["fit"]["evaluations"]} | '
                     f'{row["credits_spent"]:.5f} | {error} |')
    lines += ["", "All recipes forecast at N=64 using their best completed fit. Coarse fits allow 48 predictor",
              "calls; medium fits allow 12, chosen to leave room for prediction on this development instance.",
              "Those different effort caps mean this is not a controlled comparison of resolution alone.",
              "An evaluation-limited fit is not a converged optimizer; its completed forecast remains scoreable.",
              "Scores evaluate actual profiles, not reference predictions at fitted parameters. The scale stays",
              "fixed at 1.5 even when the hidden initial amplitude differs from 1.", "",
              "Reference-access noise-free fitting is only a recoverability diagnostic. It is not exposed to",
              "these numerical policies. A general-purpose coding track must allow lawful Cole-Hopf shortcuts.",
              "This run does not establish greater agent difficulty or a benefit from adaptive planning.", "",
              "See manifest.json, diagnostics.json, results.json and each policy's full numerical trace.", ""]
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--viscosity", type=float, default=.23)
    parser.add_argument("--amplitude", type=float, default=1.1)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--noise", type=float, default=.01)
    parser.add_argument("--budget", type=float, default=20)
    args = parser.parse_args()
    output = args.output or Path("tmp/burgers_two_parameter") / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8])
    run_trial(output, target_viscosity=args.viscosity, target_amplitude=args.amplitude,
              seed=args.seed, noise_std=args.noise, budget=args.budget)
    print((output / "report.md").resolve())


if __name__ == "__main__":
    main()
