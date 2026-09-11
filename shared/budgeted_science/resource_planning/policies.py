"""Exactly two policies, using only the public paid-data service.

No import of environment/RHS/reference implementations is allowed here. GP fits
and hypothetical outcomes are analysis of purchased evidence, not solver calls.
"""
import time

import numpy as np
from scipy.stats import qmc

from .emulator import Calibration, GPSettings, check_deadline


def make_design(seed, bounds, times):
    bounds = np.asarray(bounds, float)
    unit = qmc.Sobol(3, scramble=True, seed=seed).random_base2(4)
    theta = bounds[:, 0] + unit * np.diff(bounds, axis=1).ravel()
    midpoint = bounds.mean(axis=1).tolist()
    warm = [{"kind": "simulation", "fidelity": "low", "theta": p}
            for p in [midpoint] + theta[:3].tolist()]
    warm.append({"kind": "simulation", "fidelity": "high", "theta": midpoint})
    rng = np.random.default_rng(seed + 71)
    fixed = [{"kind": "simulation", "fidelity": "low", "theta": p} for p in theta[3:11].tolist()]
    fixed.append({"kind": "simulation", "fidelity": "high", "theta": theta[int(rng.integers(11))].tolist()})
    possible = [(variable, float(t)) for variable in ("x", "y") for t in times if t != 1.]
    variable, at = possible[int(rng.integers(len(possible)))]
    fixed.append({"kind": "observation", "variable": variable, "time": at})
    rng.shuffle(fixed)
    return warm, fixed


def fit_evidence(evidence, config, seed, settings, deadline):
    return Calibration(evidence["simulations"], evidence["observations"], config["bounds"],
                       config["initial"], config["working_times"], seed=seed,
                       settings=settings, deadline=deadline)


def next_candidates(calibration, evidence, config, remaining, seed, step):
    settings = calibration.settings
    bounds = calibration.bounds
    ng = settings.global_candidates
    global_unit = (qmc.Sobol(3, scramble=True, seed=seed + 1009 + step)
                   .random_base2(int(np.ceil(np.log2(ng))))[:ng] if ng else np.empty((0, 3)))
    global_theta = bounds[:, 0] + global_unit * np.diff(bounds, axis=1).ravel()
    rng = np.random.default_rng(seed + 3001 + step)
    # Weighted sampling without replacement using Gumbel keys. Underflowed
    # weights are regularized only for proposing candidates, not inference.
    keys = np.log(np.maximum(calibration.weights, np.finfo(float).tiny)) + rng.gumbel(size=len(calibration.weights))
    selected = (np.argsort(keys)[-settings.posterior_candidates:]
                if settings.posterior_candidates else np.array([], dtype=int))
    theta = np.vstack((global_theta[:settings.global_candidates], calibration.particles[selected]))
    purchased = {(s["fidelity"], tuple(s["theta"])) for s in evidence["simulations"]}
    actions, seen = [], set()
    for candidate in theta:
        for fidelity in ("low", "high"):
            key = (fidelity, tuple(candidate))
            if key in purchased or key in seen or config["costs"][fidelity] > remaining:
                continue
            seen.add(key)
            actions.append({"kind": "simulation", "fidelity": fidelity, "theta": candidate.tolist(),
                            "cost": config["costs"][fidelity]})
    if config["costs"]["measurement"] <= remaining:
        bought = {(o["variable"], o["time"]) for o in evidence["observations"]}
        for variable in ("x", "y"):
            for at in config["working_times"]:
                if (variable, at) not in bought:
                    actions.append({"kind": "observation", "variable": variable, "time": at,
                                    "cost": config["costs"]["measurement"]})
    return actions


def rank_actions(calibration, actions, *, seed, step, deadline=None):
    rng = np.random.default_rng(seed + 7001 + step)
    count = calibration.settings.fantasies
    # Common latent-target and Gaussian draws across all action comparisons.
    indices = rng.choice(len(calibration.weights), count, p=calibration.weights)
    normals = rng.standard_normal((count, 2, len(calibration.times)))
    ranked = []
    for action in actions:
        check_deadline(deadline)
        if action["kind"] == "simulation":
            gain = calibration.simulation_gain(action["theta"], action["fidelity"], indices, normals)
        else:
            channel = {"x": 0, "y": 1}[action["variable"]]
            index = int(np.flatnonzero(np.isclose(calibration.times, action["time"], atol=1e-12, rtol=0))[0])
            gain = calibration.observation_gain(channel, index, indices, normals)
        if not np.isfinite(gain):
            raise FloatingPointError("nonfinite expected uncertainty reduction")
        ranked.append({**action, "expected_gain": float(gain), "gain_per_credit": float(gain / action["cost"])})
    # Do not clip negative gains or turn noisy/nonpositive gain into a stopping rule.
    return sorted(ranked, key=lambda a: a["gain_per_credit"], reverse=True)


def execute(tools, action, times):
    if action["kind"] == "observation":
        result = tools.measure_target(action["variable"], action["time"])
    else:
        method = tools.simulate_low if action["fidelity"] == "low" else tools.simulate_high
        result = method(action["theta"], times)
    if result.get("status") not in ("success", "failed"):
        raise RuntimeError("policy issued a rejected scientific action: " + str(result.get("status")))
    return result


def run_policy(tools, policy="random", seed=0, log=None, deadline=None, settings=None):
    if policy not in ("random", "adaptive"):
        raise ValueError("policy must be random or adaptive")
    settings = settings or GPSettings()
    emit = log or (lambda kind, **data: None)
    started = time.monotonic()
    config = tools.public_config
    if callable(config):
        config = config()
    if policy == "random" and (config["budget"] != 40 or config["costs"] != {"low": 1, "high": 8, "measurement": 12}):
        raise ValueError("the v1 fixed allocation requires budget 40 and prices low=1, high=8, measurement=12")
    # Fix the random design before accessing even the initial target observations.
    warm, fixed = make_design(seed, config["bounds"], config["working_times"])
    emit("policy_plan", policy=policy, seed=seed, warm_start=warm,
         fixed_actions=fixed if policy == "random" else None, gp_settings=settings.to_dict())
    for action in warm:
        check_deadline(deadline)
        execute(tools, action, config["working_times"])
    if policy == "random":
        for action in fixed:
            check_deadline(deadline)
            execute(tools, action, config["working_times"])
        calibration = fit_evidence(tools.evidence(), config, seed, settings, deadline)
        emit("inference", stage="final", **calibration.diagnostics())
    else:
        step = 0
        while True:
            check_deadline(deadline)
            evidence = tools.evidence()
            calibration = fit_evidence(evidence, config, seed, settings, deadline)
            emit("inference", stage=step, **calibration.diagnostics())
            remaining = tools.get_status()["remaining"]
            actions = next_candidates(calibration, evidence, config, remaining, seed, step)
            if not actions:
                break
            ranked = rank_actions(calibration, actions, seed=seed, step=step, deadline=deadline)
            emit("acquisition", step=step, current_uncertainty=calibration.current_uncertainty,
                 actions=ranked, selected=ranked[0], all_nonpositive=all(a["expected_gain"] <= 0 for a in ranked))
            execute(tools, ranked[0], config["working_times"])
            step += 1
    check_deadline(deadline)
    estimate = calibration.estimate()
    result = tools.submit(estimate)
    if result.get("status") != "submitted":
        raise RuntimeError("policy submission was not accepted")
    emit("policy_finished", policy=policy, estimate=estimate, elapsed_seconds=time.monotonic() - started)
    return {"policy": policy, "seed": seed, "submission": result, "inference": calibration.diagnostics()}
