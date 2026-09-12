"""Metered predator-prey integration and a small injected-predictor fitter."""

from copy import deepcopy
from time import perf_counter

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import least_squares

from ..resource_planning.environment import _rhs as rhs

BOUNDS = np.array(((.6, 1.4), (.04, .12), (.8, 2.0)))
SCALE = BOUNDS[:, 1]-BOUNDS[:, 0]
CAL_INITIAL = (10., 5.)
PRED_INITIAL = (20., 2.)
CAL_TIMES = np.arange(.5, 4.01, .5)
PRED_TIMES = np.linspace(0., 24., 241)
WORK_UNIT = 256
METHODS = {
    "dop_loose": {"method": "DOP853", "rtol": 1e-4, "atol": 1e-7},
    "dop_tight": {"method": "DOP853", "rtol": 1e-9, "atol": 1e-11},
    "rk2_0.1": {"method": "RK2", "dt": .1},
    "rk2_0.2": {"method": "RK2", "dt": .2},
    "rk2_0.4": {"method": "RK2", "dt": .4},
    "rk2_0.8": {"method": "RK2", "dt": .8},
}


class WorkExhausted(RuntimeError):
    pass


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def theta(value):
    a = np.asarray(value)
    if a.shape != (3,) or a.dtype.kind not in "fiu" or not np.isfinite(a).all():
        raise ValueError("three finite numeric parameters required")
    a = a.astype(float)
    if np.any(a < BOUNDS[:, 0]) or np.any(a > BOUNDS[:, 1]):
        raise ValueError("parameters outside public bounds")
    return a


def residual(values, data):
    return ((np.asarray(values)-np.asarray(data))/np.asarray(CAL_INITIAL)).ravel()


def solve(parameters, experiment, method="dop_tight", work_limit=10**8):
    parameters = theta(parameters)
    if experiment not in ("calibration", "prediction") or method not in METHODS:
        raise ValueError("unknown experiment or method")
    integer(work_limit, "work_limit")
    initial, times = (CAL_INITIAL, CAL_TIMES) if experiment == "calibration" else (PRED_INITIAL, PRED_TIMES)
    cfg = METHODS[method]
    start, work, last = perf_counter(), 0, None
    def counted(t, y):
        nonlocal work, last
        if work >= work_limit:
            raise WorkExhausted("RHS work cap reached")
        work += 1
        last = {"time": float(t), "state": [float(v) if np.isfinite(v) else None for v in y]}
        result = rhs(t, y, parameters)
        if not np.isfinite(result).all():
            raise FloatingPointError("nonfinite derivative")
        return result
    nodes_t, nodes_y, values, reason = [0.], [list(initial)], None, None
    status = "complete"
    try:
        if cfg["method"] == "RK2":
            dt = cfg["dt"]
            for i in range(round(times[-1]/dt)):
                y = np.asarray(nodes_y[-1])
                first = counted(i*dt, y)
                stage = y+dt*first
                new = .5*(y+stage+dt*counted((i+1)*dt, stage))
                if not np.isfinite(new).all() or np.any(new <= 0):
                    raise FloatingPointError("nonpositive or nonfinite population")
                nodes_t.append((i+1)*dt)
                nodes_y.append(new.tolist())
            a = np.asarray(nodes_y)
            values = np.column_stack([np.interp(times, nodes_t, a[:, i]) for i in range(2)])
        else:
            sol = solve_ivp(counted, (0., float(times[-1])), initial, method="DOP853",
                            rtol=cfg["rtol"], atol=cfg["atol"], dense_output=True)
            nodes_t, nodes_y = sol.t.tolist(), sol.y.T.tolist()
            if not sol.success or sol.t[-1] != times[-1]:
                raise FloatingPointError("adaptive solve incomplete")
            values = sol.sol(times).T
        if not np.isfinite(values).all() or np.any(values <= 0):
            raise FloatingPointError("invalid sampled population")
    except WorkExhausted as exc:
        status, reason = "budget_exhausted", str(exc)
    except (FloatingPointError, OverflowError) as exc:
        status, reason = "failed", str(exc)
    return {"status": status, "reason": reason, "theta": parameters.tolist(),
            "experiment": experiment, "method": method, "config": deepcopy(cfg),
            "times": times.tolist() if status == "complete" else [],
            "values": values.tolist() if status == "complete" else [],
            "q": float(values[-1, 0]) if status == "complete" and experiment == "prediction" else None,
            "work": work, "credits": work/WORK_UNIT, "seconds": perf_counter()-start,
            "nodes": {"times": nodes_t, "values": nodes_y}, "last_rhs_state": last}


def fit_step(start, data, predictor, damping=1e-6):
    """One bounded damped Gauss-Newton update; every prediction is injected.

    Finite differences and line-search candidates are actual solver calls. An
    interrupted action retains its best *completed* evaluated candidate.
    """
    z = (theta(start)-BOUNDS[:, 0])/SCALE
    best, history = None, []
    def evaluate(zz):
        nonlocal best
        pp = BOUNDS[:, 0]+np.clip(zz, 0, 1)*SCALE
        prediction = predictor(pp)
        r = residual(prediction["values"], data)
        item = {"theta": pp.tolist(), "rmse": float(np.sqrt(np.mean(r*r))),
                "result_id": prediction.get("result_id"), "residual": r.tolist()}
        history.append(item)
        if best is None or item["rmse"] < best["rmse"]:
            best = item
        return r
    status = "complete"
    try:
        r = evaluate(z)
        if np.linalg.norm(r) > 1e-9:
            columns = []
            for j in range(3):
                moved = z.copy()
                h = 1e-3 if z[j] <= .999 else -1e-3
                moved[j] += h
                columns.append((evaluate(moved)-r)/h)
            jac = np.column_stack(columns)
            step = np.linalg.solve(jac.T@jac+damping*np.eye(3), -jac.T@r)
            step *= min(1., .35/max(np.linalg.norm(step), 1e-30))
            for fraction in (1., .5, .25):
                rr = evaluate(z+fraction*step)
                if np.dot(rr, rr) < np.dot(r, r):
                    break
    except WorkExhausted:
        status = "budget_exhausted"
    return {"status": status, "best": deepcopy(best), "history": history}


def fit_full(start, data, predictor):
    """Strong bounded least-squares control, with all forward calls metered."""
    history, best = [], None
    def fun(z):
        nonlocal best
        p = BOUNDS[:, 0]+np.clip(z, 0, 1)*SCALE
        prediction = predictor(p)
        r = residual(prediction["values"], data)
        item = {"theta": p.tolist(), "rmse": float(np.sqrt(np.mean(r*r))),
                "result_id": prediction.get("result_id"), "residual": r.tolist()}
        history.append(item)
        if best is None or item["rmse"] < best["rmse"]:
            best = item
        return r
    status = "complete"
    try:
        result = least_squares(fun, (theta(start)-BOUNDS[:, 0])/SCALE, bounds=(0., 1.),
                      diff_step=1e-3, max_nfev=30, ftol=1e-9, xtol=1e-9, gtol=1e-9)
        if not result.success:
            status = "optimizer_limit"
    except WorkExhausted:
        status = "budget_exhausted"
    return {"status": status, "best": deepcopy(best), "history": history}


def reference(parameters):
    """Independent solver checks plus multi-start recovery from informative data.

    This is an empirical recoverability/reference diagnostic, not a theorem of
    global identifiability or an admissible budgeted baseline.
    """
    parameters = theta(parameters)
    def independent(p, initial, times, method):
        # Separate algebraic expression, checked against the existing RHS in tests.
        def function(t, state):
            x, y = state
            return [x*(p[0]-p[1]*y-.01*x), y*(.9*p[1]*x-p[2])]
        solution = solve_ivp(function, (0., float(times[-1])), initial, method=method,
                             rtol=1e-11, atol=1e-13, dense_output=True)
        if not solution.success:
            raise ValueError("reference failure")
        return solution.sol(times).T
    data = independent(parameters, CAL_INITIAL, CAL_TIMES, "DOP853")
    other = independent(parameters, CAL_INITIAL, CAL_TIMES, "Radau")
    prediction = independent(parameters, PRED_INITIAL, PRED_TIMES, "DOP853")
    other_prediction = independent(parameters, PRED_INITIAL, PRED_TIMES, "Radau")
    recovered = []
    for start in ([.5,.5,.5], [.25,.75,.25], [.75,.25,.75]):
        result = least_squares(lambda z: residual(independent(BOUNDS[:, 0]+z*SCALE, CAL_INITIAL, CAL_TIMES, "Radau"), data),
                               start, bounds=(0., 1.), xtol=1e-11, ftol=1e-11, gtol=1e-11, max_nfev=100)
        p = BOUNDS[:, 0]+result.x*SCALE
        recovered.append({"theta": p.tolist(), "relative_parameter_error": float(np.max(np.abs(p-parameters)/parameters)),
                          "normalized_rmse": float(np.sqrt(np.mean(result.fun**2))),
                          "smallest_scaled_jacobian_singular_value": float(np.linalg.svd(result.jac, compute_uv=False)[-1])})
    checks = {"calibration_max_abs": float(np.max(np.abs(data-other))),
              "prediction_max_abs": float(np.max(np.abs(prediction-other_prediction))), "recovered": recovered}
    if max(checks["calibration_max_abs"], checks["prediction_max_abs"]) > 1e-6 or any(r["relative_parameter_error"] > 1e-6 for r in recovered):
        raise ValueError("reference/recoverability commissioning failed")
    fitted = recovered[0]["theta"]
    fitted_q = float(independent(fitted, PRED_INITIAL, PRED_TIMES, "Radau")[-1, 0])
    if abs(fitted_q-prediction[-1, 0])/abs(prediction[-1, 0]) > 1e-6:
        raise ValueError("converged fitted forecast disagrees with generating-system check")
    return {"data": data.tolist(), "fitted_theta": fitted, "q": fitted_q,
            "prediction": prediction.tolist(), "checks": checks}
