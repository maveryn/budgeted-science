"""Trusted JSON state restoration. Never rerun a physical solver or use pickle."""

from copy import deepcopy
from math import fsum
from threading import RLock

import numpy as np
from scipy.integrate import OdeSolution
from scipy.integrate._ivp.rk import Dop853DenseOutput

from .config import Config
from .environment import Episode, PublicTools, _Trajectory, _SOLVER_KEY, _theta


def trajectory_from_json(data):
    times = np.asarray(data["times"], dtype=float)
    values = np.asarray(data["values"], dtype=float)
    if (times.ndim != 1 or len(times) < 2 or values.shape != (len(times), 2)
            or not np.all(np.isfinite(times)) or not np.all(np.isfinite(values))
            or np.any(np.diff(times) <= 0) or times[0] != 0 or times[-1] != 8):
        raise ValueError("invalid saved complete trajectory")
    if data["method"] == "Euler" and data["interpolation"] == "linear":
        return _Trajectory(times, values)
    if data["method"] != "DOP853" or data["interpolation"] != "dop853_dense":
        raise ValueError("unsupported saved interpolation")
    segments = data["segments"]
    if len(segments) != len(times) - 1:
        raise ValueError("incomplete saved dense trajectory")
    interpolants = []
    for i, segment in enumerate(segments):
        old = np.asarray(segment["y_old"], dtype=float)
        coefficients = np.asarray(segment["F"], dtype=float)
        if (segment["t_old"] != times[i] or segment["t"] != times[i + 1]
                or coefficients.shape != (7, 2) or old.shape != (2,)
                or not np.all(np.isfinite(coefficients)) or not np.all(np.isfinite(old))):
            raise ValueError("invalid dense coefficients")
        interpolants.append(Dop853DenseOutput(times[i], times[i + 1], old, coefficients))
    result = _Trajectory(times, values, OdeSolution(times, interpolants))
    if not np.allclose(result.sample(times), values, atol=1e-11, rtol=1e-12):
        raise ValueError("dense coefficients disagree with saved nodes")
    return result


def export_episode(episode):
    with episode._lock:
        return {"version": 1, "solver_key": list(_SOLVER_KEY), "config": episode._config.public(),
                "theta_true": list(episode._theta_true), "target": episode._target.artifact(),
                "noise_seed": episode._noise_seed,
                "state": episode._state, "submission": episode._submission,
                "ledger": deepcopy(episode._ledger), "observations": deepcopy(list(episode._observations.values())),
                "cache": [{**{k: deepcopy(v) for k, v in item.items() if k != "trajectory"},
                           "trajectory": item["trajectory"].artifact() if item["trajectory"] else None}
                          for item in episode._cache.values()]}


def restore_episode(state, log=None):
    if state["version"] != 1 or state["solver_key"] != list(_SOLVER_KEY):
        raise ValueError("incompatible scientific checkpoint")
    if state["state"] != "active" or state["submission"] is not None:
        raise ValueError("only unsubmitted active scientific states can resume")
    config = Config.from_public(state["config"])
    episode = Episode.__new__(Episode)
    episode._config, episode._theta_true = config, _theta(state["theta_true"], config)
    episode._noise_seed = state.get("noise_seed", 0)
    if isinstance(episode._noise_seed, bool) or not isinstance(episode._noise_seed, int) or episode._noise_seed < 0:
        raise ValueError("invalid saved observation seed")
    episode._log, episode._logging_failed, episode._emitting = None, False, False
    episode._lock, episode._state, episode._submission, episode._abort_reason = RLock(), "active", None, None
    episode._target = trajectory_from_json(state["target"])
    episode._ledger, episode._cache, episode._observations = deepcopy(state["ledger"]), {}, {}
    prices = {"simulate_low": config.costs["low"], "simulate_high": config.costs["high"],
              "measure_target": config.costs["measurement"]}
    paid_ids, charges = set(), []
    for entry in episode._ledger:
        if (entry["kind"] not in prices or entry["charge"] != prices[entry["kind"]]
                or entry["status"] not in ("success", "failed") or entry["record_id"] in paid_ids):
            raise ValueError("ambiguous or invalid saved charge")
        paid_ids.add(entry["record_id"])
        charges.append(entry["charge"])
        if entry["remaining"] != config.budget - fsum(charges) or entry["remaining"] < 0:
            raise ValueError("saved scientific ledger is inconsistent")
    accounted_ids = set()
    for item in state["cache"]:
        cached = deepcopy(item)
        theta = _theta(cached["theta"], config)
        fidelity = cached["fidelity"]
        if fidelity not in ("low", "high") or cached["result_id"] not in paid_ids:
            raise ValueError("unpaid cached simulation")
        key = (theta, fidelity, config._cache_key(), _SOLVER_KEY)
        if key in episode._cache:
            raise ValueError("duplicate cached prediction")
        cached["trajectory"] = trajectory_from_json(item["trajectory"]) if item["trajectory"] else None
        if cached["status"] == "success":
            if cached["trajectory"] is None or not np.array_equal(
                    cached["trajectory"].sample(config.working_times), cached["baseline_values"]):
                raise ValueError("cached predictions disagree with their trajectory")
        elif cached["status"] != "failed" or cached["trajectory"] is not None:
            raise ValueError("invalid cached status")
        accounted_ids.add(cached["result_id"])
        episode._cache[key] = cached
    for observation in state["observations"]:
        record = deepcopy(observation)
        key = (record["variable"], record["time"])
        if (key in episode._observations or key[0] not in ("x", "y") or not 0 <= key[1] <= 8
                or record["status"] not in ("success", "failed")):
            raise ValueError("invalid observation checkpoint")
        if record["charge"] == 0:
            if record["time"] not in (0, 1):
                raise ValueError("unpaid target measurement")
        elif record["record_id"] not in paid_ids:
            raise ValueError("unpaid target measurement")
        else:
            accounted_ids.add(record["record_id"])
        if record["status"] == "success" and not np.isfinite(record["value"]):
            raise ValueError("nonfinite saved observation")
        episode._observations[key] = record
    if accounted_ids != paid_ids or not all((v, t) in episode._observations for v in ("x", "y") for t in (0, 1)):
        raise ValueError("saved purchases or initial evidence are incomplete")
    episode.tools, episode._log = PublicTools(episode), log
    return episode
