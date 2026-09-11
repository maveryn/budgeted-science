"""Private numerical adapter. References never pass through the public facade."""

from copy import deepcopy
from time import perf_counter

import numpy as np
import scipy
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

from ..agents.records import digest
from ..resource_planning.environment import _rhs as rhs


VERSION = "claim-verification-v1"
INITIAL = (10.0, 5.0)
HORIZON = 8.0
BOUNDS = ((0.6, 1.4), (0.04, 0.12), (0.8, 2.0))


class NumericalFailure(RuntimeError):
    def __init__(self, message, artifact=None):
        super().__init__(message)
        self.artifact = artifact


def number(value, name):
    if isinstance(value, (bool, str, bytes)):
        raise ValueError(f"{name} must be a finite real number")
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{name} must be a finite real number") from None
    if not np.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def output_grid(spacing, phase=0.0):
    spacing, phase = number(spacing, "spacing"), number(phase, "phase")
    if not 0 < spacing <= HORIZON or not 0 <= phase < 1:
        raise ValueError("invalid output schedule")
    # Rounded coordinates avoid duplicate endpoints from floating point arange.
    return sorted(set([0.0, HORIZON] + [
        round(float(t), 12) for t in np.arange(phase * spacing, HORIZON, spacing)
        if 0 <= t <= HORIZON]))


def configuration(method="DOP853", *, dt=None, rtol=1e-9, atol=1e-11, times=None):
    result = {"method": method, "output_times": output_grid(0.01) if times is None else list(times)}
    if method == "Euler":
        result["dt"] = dt
    else:
        result.update(rtol=rtol, atol=atol)
    return validate_config(result)


def validate_config(config):
    if not isinstance(config, dict):
        raise ValueError("configuration must be a mapping")
    method = config.get("method")
    expected = {"method", "output_times"} | ({"dt"} if method == "Euler" else {"rtol", "atol"})
    if method not in ("Euler", "DOP853", "Radau") or set(config) != expected:
        raise ValueError("unsupported numerical configuration")
    times = [number(t, "output time") for t in config["output_times"]]
    if (len(times) < 2 or times[0] != 0 or times[-1] != HORIZON
            or any(a >= b for a, b in zip(times, times[1:]))):
        raise ValueError("output times must increase from 0 to 8")
    result = {"method": method, "output_times": times}
    if method == "Euler":
        dt = number(config["dt"], "dt")
        if not 0 < dt <= HORIZON or abs(round(HORIZON / dt) * dt - HORIZON) > 1e-10:
            raise ValueError("Euler dt must divide the horizon")
        result["dt"] = dt
    else:
        for key in ("rtol", "atol"):
            value = number(config[key], key)
            if not 0 < value < 1:
                raise ValueError("tolerances must lie between 0 and 1")
            result[key] = value
    return result


def validate_theta(theta):
    if isinstance(theta, (str, bytes)) or len(theta) != 3:
        raise ValueError("three parameters required")
    theta = tuple(number(t, "parameter") for t in theta)
    if any(not lo <= t <= hi for t, (lo, hi) in zip(theta, BOUNDS)):
        raise ValueError("parameter outside supported bounds")
    return theta


def _check(values):
    if not np.all(np.isfinite(values)) or np.any(np.asarray(values) < 0):
        raise NumericalFailure("nonfinite or negative population")


def _integrate(theta, config):
    if config["method"] == "Euler":
        dt = config["dt"]
        times = np.arange(round(HORIZON / dt) + 1) * dt
        values = np.empty((len(times), 2))
        values[0] = INITIAL
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            for index in range(len(times) - 1):
                try:
                    values[index + 1] = values[index] + dt * rhs(times[index], values[index], theta)
                    _check(values[index + 1])
                except (NumericalFailure, FloatingPointError) as exc:
                    raise NumericalFailure("Euler integration failed", {
                        "node_times": times[:index + 1].tolist(),
                        "node_values": values[:index + 1].tolist(),
                        "completed_steps": index}) from exc
        def sample(t):
            return np.column_stack([np.interp(t, times, values[:, j]) for j in range(2)])
        return sample, {"node_times": times.tolist(), "node_values": values.tolist(),
                        "interpolation": "piecewise_linear", "rhs_evaluations": len(times) - 1}
    sol = solve_ivp(rhs, (0, HORIZON), INITIAL, args=(theta,), method=config["method"],
                    rtol=config["rtol"], atol=config["atol"], dense_output=True)
    if not sol.success or sol.t[-1] != HORIZON or sol.sol is None:
        raise NumericalFailure("adaptive integration did not complete")
    _check(sol.y)
    internal = {"node_times": sol.t.tolist(), "node_values": sol.y.T.tolist(),
                "interpolation": config["method"] + "_dense", "rhs_evaluations": sol.nfev,
                "segments": []}
    # Retain complete interpolant coefficients, not Python solver objects.
    for segment in sol.sol.interpolants:
        item = {}
        for key in ("t_old", "t", "h", "y_old", "F", "Q", "order"):
            if hasattr(segment, key):
                value = getattr(segment, key)
                item[key] = value.tolist() if isinstance(value, np.ndarray) else (
                    value.item() if isinstance(value, np.generic) else value)
        internal["segments"].append(item)
    return lambda t: np.asarray(sol.sol(t)).T, internal


def solve(theta, config):
    theta, config = validate_theta(theta), validate_config(config)
    start = perf_counter()
    sample, internal = _integrate(theta, config)
    values = sample(config["output_times"])
    _check(values)
    if values.shape != (len(config["output_times"]), 2):
        raise NumericalFailure("invalid output shape")
    return {"status": "success", "config": config, "times": config["output_times"],
            "values": values.tolist(), "internal": internal,
            "seconds": perf_counter() - start, "solver_version": VERSION}


def peak(run):
    if run.get("status") != "success":
        raise ValueError("a successful run is required")
    values = np.asarray(run["values"])
    index = int(np.argmax(values[:, 0]))
    return {"q": float(values[index, 0]), "time": float(run["times"][index]),
            "samples": len(run["times"]), "definition": "maximum of stored x samples"}


def reported_value(run):
    return float(format(peak(run)["q"], ".10g"))


def reference(theta):
    theta = validate_theta(theta)
    candidates, artifacts = [], []
    for method in ("DOP853", "Radau"):
        config = configuration(method, rtol=1e-11, atol=1e-13)
        sample, internal = _integrate(theta, config)
        for size in (4097, 8193):
            times = np.linspace(0, HORIZON, size)
            states = sample(times)
            _check(states)
            derivatives = np.array([rhs(t, y, theta)[0] for t, y in zip(times, states)])
            extrema = [0.0, HORIZON]
            extrema.extend(float(t) for t, d in zip(times, derivatives) if d == 0)
            for a, b, da, db in zip(times[:-1], times[1:], derivatives[:-1], derivatives[1:]):
                if da * db < 0:
                    extrema.append(brentq(lambda t: rhs(t, sample([t])[0], theta)[0], a, b,
                                          xtol=1e-13))
            values = sample(extrema)[:, 0]
            index = int(np.argmax(values))
            candidates.append({"method": method, "search_points": size,
                               "q": float(values[index]), "time": float(extrema[index])})
        artifacts.append({"config": config, "internal": internal,
                          "times": times.tolist(), "values": states.tolist()})
    q = candidates[0]["q"]
    disagreement = max(abs(item["q"] - q) / abs(q) for item in candidates)
    if disagreement >= 1e-7:
        raise NumericalFailure("independent peak references disagree")
    return {"q": q, "checks": candidates, "max_relative_disagreement": disagreement,
            "artifacts": artifacts, "certified_exact": False}


def cache_key(theta, config):
    return digest({"theta": list(validate_theta(theta)), "config": validate_config(config),
                   "initial": INITIAL, "horizon": HORIZON, "version": VERSION,
                   "numpy": np.__version__, "scipy": scipy.__version__})


class Backend:
    """Optional cross-episode cache; scientific purchase histories live elsewhere."""
    def __init__(self, solver=None):
        self.solver = solve if solver is None else solver
        self.cache = {}

    def get(self, theta, config):
        key = cache_key(theta, config)
        hit = key in self.cache
        if not hit:
            try:
                run = self.solver(theta, config)
            except Exception as exc:
                # Keep failure details private; the public facade returns a generic failure.
                run = {"status": "failed", "config": deepcopy(config),
                       "error": type(exc).__name__ + ": " + str(exc),
                       "partial_artifact": getattr(exc, "artifact", None)}
            self.cache[key] = deepcopy(run)
        return deepcopy(self.cache[key]), hit
