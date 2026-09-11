"""Privileged offline numerical diagnostics, never an agent baseline.

Validation uses only the fixed debug target and development seeds 1000..1007.
It requires maximum absolute error below 1e-6 between the production high-fidelity
solver and independent Radau (rtol=1e-10, atol=1e-12), measures low/high discrepancies, and fits rich observations from
multiple starts using the private simulator. All starts and trial diagnostics
are retained, including unsuccessful solves/optimizations. No pilot targets
are generated here and no validation evidence is exposed to a policy.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import time

from budgeted_science.agents.records import RunLog, json_text
from .experiment import DEFAULT_OUTPUT_ROOT, THREAD_LIMITS, _plain, configuration, source_hashes, target_set, versions


def _errors(estimate, theta, tolerance):
    import numpy as np
    values = np.abs(np.asarray(estimate) - theta) / (tolerance * np.asarray(theta))
    return {"normalized_parameter_errors": values.tolist(),
            "parameter_error": float(np.max(values)),
            "score": int(np.all(values <= 1)), "all_success": bool(np.all(values <= 1))}


def _comparison(candidate, reference, initial):
    import numpy as np
    residual = np.asarray(candidate) - reference
    relative = residual / np.maximum(np.abs(reference), 1e-12)
    normalized = residual / np.asarray(initial)
    return {"maximum_absolute_error": float(np.max(np.abs(residual))),
            "rmse": float(np.sqrt(np.mean(residual ** 2))),
            "maximum_relative_error": float(np.max(np.abs(relative))),
            "relative_rmse": float(np.sqrt(np.mean(relative ** 2))),
            "initial_scaled_rmse": float(np.sqrt(np.mean(normalized ** 2))),
            "per_channel_rmse": np.sqrt(np.mean(residual ** 2, axis=0)).tolist()}


def _recover(theta, config, observations, times, starts, max_nfev, emit, *, label):
    """Unbudgeted privileged identifiability check; each start is visible."""
    import numpy as np
    from scipy.optimize import least_squares
    from .environment import _solve_high
    bounds = np.asarray(config.ranges)
    lower, upper = bounds[:, 0], bounds[:, 1]
    runs = []
    for index, start in enumerate(starts):
        trial_history = []
        began = time.monotonic()
        def residual(parameters):
            trajectory = _solve_high(parameters, config)
            predictions = trajectory.sample(times)
            values = ((predictions - observations) / np.asarray(config.initial)).ravel()
            trial = {"theta": parameters.tolist(), "predictions": predictions.tolist(),
                     "residuals": values.tolist(), "squared_residual": float(values @ values),
                     "solver_knots": len(trajectory.times)}
            trial_history.append(trial)
            return values
        record = {"start_index": index, "initial_theta": start.tolist(), "privileged": True}
        try:
            fitted = least_squares(residual, start, bounds=(lower, upper), method="trf",
                                   xtol=1e-10, ftol=1e-10, gtol=1e-10,
                                   max_nfev=max_nfev, x_scale=upper - lower)
            singular = np.linalg.svd(fitted.jac, compute_uv=False)
            record.update(status="completed", optimizer_success=bool(fitted.success),
                          optimizer_status=int(fitted.status), message=str(fitted.message),
                          theta_hat=fitted.x.tolist(), cost=float(fitted.cost),
                          nfev=int(fitted.nfev), njev=int(fitted.njev) if fitted.njev is not None else None,
                          actual_solver_calls=len(trial_history), optimality=float(fitted.optimality),
                          active_mask=fitted.active_mask.tolist(), jacobian_singular_values=singular.tolist(),
                          jacobian_rank=int(np.linalg.matrix_rank(fitted.jac)),
                          residuals=fitted.fun.tolist(), **_errors(fitted.x, theta, config.tolerance))
        except Exception as exc:
            record.update(status="failed", error={"class": type(exc).__name__, "message": str(exc)},
                          actual_solver_calls=len(trial_history))
        record.update(elapsed_seconds=time.monotonic() - began, trials=trial_history)
        runs.append(record)
        emit("recovery_start", observation_design=label, record=record)
    successful = [r for r in runs if r.get("optimizer_success") and r.get("all_success")]
    fitted = [r for r in runs if r["status"] == "completed"]
    exact = [r for r in fitted if np.max(np.abs(r["residuals"])) <= 1e-6]
    spread = None
    if len(exact) >= 2:
        estimates = np.asarray([r["theta_hat"] for r in exact])
        spread = ((estimates.max(axis=0) - estimates.min(axis=0)) / (upper - lower)).tolist()
    return {"label": label, "privileged": True, "baseline": False,
            "observation_times": list(times), "observations": observations.tolist(), "starts": runs,
            "attempted_starts": len(runs), "converged_and_recovered": len(successful),
            "recovered_from_any_start": bool(successful), "recovered_from_all_starts": len(successful) == len(runs),
            "near_exact_fits": len(exact), "near_exact_parameter_spread_fraction_of_box": spread,
            "interpretation": "Uses private exact candidate solves and rich target observations without a budget. "
                              "Tests numerical recoverability, not baseline planning performance."}


def run_validation(config=None, *, starts=8, seed=419, max_nfev=160, sparse_ambiguity=False, log=None):
    os.environ.update(THREAD_LIMITS)
    import numpy as np
    from scipy.integrate import solve_ivp
    from .config import Config
    from .environment import _rhs, _solve_high, _solve_low
    if isinstance(starts, bool) or not isinstance(starts, int) or starts < 2:
        raise ValueError("recoverability requires at least two starts")
    if isinstance(max_nfev, bool) or not isinstance(max_nfev, int) or max_nfev < 1:
        raise ValueError("max_nfev must be a positive integer")
    config = config if config is not None else Config()
    emit = log if log is not None else lambda kind, **data: None
    targets = target_set("debug", config) + target_set("development", config)
    grid = np.linspace(0, 8, 161)
    bounds = np.asarray(config.ranges)
    rng = np.random.default_rng(seed)
    # Shared initial guesses; never seed an optimizer with the private truth.
    start_points = rng.uniform(bounds[:, 0], bounds[:, 1], size=(starts, 3))
    records = []
    for target in targets:
        began = time.monotonic()
        record = {"target_id": target["target_id"], "target_seed": target["target_seed"],
                  "PRIVATE_theta": target["theta"], "times": grid.tolist()}
        emit("validation_target_started", target_id=target["target_id"])
        try:
            high = _solve_high(target["theta"], config)
            high_values = high.sample(grid)
            record["high"] = {"values": high_values.tolist(), "artifact": high.artifact()}
            radau = solve_ivp(_rhs, (0., 8.), config.initial, args=(target["theta"],), method="Radau",
                              rtol=1e-10, atol=1e-12, t_eval=grid, dense_output=True)
            record["radau"] = {"success": bool(radau.success), "status": int(radau.status),
                               "message": str(radau.message), "rtol": 1e-10, "atol": 1e-12,
                               "nfev": int(radau.nfev), "njev": int(radau.njev), "nlu": int(radau.nlu),
                               "times": radau.t.tolist(), "values": radau.y.T.tolist()}
            if not radau.success or radau.y.T.shape != high_values.shape or not np.all(np.isfinite(radau.y)):
                raise RuntimeError("Radau reference did not return a complete finite trajectory")
            record["high_vs_radau"] = _comparison(high_values, radau.y.T, config.initial)
            record["high_vs_radau"]["within_1e_6_absolute"] = record["high_vs_radau"]["maximum_absolute_error"] < 1e-6
            try:
                low = _solve_low(target["theta"], config)
                low_values = low.sample(grid)
                record["low"] = {"status": "completed", "values": low_values.tolist(), "artifact": low.artifact()}
                record["low_vs_high"] = _comparison(low_values, high_values, config.initial)
            except Exception as exc:
                record["low"] = {"status": "failed", "error": {"class": type(exc).__name__, "message": str(exc)},
                                 "artifact": _plain(getattr(exc, "artifact", None))}
                record["low_vs_high"] = None
            rich_times = list(config.working_times)
            def target_emit(kind, **data):
                emit(kind, target_id=target["target_id"], **data)
            record["rich_recoverability"] = _recover(target["theta"], config, high.sample(rich_times), rich_times,
                                                       start_points, max_nfev, target_emit, label="rich_both_channels")
            if sparse_ambiguity:
                record["sparse_ambiguity"] = _recover(target["theta"], config, high.sample([1.]), [1.],
                                                       start_points, max_nfev, target_emit, label="free_observations_t1")
            record["status"] = "completed"
        except Exception as exc:
            record.update(status="failed", error={"class": type(exc).__name__, "message": str(exc)})
        record["elapsed_seconds"] = time.monotonic() - began
        records.append(record)
        emit("validation_target_finished", result=_plain(record))
    numerical_pass = all(r["status"] == "completed"
                         and r["high_vs_radau"]["within_1e_6_absolute"]
                         and r["low"]["status"] == "completed"
                         and r["rich_recoverability"]["recovered_from_any_start"] for r in records)
    return _plain({"schema_version": 1, "privileged": True, "policy_evidence": False,
                   "targets": records, "starts": starts, "seed": seed, "max_nfev": max_nfev,
                   "sparse_ambiguity_enabled": sparse_ambiguity,
                   "complete": len(records) == 9 and numerical_pass, "all_numeric_pass": numerical_pass,
                   "interpretation": "All numerical targets are debug/development only. Exact private solves and "
                                     "rich observations are validation privileges, never an agent baseline."})


def _markdown(result):
    lines = ["# Privileged numerical validation", "", result["interpretation"], "",
             "HF is production DOP853; the independent comparison uses Radau rtol=1e-10, atol=1e-12. "
             "Maximum absolute HF/Radau error must be below 1e-6. Completion also requires finite LF comparisons "
             "and recovery from at least one rich-observation start for every target.", "",
             "| Target | Status | HF/Radau max absolute error | LF/HF relative RMSE | Recovered starts |",
             "|---|---|---:|---:|---:|"]
    for record in result["targets"]:
        def value(comparison, key):
            number = (record.get(comparison) or {}).get(key)
            return "unavailable" if number is None else f"{number:.6g}"
        recovery = record.get("rich_recoverability", {})
        lines.append(f"| {record['target_id']} | {record['status']} | "
                     f"{value('high_vs_radau', 'maximum_absolute_error')} | {value('low_vs_high', 'relative_rmse')} | "
                     f"{recovery.get('converged_and_recovered', 0)}/{recovery.get('attempted_starts', 0)} |")
    lines += ["", "All optimizer starts, trial parameters, predictions, residuals, convergence messages, Jacobian "
              "singular values, solver diagnostics, and available trajectory artifacts are saved in validation.json "
              "and the chronological event log. An unsuccessful optimizer is retained even when its last estimate is close.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--starts", type=int, default=8)
    parser.add_argument("--seed", type=int, default=419)
    parser.add_argument("--max-nfev", type=int, default=160)
    parser.add_argument("--sparse-ambiguity", action="store_true")
    args = parser.parse_args(argv)
    os.environ.update(THREAD_LIMITS)
    from .config import Config
    config = Config()
    log = RunLog(args.output_root, "validation")
    try:
        log.write_json("manifest.json", {"phase": "validation", "configuration": configuration(config),
                                        "source_hashes": source_hashes(), "versions": versions()})
        result = run_validation(config, starts=args.starts, seed=args.seed, max_nfev=args.max_nfev,
                                sparse_ambiguity=args.sparse_ambiguity, log=log.event)
        log.write_json("validation.json", result)
        with (log.path / "validation.md").open("x", encoding="utf-8") as stream:
            stream.write(_markdown(result))
        log.event("validation_finished", complete=result["complete"])
    finally:
        log.close()
    print(json_text({"run": str(log.path), "complete": result["complete"]}))
    return 0 if result["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
