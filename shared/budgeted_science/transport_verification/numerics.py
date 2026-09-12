"""Periodic linear transport: finite differences versus independent exact series.

Work is a disclosed proxy, not FLOPs or wall time. Analytic solutions are cheap
for this restricted equation; reference exclusion is a trusted-tool contract.
"""

import math
import time

import numpy as np
from scipy.integrate import quad
from scipy.optimize import brentq, minimize_scalar

T = 1.0
X0 = 0.25
SENSOR = 0.75
WIDTH = 0.045
THRESHOLD = 0.10
WORK_UNIT = 16384
QUANTITIES = ("peak", "arrival", "exposure", "crossing")
SYSTEMS = (
    {"v": 0.6, "D": 0.0005, "k": 0.1},
    {"v": 0.6, "D": 0.003, "k": 0.1},
    {"v": 0.6, "D": 0.015, "k": 0.1},
)


def physical(system):
    if set(system) != {"v", "D", "k"}:
        raise ValueError("expected v, D, k")
    p = {k: float(v) for k, v in system.items()}
    if not all(math.isfinite(v) for v in p.values()) or p["v"] <= 0 or p["D"] <= 0 or p["k"] < 0:
        raise ValueError("finite v,D>0 and k>=0 required")
    return p


def config(nx=64, dt=1/256, spatial_method="centered", temporal_method="RK2", output_dt=1/128):
    if isinstance(nx, bool) or not isinstance(nx, (int, np.integer)) or nx not in (32, 64, 128, 256, 512):
        raise ValueError("nx must be 32,64,128,256,512")
    if spatial_method not in ("upwind", "centered") or temporal_method not in ("Euler", "RK2"):
        raise ValueError("unknown numerical method")
    for value in (dt, output_dt):
        if isinstance(value, bool) or not math.isfinite(float(value)) or float(value) <= 0:
            raise ValueError("positive finite spacings required")
        n = T / float(value)
        if not math.isclose(n, round(n), rel_tol=0, abs_tol=1e-8) or not 4 <= round(n) <= 65536:
            raise ValueError("spacings must divide T, with 4..65536 intervals")
    return {"nx": int(nx), "dt": T/round(T/float(dt)), "spatial_method": spatial_method,
            "temporal_method": temporal_method, "output_dt": T/round(T/float(output_dt))}


def quote(cfg):
    cfg = config(**cfg)
    stages = 1 if cfg["temporal_method"] == "Euler" else 2
    nsteps, outputs = round(T/cfg["dt"]), round(T/cfg["output_dt"]) + 1
    work = cfg["nx"] * (stages*nsteps + outputs)
    return {"work": work, "credits": work/WORK_UNIT, "rhs_evaluations": stages*nsteps,
            "output_fields": outputs}


def amplification(system, cfg):
    """Exact linear von Neumann stability check for this circulant discretization."""
    p, cfg = physical(system), config(**cfg)
    n = cfg["nx"]
    angle = 2*np.pi*np.arange(n)/n
    first = (1-np.exp(-1j*angle))*n if cfg["spatial_method"] == "upwind" else 1j*np.sin(angle)*n
    lam = -p["v"]*first - 4*p["D"]*n*n*np.sin(angle/2)**2 - p["k"]
    z = cfg["dt"]*lam
    g = 1+z if cfg["temporal_method"] == "Euler" else 1+z+z*z/2
    return float(np.max(np.abs(g)))


def validate(system, cfg):
    cfg = config(**cfg)
    if amplification(system, cfg) > 1+1e-12:
        raise ValueError("unstable explicit discretization; reduce dt or change configuration")
    return cfg


def exact_images(system, x, t):
    """Wrapped Gaussian heat kernel, translated and exponentially decayed."""
    p = physical(system)
    x, t = np.broadcast_arrays(np.asarray(x, dtype=float), np.asarray(t, dtype=float))
    variance = WIDTH**2 + 2*p["D"]*t
    delta = x-X0-p["v"]*t
    result = np.zeros_like(delta)
    for winding in range(-6, 7):
        result += np.exp(-(delta+winding)**2/(2*variance))
    return result * WIDTH/np.sqrt(variance)*np.exp(-p["k"]*t)


def exact_fourier(system, x, t, modes=128):
    """Analytic Fourier coefficients, independent of a sampled candidate field."""
    p = physical(system)
    x, t = np.broadcast_arrays(np.asarray(x, dtype=float), np.asarray(t, dtype=float))
    original_shape = x.shape
    x, t = x.ravel(), t.ravel()
    m = np.arange(-modes, modes+1)
    coeff = WIDTH*np.sqrt(2*np.pi)*np.exp(-2*np.pi**2*WIDTH**2*m*m)
    answer = np.empty(len(t))
    for start in range(0, len(t), 256):
        tt, xx = t[start:start+256, None], x[start:start+256, None]
        terms = coeff * np.exp(-(4*np.pi**2*p["D"]*m*m+p["k"])*tt
                               + 2j*np.pi*m*(xx-X0-p["v"]*tt))
        answer[start:start+256] = terms.sum(axis=1).real
    return answer.reshape(original_shape)


def rhs(u, p, cfg):
    left, right = np.roll(u, 1), np.roll(u, -1)
    n = cfg["nx"]
    derivative = (u-left)*n if cfg["spatial_method"] == "upwind" else (right-left)*(n/2)
    return -p["v"]*derivative + p["D"]*(right-2*u+left)*n*n - p["k"]*u


def solve(system, cfg):
    p, cfg = physical(system), validate(system, cfg)
    start = time.perf_counter()
    n, dt = cfg["nx"], cfg["dt"]
    x = np.arange(n)/n
    u = exact_images(p, x, 0)
    times = np.linspace(0, T, round(T/cfg["output_dt"])+1)
    fields, done, evaluations = [u.copy()], 1, 0
    status, reason = "complete", None
    for step in range(round(T/dt)):
        with np.errstate(over="ignore", invalid="ignore"):
            first = rhs(u, p, cfg)
            evaluations += 1
            new = u+dt*first
            if cfg["temporal_method"] == "RK2":
                new = 0.5*(u+new+dt*rhs(new, p, cfg))
                evaluations += 1
        if not np.all(np.isfinite(new)) or np.max(np.abs(new)) > 1e6:
            status, reason = "failed", "nonfinite or divergent field"
            break
        end = (step+1)*dt
        while done < len(times) and times[done] <= end+1e-13:
            weight = float(np.clip((times[done]-step*dt)/dt, 0, 1))
            fields.append((1-weight)*u+weight*new)
            done += 1
        u = new
    a = np.asarray(fields)
    work = n*(evaluations+done)
    return {"status": status, "reason": reason, "config": cfg, "times": times[:done].tolist(),
            "fields": a.tolist(), "sensor": a[:, round(SENSOR*n)].tolist(),
            "rhs_evaluations": evaluations, "work": work, "credits": work/WORK_UNIT,
            "seconds": time.perf_counter()-start,
            "mass": (a.sum(axis=1)/n).tolist(), "minimum": float(a.min())}


def qois(run):
    if run["status"] != "complete":
        raise ValueError("incomplete run cannot estimate a claim")
    t, c = np.asarray(run["times"]), np.asarray(run["sensor"])
    peak = int(np.argmax(c))
    crossing = None
    hits = np.flatnonzero(c >= THRESHOLD)
    if len(hits):
        i = int(hits[0])
        crossing = float(t[0] if i == 0 else t[i-1]+(THRESHOLD-c[i-1])*(t[i]-t[i-1])/(c[i]-c[i-1]))
    return {"peak": float(c[peak]), "arrival": float(t[peak]),
            "exposure": float(np.sum((c[:-1]+c[1:])*np.diff(t)/2)), "crossing": crossing}


def continuous_qois(value, points=4097):
    times = np.linspace(0, T, points)
    c = np.asarray(value(times))
    i = int(np.argmax(c))
    candidates = [(0., float(c[0])), (T, float(c[-1]))]
    for j in np.flatnonzero((c[1:-1] >= c[:-2]) & (c[1:-1] >= c[2:]))+1:
        if c[j] < c[i]*1e-8:
            continue
        fit = minimize_scalar(lambda t: -float(value(t)), bounds=(times[j-1], times[j+1]),
                              method="bounded", options={"xatol": 1e-14})
        candidates.append((float(fit.x), -float(fit.fun)))
    arrival, peak = max(candidates, key=lambda pair: pair[1])
    crossing = None
    hits = np.flatnonzero(c >= THRESHOLD)
    if len(hits):
        j = int(hits[0])
        crossing = 0. if j == 0 else float(brentq(lambda t: float(value(t))-THRESHOLD,
                                               times[j-1], times[j], xtol=1e-13))
    exposure, error = quad(lambda t: float(value(t)), 0, T, epsabs=1e-12, epsrel=1e-12)
    return {"peak": peak, "arrival": arrival, "exposure": float(exposure), "crossing": crossing}, float(error)


def reference(system):
    times = np.linspace(0, T, 4097)
    images = lambda t: exact_images(system, SENSOR, t)
    fourier = lambda t: exact_fourier(system, SENSOR, t, 128)
    a, quadrature_error = continuous_qois(images)
    b, _ = continuous_qois(fourier)
    dense, _ = continuous_qois(images, 8193)
    errors = {q: max(abs(a[q]-b[q]), abs(a[q]-dense[q])) if a[q] is not None and b[q] is not None and dense[q] is not None else None
              for q in QUANTITIES}
    agreement = float(np.max(np.abs(images(times)-fourier(times))))
    modes = float(np.max(np.abs(fourier(times)-exact_fourier(system, SENSOR, times, 256))))
    if agreement > 1e-10 or modes > 1e-10 or any(e is None or e > 1e-7 for e in errors.values()):
        raise ValueError("reference or event eligibility check failed")
    return {"qois": a, "checks": {"image_fourier_max_abs": agreement, "mode_refinement_max_abs": modes,
                                   "qoi_max_abs_differences": errors, "quadrature_estimate": quadrature_error}}
