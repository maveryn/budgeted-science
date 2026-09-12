"""2-D advection/diffusion FD and independently assembled reference kernel."""
from dataclasses import asdict, dataclass
from time import perf_counter
import warnings

import numpy as np
from scipy.sparse import coo_matrix, diags, eye, kron
from scipy.sparse.linalg import MatrixRankWarning, spsolve

GRIDS = (8, 16, 32, 64)
MMS_GRIDS = (8, 16, 32)
ORDER_BAND = (1.7, 2.3)
Q_POINT = (.375, .625)
FLAVORS = ("sound", "upwind", "neumann_first")


@dataclass(frozen=True)
class Problem:
    kappa: float
    vx: float
    vy: float
    boundary: str = "dirichlet"

    def __post_init__(self):
        if not all(np.isfinite(v) for v in (self.kappa, self.vx, self.vy)) or self.kappa <= 0:
            raise ValueError("finite coefficients and positive diffusion required")
        if self.boundary not in ("dirichlet", "mixed"):
            raise ValueError("unknown boundary condition")

    def public(self):
        return asdict(self)


PROBLEMS = {"diffusion": Problem(1., 0., 0.),
            "advection": Problem(.2, 1.6, .7),
            "mixed": Problem(.6, .4, -.2, "mixed")}


@dataclass(frozen=True)
class Profile:
    """Positive asymmetric MMS with nonzero boundary values/normal curvature."""
    offset: float = 1.1
    ax: float = .2
    ay: float = .35
    axy: float = .15
    amplitude: float = .45
    fx: float = 1.3
    fy: float = 1.7
    px: float = .2
    py: float = .4

    def evaluate(self, x, y):
        a, b = self.fx*np.pi, self.fy*np.pi
        sx, sy = np.sin(a*x+self.px), np.sin(b*y+self.py)
        cx, cy = np.cos(a*x+self.px), np.cos(b*y+self.py)
        wave = self.amplitude*sx*sy
        u = self.offset+self.ax*x+self.ay*y+self.axy*x*y+wave
        ux = self.ax+self.axy*y+self.amplitude*a*cx*sy
        uy = self.ay+self.axy*x+self.amplitude*b*sx*cy
        lap = -(a*a+b*b)*wave
        return u, ux, uy, lap

    def forcing(self, problem, x, y):
        _, ux, uy, lap = self.evaluate(x, y)
        return -problem.kappa*lap+problem.vx*ux+problem.vy*uy

    def q(self):
        return float(self.evaluate(*Q_POINT)[0])


DIAGNOSTIC = Profile()
STUDY_PROFILES = {
    "diffusion": Profile(amplitude=.8, fx=2.7, fy=2.2, px=.31, py=.17),
    "advection": Profile(amplitude=.8, fx=2.3, fy=1.8, px=.41, py=.27),
    "mixed": Profile(amplitude=.7, fx=1.6, fy=2.4, px=.13, py=.37),
}


def charge_units(n):
    if isinstance(n, bool) or not isinstance(n, int) or n not in GRIDS:
        raise ValueError("grid must be 8, 16, 32, or 64 intervals per axis")
    return (n+1)**2


def inputs(problem, profile, n):
    """Supply forcing and boundary data, never an interior exact solution."""
    charge_units(n)
    axis = np.linspace(0, 1, n+1)
    x, y = np.meshgrid(axis, axis)
    boundary_values = np.zeros_like(x)
    boundary_values[0, :] = profile.evaluate(axis, 0.)[0]
    boundary_values[:, 0] = profile.evaluate(0., axis)[0]
    if problem.boundary == "dirichlet":
        boundary_values[-1, :] = profile.evaluate(axis, 1.)[0]
        boundary_values[:, -1] = profile.evaluate(1., axis)[0]
    data = {"forcing": profile.forcing(problem, x, y), "boundary_values": boundary_values}
    if problem.boundary == "mixed":
        data.update(right_derivative=profile.evaluate(1., axis)[1],
                    top_derivative=profile.evaluate(axis, 1.)[2])
    return data


def assemble(problem, n, data, flavor="sound"):
    """Loop-based audited assembly; outward *derivative*, not heat flux, BCs.

    Left/bottom Dirichlet conditions win at their mixed corners. Top-right uses
    the sum of the two Neumann equations. No exact corner value is injected.
    """
    charge_units(n)
    if flavor not in FLAVORS:
        raise ValueError("unknown numerical kernel")
    h, width = 1./n, n+1
    rhs = np.asarray(data["forcing"], dtype=float).ravel().copy()
    rows, cols, vals = [], [], []

    def row(index, entries):
        for col, value in entries.items():
            if value:
                rows.append(index); cols.append(col); vals.append(value)

    for j in range(width):
        for i in range(width):
            r = j*width+i
            if i == 0 or j == 0 or (problem.boundary == "dirichlet" and (i == n or j == n)):
                row(r, {r: 1.}); rhs[r] = data["boundary_values"][j, i]
            elif i == n or j == n:
                entries, value = {}, 0.
                for active, stride, derivative in ((i == n, 1, data["right_derivative"][j]),
                                                    (j == n, width, data["top_derivative"][i])):
                    if active:
                        weights = (1., -1.) if flavor == "neumann_first" else (1.5, -2., .5)
                        for distance, weight in enumerate(weights):
                            c = r-distance*stride
                            entries[c] = entries.get(c, 0.)+weight/h
                        value += derivative
                row(r, entries); rhs[r] = value
            else:
                d = problem.kappa/h**2
                entries = {r: 4*d, r-1: -d, r+1: -d, r-width: -d, r+width: -d}
                for velocity, stride in ((problem.vx, 1), (problem.vy, width)):
                    if flavor == "upwind":
                        entries[r] += abs(velocity)/h
                        c = r-stride if velocity >= 0 else r+stride
                        entries[c] -= abs(velocity)/h
                    else:
                        entries[r+stride] += velocity/(2*h)
                        entries[r-stride] -= velocity/(2*h)
                row(r, entries)
    return coo_matrix((vals, (rows, cols)), shape=(width**2, width**2)).tocsr(), rhs


def independent_assemble(problem, n, data):
    """Separate tensor assembly of the intended operator; no fault flags/MMS u*."""
    charge_units(n)
    w = n+1
    d2 = diags([np.ones(w-1), -2*np.ones(w), np.ones(w-1)], [-1, 0, 1])*n*n
    d1 = diags([-np.ones(w-1), np.ones(w-1)], [-1, 1])*(n/2)
    a = (-problem.kappa*(kron(eye(w), d2)+kron(d2, eye(w)))
         +problem.vx*kron(eye(w), d1)+problem.vy*kron(d1, eye(w))).tolil()
    b = np.asarray(data["forcing"], dtype=float).ravel().copy()
    boundary_nodes = sorted(set(range(w)) | set(range(0, w*w, w)) |
                            set(range(n, w*w, w)) | set(range(n*w, w*w)))
    for r in boundary_nodes:
        j, i = divmod(r, w)
        a.rows[r], a.data[r] = [], []
        if i == 0 or j == 0 or problem.boundary == "dirichlet":
            a[r, r] = 1.
            b[r] = data["boundary_values"][j, i]
        else:
            b[r] = 0.
            if i == n:
                a[r, r] += 1.5*n; a[r, r-1] = -2*n; a[r, r-2] = .5*n
                b[r] += data["right_derivative"][j]
            if j == n:
                a[r, r] += 1.5*n; a[r, r-w] = -2*n; a[r, r-2*w] = .5*n
                b[r] += data["top_derivative"][i]
    return a.tocsr(), b


def solve(problem, profile, n, flavor="sound", kernel="audited"):
    start = perf_counter()
    units = charge_units(n)
    if flavor not in FLAVORS or kernel not in ("audited", "independent"):
        raise ValueError("unknown kernel")
    data = inputs(problem, profile, n)
    a, b = independent_assemble(problem, n, data) if kernel == "independent" else assemble(problem, n, data, flavor)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", MatrixRankWarning)
            u = spsolve(a, b)
        if not np.all(np.isfinite(u)):
            raise FloatingPointError("nonfinite solution")
        field = u.reshape((n+1, n+1))
        result = {"status": "complete", "grid": n,
                  "q": float(field[int(Q_POINT[1]*n), int(Q_POINT[0]*n)]), "field": field.tolist(),
                  "scaled_residual": float(np.linalg.norm(a@u-b)/max(1., np.linalg.norm(b))),
                  "matrix_nnz": int(a.nnz)}
    except (MatrixRankWarning, FloatingPointError, RuntimeError) as exc:
        result = {"status": "failed", "grid": n, "message": type(exc).__name__}
    return {**result, "work_units": units, "credits": units/289, "seconds": perf_counter()-start}


def errors(result, profile):
    if result["status"] != "complete":
        raise ValueError("incomplete numerical result")
    axis = np.linspace(0, 1, result["grid"]+1)
    x, y = np.meshgrid(axis, axis)
    difference = np.asarray(result["field"])-profile.evaluate(x, y)[0]
    return {"rms_error": float(np.sqrt(np.mean(difference**2))),
            "max_error": float(np.max(np.abs(difference))),
            "q_error": relative_error(result["q"], profile.q())}


def orders(errors):
    if len(errors) != 3 or not all(np.isfinite(e) and e > 1e-12 for e in errors):
        raise ValueError("three finite RMS errors above numerical floor required")
    return [float(np.log2(errors[i]/errors[i+1])) for i in (0, 1)]


def order_pass(values):
    return len(values) == 2 and all(np.isfinite(p) and ORDER_BAND[0] <= p <= ORDER_BAND[1] for p in values)


def relative_error(value, reference):
    if not np.isfinite(value) or not np.isfinite(reference) or reference == 0:
        raise ValueError("finite estimate and nonzero reference required")
    return abs(value-reference)/abs(reference)


def validate():
    checks, convergence = {}, []
    x, y = np.meshgrid(np.linspace(.1, .9, 7), np.linspace(.1, .9, 7))
    eps, derivative_errors, lap_errors = 1e-25, [], []
    for profile in (DIAGNOSTIC, *STUDY_PROFILES.values()):
        u, ux, uy, lap = profile.evaluate(x, y)
        derivative_errors.extend((float(np.max(abs(profile.evaluate(x+1j*eps, y)[0].imag/eps-ux))),
                                  float(np.max(abs(profile.evaluate(x, y+1j*eps)[0].imag/eps-uy)))))
        lap2 = profile.evaluate(x+1j*eps, y)[1].imag/eps+profile.evaluate(x, y+1j*eps)[2].imag/eps
        lap_errors.append(float(np.max(abs(lap2-lap))))
    checks["max_first_derivative_disagreement"] = max(derivative_errors)
    checks["max_laplacian_disagreement"] = max(lap_errors)
    assert max(derivative_errors+lap_errors) < 1e-10
    differences = []
    for family, problem in PROBLEMS.items():
        for flavor in FLAVORS:
            results = [solve(problem, DIAGNOSTIC, n, flavor) for n in GRIDS]
            assert all(r["status"] == "complete" and r["scaled_residual"] < 1e-10 for r in results)
            measurements = [{**{k:v for k,v in r.items() if k != "field"}, **errors(r, DIAGNOSTIC)} for r in results]
            p = orders([r["rms_error"] for r in measurements[:3]])
            if flavor == "sound":
                assert order_pass(p), (family, p)
                assert all(a["rms_error"] > b["rms_error"] for a, b in zip(measurements, measurements[1:]))
                other = solve(problem, DIAGNOSTIC, 32, kernel="independent")
                differences.append(float(np.max(abs(np.asarray(results[2]["field"])-other["field"]))))
            convergence.append({"family": family, "kernel": flavor, "orders": p, "results": measurements})
    checks["independent_assembly_max_disagreement"] = max(differences)
    assert max(differences) < 1e-9
    a = solve(PROBLEMS["diffusion"], DIAGNOSTIC, 16)
    b = solve(PROBLEMS["diffusion"], DIAGNOSTIC, 16, "upwind")
    checks["inactive_upwind_max_difference"] = float(np.max(abs(np.asarray(a["field"])-b["field"])))
    assert checks["inactive_upwind_max_difference"] == 0.
    return {"checks": checks, "convergence": convergence}
