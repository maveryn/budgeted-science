"""Private dynamics, per-episode accounting, evidence tools, and private scoring.

Only give an agent ``episode.tools``. This is a trusted in-process facade, not a
security sandbox against Python introspection. Never give an agent the Episode
or its log callback: private events include the target and numerical artifacts.
No baseline, runner, credential, or API modules are imported here.
"""

from copy import deepcopy
from dataclasses import dataclass
from math import fsum, isfinite
from threading import RLock

import numpy as np
from scipy.integrate import solve_ivp

from .config import Config, _number, _sequence


_HORIZON = 8.0
_LOW_DT = 0.1
_RTOL = 1e-10
_ATOL = 1e-12
_SOLVER_KEY = ("predator-prey-v1", _HORIZON, _LOW_DT, "DOP853", _RTOL, _ATOL)


def _json_arguments(value, seen=None):
    """Preserve caller data for diagnostics without NaNs or arbitrary reprs."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if isfinite(value) else {"type": "float", "value": str(value)}
    if isinstance(value, np.generic):
        return _json_arguments(value.item(), seen)
    if isinstance(value, complex):
        return {"type": "complex", "real": _json_arguments(value.real),
                "imag": _json_arguments(value.imag)}
    if isinstance(value, np.ndarray):
        return _json_arguments(value.tolist(), seen)
    if isinstance(value, (list, tuple, dict)):
        seen = set() if seen is None else seen
        if id(value) in seen:
            return {"type": "cyclic_argument"}
        seen.add(id(value))
        try:
            if isinstance(value, dict):
                if all(isinstance(key, str) for key in value):
                    return {key: _json_arguments(item, seen) for key, item in value.items()}
                return {"type": "mapping", "items": [[_json_arguments(key, seen),
                                                        _json_arguments(item, seen)]
                                                       for key, item in value.items()]}
            return [_json_arguments(item, seen) for item in value]
        finally:
            seen.remove(id(value))
    return {"type": type(value).__name__}


def _rhs(time, state, theta):
    x, y = state
    theta1, theta2, theta3 = theta
    return np.array([theta1 * x - theta2 * x * y - 0.01 * x * x,
                     0.9 * theta2 * x * y - theta3 * y])


def _theta(value, config):
    values = _sequence(value, "theta")
    if len(values) != 3:
        raise ValueError("theta must contain three finite real numbers")
    values = tuple(_number(item, "theta component") for item in values)
    if any(not low <= item <= high for item, (low, high) in zip(values, config.ranges)):
        raise ValueError("theta must lie within the public parameter ranges")
    return values


def _time(value):
    value = _number(value, "time")
    if not 0 <= value <= _HORIZON:
        raise ValueError("time must lie within [0, 8]")
    return value


def _times(values, config):
    if values is None:
        return config.working_times
    values = _sequence(values, "times")
    if not values:
        raise ValueError("times must be nonempty")
    return tuple(_time(value) for value in values)


class _SolveFailure(RuntimeError):
    def __init__(self, message, artifact=None):
        super().__init__(message)
        self.artifact = artifact


@dataclass
class _Trajectory:
    times: np.ndarray
    values: np.ndarray
    dense: object = None

    def sample(self, times):
        times = np.asarray(times, dtype=float)
        if self.dense is None:
            values = np.column_stack([np.interp(times, self.times, self.values[:, column])
                                      for column in range(2)])
        else:
            values = np.asarray(self.dense(times), dtype=float).T
        if values.shape != (len(times), 2) or not np.all(np.isfinite(values)):
            raise _SolveFailure("solver produced invalid samples")
        return values

    def artifact(self):
        """Full Euler nodes or DOP853 knots plus all dense interpolation data."""
        result = {"times": self.times.tolist(), "values": self.values.tolist()}
        if self.dense is None:
            result.update(method="Euler", dt=_LOW_DT, interpolation="linear")
        else:
            result.update(method="DOP853", rtol=_RTOL, atol=_ATOL,
                          interpolation="dop853_dense", segments=[
                              {"t_old": float(segment.t_old), "t": float(segment.t),
                               "h": float(segment.h), "y_old": segment.y_old.tolist(),
                               "F": segment.F.tolist()}
                              for segment in self.dense.interpolants])
        return result


def _solve_low(theta, config):
    times = np.arange(round(_HORIZON / _LOW_DT) + 1, dtype=float) * _LOW_DT
    values = np.empty((len(times), 2), dtype=float)
    values[0] = config.initial
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        for index in range(len(times) - 1):
            try:
                values[index + 1] = values[index] + _LOW_DT * _rhs(times[index], values[index], theta)
                if not np.all(np.isfinite(values[index + 1])) or np.any(values[index + 1] < 0):
                    raise _SolveFailure("Euler trajectory became invalid")
            except Exception as exc:
                artifact = _Trajectory(times[:index + 1], values[:index + 1]).artifact()
                raise _SolveFailure(f"Euler stopped at step {index + 1}: {exc}", artifact) from exc
    return _Trajectory(times, values)


def _solve_high(theta, config):
    result = solve_ivp(_rhs, (0.0, _HORIZON), config.initial, args=(theta,),
                       method="DOP853", rtol=_RTOL, atol=_ATOL, dense_output=True)
    if (not result.success or result.sol is None or result.t[-1] != _HORIZON
            or not np.all(np.isfinite(result.y)) or np.any(result.y < 0)):
        # Failed solver output can contain NaNs; omit them from JSON artifacts.
        artifact = {"method": "DOP853", "message": str(result.message),
                    "times": [float(value) if np.isfinite(value) else None for value in result.t],
                    "values": [[float(value) if np.isfinite(value) else None for value in row]
                               for row in np.asarray(result.y).T]}
        raise _SolveFailure("DOP853 did not produce a complete valid trajectory", artifact)
    return _Trajectory(result.t, result.y.T, result.sol)


class PublicTools:
    """The six allowed free/paid actions plus free evidence/config access.

    ``get_status()`` keys are status, config, spent, remaining, observations,
    simulations, ledger, and submission. Observations include free x/y at t=0,1
    and successful purchased scalars (variable, time, value, charge, remaining,
    record_id, status). Simulations contain successful purchased full solves
    sampled at config.working_times, with columns x,y and rows matching times.
    Every simulation has status, theta, fidelity, times, values, charge,
    remaining, cache_hit, result_id. Failures are visible in the charge ledger.
    Evidence retains each original charge; repeat requests return charge zero.

    ``evidence()`` returns observations and simulations, including failed
    purchased simulations (empty values). ``public_config`` exposes the same
    public settings as get_status()['config']. Both return independent copies.

    Action statuses: success, invalid, unaffordable, failed, closed; submit returns
    submitted on acceptance. Episode status is active, submitted, or aborted.
    Invalid/unaffordable requests return an error without executing or charging.
    """

    __slots__ = ("__episode",)

    def __init__(self, episode):
        self.__episode = episode

    def _call(self, action, arguments, operation):
        episode = self.__episode
        with episode._lock:
            arguments = _json_arguments(arguments)
            episode._emit("tool_call", action=action, arguments=arguments)
            result = operation()
            if isinstance(result, dict) and result.get("status") in ("invalid", "unaffordable", "closed"):
                result["arguments"] = arguments
            episode._emit("tool_result", action=action, result=result)
            return result

    def simulate_low(self, theta, times=None):
        return self._call("simulate_low", {"theta": theta, "times": times},
                          lambda: self.__episode._simulate("low", theta, times))

    def simulate_high(self, theta, times=None):
        return self._call("simulate_high", {"theta": theta, "times": times},
                          lambda: self.__episode._simulate("high", theta, times))

    def measure_target(self, variable, time):
        return self._call("measure_target", {"variable": variable, "time": time},
                          lambda: self.__episode._measure(variable, time))

    def get_status(self):
        return self._call("get_status", {}, self.__episode._status)

    @property
    def public_config(self):
        return self._call("public_config", {}, self.__episode._config.public)

    def evidence(self):
        return self._call("evidence", {}, self.__episode._evidence)

    def compare_cached_candidates(self):
        return self._call("compare_cached_candidates", {}, self.__episode._compare)

    def submit(self, theta_hat):
        return self._call("submit", {"theta_hat": theta_hat}, lambda: self.__episode._submit(theta_hat))


class Episode:
    """Own a private target, independent budget, and cache for one run.

    ``log(kind, **data)`` is an optional trusted synchronous callback. Events:
    episode_started (private target + full reference artifact), simulation
    (public result + full artifact for a new solve, including known partial
    failure output), measurement, rejected, submitted, aborted, and evaluated.
    Artifacts contain every numerical node and HF dense coefficient, so a
    logger can save/reconstruct full trajectories without rerunning the solver.
    Every facade access emits tool_call/tool_result, including free evidence.
    Validated acquisition arguments appear in tool_started before execution;
    a charged event records the reservation and public budget snapshot before
    invoking a solver (the callback owns durable storage). Status reads made
    inside the callback are not recursively logged. Callback exceptions abort the
    episode, preventing unlogged work from resuming. Existing charges/results
    remain committed, and private evaluation remains available after log loss.
    Runtime/API limits belong to the runner, not this environment.
    """

    def __init__(self, theta, config=Config(), log=None):
        if not isinstance(config, Config):
            raise ValueError("config must be a Config")
        if log is not None and not callable(log):
            raise ValueError("log must be callable or None")
        self._config = config
        self._theta_true = _theta(theta, config)
        self._log = log
        self._logging_failed = False
        self._emitting = False
        self._lock = RLock()
        self._state = "active"
        self._submission = None
        self._abort_reason = None
        self._ledger = []
        self._cache = {}
        self._observations = {}
        self._target = _solve_high(self._theta_true, config)
        for time in (0.0, 1.0):
            values = self._target.sample([time])[0]
            for index, variable in enumerate(("x", "y")):
                record = {"variable": variable, "time": time, "value": float(values[index]),
                          "charge": 0.0, "remaining": config.budget,
                          "record_id": f"observation-{len(self._observations) + 1}", "status": "success"}
                self._observations[variable, time] = record
        self.tools = PublicTools(self)
        self._emit("episode_started", theta_true=list(self._theta_true), config=config.public(),
                   target_artifact=self._target.artifact(), observations=list(self._observations.values()))

    @property
    def _spent(self):
        return fsum(entry["charge"] for entry in self._ledger)

    @property
    def _remaining(self):
        return self._config.budget - self._spent

    def _emit(self, kind, **data):
        if self._log is not None and not self._logging_failed and not self._emitting:
            self._emitting = True
            try:
                self._log(kind, **deepcopy(data))
            except Exception:
                self._logging_failed = True
                self._state = "aborted"
                self._abort_reason = "log callback failed"
                raise
            finally:
                self._emitting = False

    def _reject(self, kind, status, error, **fields):
        result = {**fields, "status": status, "error": error,
                  "charge": 0.0, "remaining": self._remaining}
        self._emit("rejected", action=kind, result=result)
        return result

    def _charge(self, kind, record_id, amount):
        entry = {"kind": kind, "record_id": record_id, "charge": amount,
                 "remaining": self._remaining - amount, "status": "pending"}
        self._ledger.append(entry)
        try:
            self._emit("charged", entry=entry, budget_after=self._status())
        except Exception:
            entry["status"] = "logging_failed"
            raise
        return entry

    def _simulate(self, fidelity, theta, times):
        with self._lock:
            kind = f"simulate_{fidelity}"
            fields = {"theta": None, "fidelity": fidelity, "times": [], "values": [],
                      "cache_hit": False, "result_id": None}
            if self._state != "active":
                return self._reject(kind, "closed", "episode is closed", **fields)
            try:
                theta = _theta(theta, self._config)
                fields["theta"] = list(theta)
                times = _times(times, self._config)
                fields["times"] = list(times)
            except ValueError as exc:
                return self._reject(kind, "invalid", str(exc), **fields)
            self._emit("tool_started", action=kind,
                       arguments={"theta": list(theta), "times": list(times), "fidelity": fidelity})
            key = (theta, fidelity, self._config._cache_key(), _SOLVER_KEY)
            cached = self._cache.get(key)
            cache_hit = cached is not None
            charge = 0.0
            artifact = None
            private_error = None
            if cached is None:
                charge = self._config.costs[fidelity]
                if charge > self._remaining:
                    return self._reject(kind, "unaffordable", "insufficient credits", **fields)
                result_id = f"simulation-{len(self._cache) + 1}"
                entry = self._charge(kind, result_id, charge)
                cached = {"result_id": result_id, "theta": list(theta), "fidelity": fidelity,
                          "charge": charge, "remaining": self._remaining, "status": "failed",
                          "trajectory": None, "baseline_values": []}
                # Reserve the cache entry before execution so even failures are charged once.
                self._cache[key] = cached
                try:
                    trajectory = (_solve_low if fidelity == "low" else _solve_high)(theta, self._config)
                    baseline = trajectory.sample(self._config.working_times)
                    trajectory.sample(times)
                    artifact = trajectory.artifact()
                    cached.update(status="success", trajectory=trajectory, baseline_values=baseline.tolist())
                except Exception as exc:
                    private_error = f"{type(exc).__name__}: {exc}"
                    artifact = getattr(exc, "artifact", None)
                entry["status"] = cached["status"]
            result = {**fields, "status": cached["status"], "result_id": cached["result_id"],
                      "charge": charge, "remaining": self._remaining, "cache_hit": cache_hit}
            if cached["status"] == "success":
                result["values"] = cached["trajectory"].sample(times).tolist()
            else:
                result["error"] = "simulation failed"
            self._emit("simulation", result=result, artifact=artifact, error=private_error)
            return result

    def _measure(self, variable, time):
        with self._lock:
            fields = {"variable": variable if isinstance(variable, str) else None,
                      "time": None, "value": None, "record_id": None, "cache_hit": False}
            if self._state != "active":
                return self._reject("measure_target", "closed", "episode is closed", **fields)
            try:
                if not isinstance(variable, str) or variable not in ("x", "y"):
                    raise ValueError("variable must be x or y")
                time = _time(time)
                fields["time"] = time
            except ValueError as exc:
                return self._reject("measure_target", "invalid", str(exc), **fields)
            self._emit("tool_started", action="measure_target", arguments={"variable": variable, "time": time})
            key = variable, time
            if key in self._observations:
                result = {**self._observations[key], "charge": 0.0,
                          "remaining": self._remaining, "cache_hit": True}
                self._emit("measurement", result=result)
                return result
            charge = self._config.costs["measurement"]
            if charge > self._remaining:
                return self._reject("measure_target", "unaffordable", "insufficient credits", **fields)
            record_id = f"observation-{len(self._observations) + 1}"
            entry = self._charge("measure_target", record_id, charge)
            result = {**fields, "status": "success", "record_id": record_id,
                      "charge": charge, "remaining": self._remaining}
            private_error = None
            try:
                result["value"] = float(self._target.sample([time])[0, ("x", "y").index(variable)])
            except Exception as exc:
                result.update(status="failed", error="measurement failed")
                private_error = f"{type(exc).__name__}: {exc}"
            entry["status"] = result["status"]
            self._observations[key] = deepcopy(result)
            self._emit("measurement", result=result, error=private_error)
            return result

    def _evidence(self):
        with self._lock:
            simulations = [
                {key: item[key] for key in ("status", "theta", "fidelity", "charge", "remaining", "result_id")}
                | {"times": list(self._config.working_times), "values": item["baseline_values"],
                   "cache_hit": False}
                for item in self._cache.values()]
            return deepcopy({"simulations": simulations,
                             "observations": [record for record in self._observations.values()
                                              if record["status"] == "success"]})

    def _status(self):
        with self._lock:
            evidence = self._evidence()
            return deepcopy({"status": self._state, "config": self._config.public(),
                             "spent": self._spent, "remaining": self._remaining,
                             "observations": evidence["observations"],
                             "simulations": [item for item in evidence["simulations"]
                                             if item["status"] == "success"], "ledger": self._ledger,
                             "submission": list(self._submission) if self._submission is not None else None})

    def _compare(self):
        """Free ranking using only cached predictions and acquired observations.

        Returns candidates sorted by normalized_rmse (ascending). Each residual
        is (prediction - observation) / (tolerance * abs(observation)); variables
        are positive in this task. Matching observations, their record IDs, and
        predicted values are included. No solver, private target, or score call.
        """
        with self._lock:
            observations = [record for record in self._observations.values() if record["status"] == "success"]
            times = [record["time"] for record in observations]
            candidates = []
            for cached in self._cache.values():
                if cached["status"] != "success":
                    continue
                samples = cached["trajectory"].sample(times)
                predictions = [float(samples[index, ("x", "y").index(record["variable"])])
                               for index, record in enumerate(observations)]
                residuals = [(prediction - record["value"])
                             / (self._config.tolerance * abs(record["value"]))
                             for prediction, record in zip(predictions, observations)]
                candidates.append({"result_id": cached["result_id"], "theta": cached["theta"],
                                   "fidelity": cached["fidelity"],
                                   "normalized_rmse": float(np.sqrt(np.mean(np.square(residuals)))),
                                   "predictions": predictions,
                                   "record_ids": [record["record_id"] for record in observations]})
            candidates.sort(key=lambda candidate: candidate["normalized_rmse"])
            return deepcopy({"status": "success", "candidates": candidates,
                             "observations": observations, "charge": 0.0, "remaining": self._remaining})

    def _submit(self, theta_hat):
        with self._lock:
            if self._state != "active":
                return self._reject("submit", "closed", "episode is closed")
            try:
                theta_hat = _theta(theta_hat, self._config)
            except ValueError as exc:
                return self._reject("submit", "invalid", str(exc))
            self._emit("tool_started", action="submit", arguments={"theta_hat": list(theta_hat)})
            self._submission = theta_hat
            self._state = "submitted"
            result = {"status": "submitted", "theta_hat": list(theta_hat),
                      "charge": 0.0, "remaining": self._remaining}
            self._emit("submitted", result=result)
            return result

    def abort(self, reason):
        """Close an unfinished run from the trusted runner; idempotent."""
        with self._lock:
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError("abort reason must be a nonempty string")
            if self._state == "active":
                self._state = "aborted"
                self._abort_reason = reason
                self._emit("aborted", reason=reason, remaining=self._remaining)
            return {"status": self._state, "remaining": self._remaining}

    def evaluate(self):
        """Private parameter scoring; no runtime evaluation or savings reward.

        ``errors`` are absolute parameter errors divided by tolerance * truth.
        ``successes`` are the three inclusive error <= 1 decisions, and
        ``parameter_error`` is their maximum normalized error. ``success`` and
        binary ``score`` require all three parameters to meet tolerance.
        Boundary slack is only floating-point
        subtraction roundoff. Unsubmitted/aborted runs get zero and null errors.
        Remaining scientific credits are reported independently from the score.
        """
        with self._lock:
            errors = [None, None, None]
            successes = [False, False, False]
            valid = self._state == "submitted" and self._submission is not None
            if valid:
                truth = np.array(self._theta_true)
                estimate = np.array(self._submission)
                absolute = np.abs(estimate - truth)
                scale = self._config.tolerance * truth
                errors_array = absolute / scale
                # theta * 1.1 can subtract to slightly more than 0.1 * theta.
                roundoff = 8 * np.finfo(float).eps * np.maximum(np.abs(estimate), np.abs(truth))
                success_array = absolute <= scale + roundoff
                errors_array = np.where(success_array & (errors_array > 1), 1.0, errors_array)
                errors = errors_array.tolist()
                successes = success_array.tolist()
            result = {"status": self._state, "theta_true": list(self._theta_true),
                      "theta_hat": list(self._submission) if self._submission is not None else None,
                      "errors": errors, "successes": successes,
                      "parameter_error": max(errors) if valid else None,
                      "success": all(successes), "valid": valid,
                      "score": int(all(successes)), "completed_objectives": sum(successes),
                      "all_success": all(successes), "spent": self._spent,
                      "remaining": self._remaining, "abort_reason": self._abort_reason}
            self._emit("evaluated", result=result)
            return result
