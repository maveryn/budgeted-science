"""CPU numerical QoIs and independently checked private references.

Work is an explicit proxy: one unit per attempted RHS evaluation plus one per
completed output sample, at 100 units per credit. It is not measured FLOPs.
Euler/RK2 outputs use only their own piecewise-linear numerical interpolant.
The independent reference is for private validation, never numerical sampling.
"""

from collections.abc import Mapping
from math import ceil, isfinite
from numbers import Real
from time import perf_counter

import numpy as np
from scipy.integrate import quad, solve_ivp, trapezoid
from scipy.optimize import brentq

from ..claim_verification.numerics import BOUNDS, HORIZON, INITIAL, rhs, validate_theta


_FIELDS = {"method", "dt", "output_step", "output_offset"}
_REFERENCE_RTOL = 1e-11
_REFERENCE_ATOL = 1e-13
_HEIGHT_TOL = 1e-7
_TIME_TOL = 1e-6
_INTEGRAL_TOL = 1e-7
_SEPARATION = 1e-4
_LOCAL_DISTANCE = 0.02
_LOCAL_DROP = 1e-7


def _number(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    try:
        value = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite real number") from exc
    if not isfinite(value):
        raise ValueError(f"{name} must be a finite real number")
    return value


def _theta(theta):
    if isinstance(theta, (str, bytes, Mapping)):
        raise ValueError("three finite real parameters required")
    try:
        values = tuple(theta)
    except TypeError as exc:
        raise ValueError("three finite real parameters required") from exc
    if len(values) != 3:
        raise ValueError("three finite real parameters required")
    return validate_theta(tuple(_number(value, "parameter") for value in values))


def config(method="Euler", dt=.08, output_step=.08, output_offset=0):
    """Return exactly method/dt/output_step/output_offset, validated and copied.

    ``RK2`` denotes explicit midpoint (two RHS stages). dt must divide the
    eight-unit horizon to floating-point precision. output_offset is a fraction
    of output_step, independently of the integration step.
    """
    if not isinstance(method, str) or method not in ("Euler", "RK2"):
        raise ValueError("method must be Euler or RK2 (explicit midpoint)")
    dt = _number(dt, "dt")
    output_step = _number(output_step, "output_step")
    output_offset = _number(output_offset, "output_offset")
    if not .01 <= dt <= .32:
        raise ValueError("dt must lie in [0.01, 0.32]")
    steps = round(HORIZON / dt)
    if abs(steps * dt - HORIZON) > 16 * np.finfo(float).eps * HORIZON:
        raise ValueError("dt must divide the horizon")
    if not .01 <= output_step <= 2:
        raise ValueError("output_step must lie in [0.01, 2]")
    if not 0 <= output_offset < 1:
        raise ValueError("output_offset must lie in [0, 1)")
    return {"method": method, "dt": dt, "output_step": output_step, "output_offset": output_offset}


def _config(value):
    if not isinstance(value, Mapping) or set(value) != _FIELDS:
        raise ValueError("config must contain exactly method, dt, output_step, output_offset")
    return config(**value)


def output_times(config):
    """Sorted endpoints plus phase * spacing + k * spacing for integer k >= 0."""
    settings = _config(config)
    spacing, phase = settings["output_step"], settings["output_offset"]
    interior = [float(phase * spacing + index * spacing)
                for index in range(ceil(HORIZON / spacing) + 1)]
    return sorted({0.0, HORIZON, *(time for time in interior if 0 < time < HORIZON)})


def quote(config):
    """Full-completion work proxy, not measured FLOPs or a failure charge."""
    settings = _config(config)
    stages = 1 if settings["method"] == "Euler" else 2
    evaluations = stages * round(HORIZON / settings["dt"])
    samples = len(output_times(settings))
    work = evaluations + samples
    return {"rhs_evaluations": evaluations, "output_samples": samples,
            "work": work, "credits": work / 100}


def _population(values, shape=None):
    values = np.asarray(values, dtype=float)
    if shape is not None and values.shape != shape:
        raise ValueError("invalid numerical state shape")
    if not np.all(np.isfinite(values)) or np.any(values < 0):
        raise ValueError("numerical populations must be finite and nonnegative")
    return values


def _sample(times, nodes, values):
    return np.column_stack([np.interp(times, nodes, values[:, column]) for column in range(2)])


def solve(theta, config):
    """Execute validated numerics with actual-work accounting.

    Return keys: status, config, times, values, internal, rhs_evaluations,
    output_samples, work, credits, seconds. internal has node_times/node_values.
    Failed execution returns only completed finite nodes in internal and empty
    times/values. Its output_samples is zero. The RHS call that raises or returns
    invalid data still counts; an unattempted RK2 stage does not. Input errors
    raise ValueError before any numerical execution or timing starts.
    """
    theta, settings = _theta(theta), _config(config)
    requested_times = output_times(settings)
    start = perf_counter()
    steps = round(HORIZON / settings["dt"])
    node_times = np.arange(steps + 1, dtype=float) * settings["dt"]
    node_values = np.empty((steps + 1, 2), dtype=float)
    node_values[0] = INITIAL
    completed, evaluations, samples = 0, 0, 0
    times, values, status = [], [], "failed"

    def evaluate(time, state):
        nonlocal evaluations
        evaluations += 1
        derivative = np.asarray(rhs(time, state, theta), dtype=float)
        if derivative.shape != (2,) or not np.all(np.isfinite(derivative)):
            raise ValueError("RHS returned an invalid derivative")
        return derivative

    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            for index in range(steps):
                state, time = node_values[index], node_times[index]
                dt = settings["dt"]
                first = evaluate(time, state)
                if settings["method"] == "Euler":
                    candidate = state + dt * first
                else:
                    midpoint = _population(state + .5 * dt * first, (2,))
                    candidate = state + dt * evaluate(time + .5 * dt, midpoint)
                node_values[index + 1] = _population(candidate, (2,))
                completed += 1
            sampled = _population(_sample(requested_times, node_times, node_values),
                                  (len(requested_times), 2))
        times, values = requested_times, sampled.tolist()
        samples, status = len(times), "success"
    except Exception:
        # Partial output sampling is not delivered or charged as completed data.
        # Interrupts such as KeyboardInterrupt still belong to the outer runner.
        pass
    work = evaluations + samples
    return {"status": status, "config": settings, "times": times, "values": values,
            "internal": {"node_times": node_times[:completed + 1].tolist(),
                         "node_values": node_values[:completed + 1].tolist()},
            "rhs_evaluations": evaluations, "output_samples": samples,
            "work": work, "credits": work / 100, "seconds": perf_counter() - start}


def qois(run):
    """Peak height, earliest stored-sample argmax time, and trapezoidal x integral.

    This deliberately uses stored outputs, including their actual unequal time
    intervals. A successful status and finite, nonnegative data are required.
    """
    if not isinstance(run, Mapping) or run.get("status") != "success":
        raise ValueError("QoIs require a successful run")
    try:
        times = np.asarray(run["times"], dtype=float)
        values = _population(run["values"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError("run must contain finite nonnegative time/population data") from exc
    if (times.ndim != 1 or len(times) < 2 or values.shape != (len(times), 2)
            or not np.all(np.isfinite(times)) or np.any(times < 0)
            or np.any(times > HORIZON) or np.any(np.diff(times) <= 0)):
        raise ValueError("times must increase within the horizon and match two population columns")
    index = int(np.argmax(values[:, 0]))
    try:
        with np.errstate(over="raise", invalid="raise"):
            cumulative = float(trapezoid(values[:, 0], times))
    except FloatingPointError as exc:
        raise ValueError("cumulative QoI is not finite") from exc
    if not isfinite(cumulative) or cumulative < 0:
        raise ValueError("cumulative QoI must be finite and nonnegative")
    return {"peak_height": float(values[index, 0]), "peak_time": float(times[index]),
            "cumulative": cumulative}


def _augmented_rhs(time, state, theta):
    return np.r_[rhs(time, state[:2], theta), state[0]]


def _extrema(solution, theta, size):
    times = np.linspace(0, HORIZON, size)
    states = _population(solution.sol(times), (3, size))
    derivatives = np.asarray(rhs(times, states[:2], theta)[0], dtype=float)
    if derivatives.shape != (size,) or not np.all(np.isfinite(derivatives)):
        raise RuntimeError("invalid reference derivative samples")
    relative_range = float(np.ptp(states[0]) / np.max(states[0]))
    roots = []

    def derivative(time):
        return float(rhs(time, solution.sol(time)[:2], theta)[0])

    if relative_range > 1e-12:
        roots.extend(float(times[index]) for index in range(1, size - 1) if derivatives[index] == 0)
        for index in range(size - 1):
            left, right = derivatives[index:index + 2]
            if (left < 0 < right) or (left > 0 > right):
                roots.append(float(brentq(derivative, times[index], times[index + 1], xtol=1e-13)))
    distinct = []
    for time in sorted(roots):
        if 0 < time < HORIZON and (not distinct or time - distinct[-1] > 1e-9):
            distinct.append(time)
    stationary = []
    for time in distinct:
        delta = min(1e-4, time / 2, (HORIZON - time) / 2)
        left, right = derivative(time - delta), derivative(time + delta)
        kind = "maximum" if left > 0 > right else "minimum" if left < 0 < right else "stationary"
        stationary.append({"time": time, "height": float(solution.sol(time)[0]), "kind": kind})
    candidates = [{"time": 0.0, "height": float(solution.sol(0)[0]), "kind": "endpoint"},
                  *stationary,
                  {"time": HORIZON, "height": float(solution.sol(HORIZON)[0]), "kind": "endpoint"}]
    height = max(candidate["height"] for candidate in candidates)
    # Numerically indistinguishable equal maxima get a deterministic earliest time.
    peak = next(candidate for candidate in candidates if height - candidate["height"] <= 5e-12 * height)
    maxima = [point for point in stationary if point["kind"] == "maximum"]
    competitors = [point["height"] for point in candidates
                   if point["kind"] in ("maximum", "endpoint") and abs(point["time"] - peak["time"]) > 1e-9]
    separation = float((height - max(competitors)) / height) if competitors else None
    left_drop = right_drop = None
    if _LOCAL_DISTANCE <= peak["time"] <= HORIZON - _LOCAL_DISTANCE:
        left_drop = float((height - solution.sol(peak["time"] - _LOCAL_DISTANCE)[0]) / height)
        right_drop = float((height - solution.sol(peak["time"] + _LOCAL_DISTANCE)[0]) / height)
    if relative_range <= 1e-12:
        reason = "flat_trajectory"
    elif peak["kind"] != "maximum":
        reason = "endpoint_global_maximum" if peak["kind"] == "endpoint" else "nonisolated_stationary_maximum"
    elif separation is not None and separation < _SEPARATION:
        reason = "competing_maxima"
    elif left_drop is None or right_drop is None:
        reason = "insufficient_interior_margin"
    elif min(left_drop, right_drop) < _LOCAL_DROP:
        reason = "insufficient_local_drop"
    else:
        reason = "unique_well_separated_interior_maximum"
    diagnostics = {"interior_maxima_count": len(maxima), "interior_maxima": maxima,
                   "stationary_points": stationary, "max_abs_dx_dt": float(np.max(np.abs(derivatives))),
                   "relative_x_range": relative_range, "relative_peak_separation": separation,
                   "local_drop_left": left_drop, "local_drop_right": right_drop,
                   "local_distance": _LOCAL_DISTANCE}
    return {"peak_height": height, "peak_time": peak["time"]}, diagnostics, reason


def reference(theta):
    """Independent, private QoI reference with explicit agreement checks.

    Both DOP853 and Radau integrate (x,y,z), z'=x, at rtol=1e-11/atol=1e-13.
    Each dense x trajectory is also integrated independently by quad. Derivative
    roots are bracketed on 4097 and 8193 points; endpoints remain peak candidates.
    Disagreement at or above the stated thresholds raises RuntimeError.

    Return keys: qois, checks, peak_time_eligible, peak_time_reason,
    regime_diagnostics. checks includes comparisons (four method/grid records),
    agreement metrics, thresholds, solver tolerances, and extrema_counts_agree.
    Regime diagnostics describe finite-horizon transients, not asymptotic cycles.
    Only unique interior maxima separated from all competing maxima/endpoints
    by >=1e-4 relative height and dropping >=1e-7 at both +/-0.02 are time-eligible.
    """
    theta = _theta(theta)
    comparisons, diagnostics, reasons, integrals = [], [], [], []
    for method in ("DOP853", "Radau"):
        solution = solve_ivp(_augmented_rhs, (0, HORIZON), (*INITIAL, 0.), args=(theta,),
                             method=method, rtol=_REFERENCE_RTOL, atol=_REFERENCE_ATOL, dense_output=True)
        if (not solution.success or solution.sol is None or solution.t[-1] != HORIZON
                or not np.all(np.isfinite(solution.y)) or np.any(solution.y < 0)):
            raise RuntimeError(f"{method} reference did not complete with valid states")
        cumulative = float(solution.sol(HORIZON)[2])
        quadrature, quad_error = quad(lambda time: float(solution.sol(time)[0]), 0, HORIZON,
                                      epsabs=1e-11, epsrel=1e-11, limit=200)
        if not all(isfinite(value) and value >= 0 for value in (cumulative, quadrature, quad_error)):
            raise RuntimeError("reference cumulative integral is invalid")
        integrals.extend((cumulative, quadrature))
        for size in (4097, 8193):
            peak, diagnostic, reason = _extrema(solution, theta, size)
            comparisons.append({"method": method, "search_points": size,
                                "qois": {**peak, "cumulative": cumulative},
                                "quadrature_cumulative": float(quadrature),
                                "quadrature_error_estimate": float(quad_error),
                                "rhs_evaluations": int(solution.nfev),
                                "interior_maxima_count": diagnostic["interior_maxima_count"]})
            diagnostics.append(diagnostic)
            reasons.append(reason)
    canonical = comparisons[1]["qois"]
    heights = [item["qois"]["peak_height"] for item in comparisons]
    times = [item["qois"]["peak_time"] for item in comparisons]
    height_agreement = (max(heights) - min(heights)) / canonical["peak_height"]
    time_agreement = max(times) - min(times)
    integral_agreement = (max(integrals) - min(integrals)) / canonical["cumulative"]
    quad_agreement = max(abs(item["qois"]["cumulative"] - item["quadrature_cumulative"])
                         / item["qois"]["cumulative"] for item in comparisons)
    if not (height_agreement < _HEIGHT_TOL and time_agreement < _TIME_TOL
            and integral_agreement < _INTEGRAL_TOL):
        raise RuntimeError("independent QoI references disagree beyond the required tolerances")
    counts_agree = len({item["interior_maxima_count"] for item in comparisons}) == 1
    eligible = counts_agree and all(reason == "unique_well_separated_interior_maximum" for reason in reasons)
    reason = ("unstable_extrema_count" if not counts_agree else
              next((item for item in reasons if item != "unique_well_separated_interior_maximum"), reasons[1]))
    checks = {"passed": True, "comparisons": comparisons,
              "peak_height_relative_agreement": float(height_agreement),
              "peak_time_absolute_agreement": float(time_agreement),
              "cumulative_relative_agreement": float(integral_agreement),
              "augmented_vs_quad_relative_agreement": float(quad_agreement),
              "extrema_counts_agree": counts_agree, "rtol": _REFERENCE_RTOL, "atol": _REFERENCE_ATOL,
              "thresholds": {"peak_height_relative": _HEIGHT_TOL, "peak_time_absolute": _TIME_TOL,
                             "cumulative_relative": _INTEGRAL_TOL}}
    return {"qois": canonical, "checks": checks, "peak_time_eligible": eligible,
            "peak_time_reason": reason, "regime_diagnostics": diagnostics[1]}
