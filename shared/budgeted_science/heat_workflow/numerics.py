"""Five-point heat solver, literal study analysis, and independent harmonic reference.

This is an independent NumPy/SciPy implementation inspired by SimulCost's
steady-heat example, not a vendored or executed SimulCost solver.
"""

from dataclasses import asdict, dataclass
from time import perf_counter

import numpy as np
from scipy.interpolate import RegularGridInterpolator
from scipy.sparse import diags, eye, kron
from scipy.sparse.linalg import spsolve


@dataclass(frozen=True)
class Problem:
    top: float = 1.0
    bottom: float = 0.0
    left: float = 0.0
    right: float = 0.0

    def __post_init__(self):
        if not all(np.isfinite(v) for v in asdict(self).values()):
            raise ValueError("boundary values must be finite")


@dataclass(frozen=True)
class Config:
    n: int = 33
    relaxation: float = 0.8
    update_tolerance: float = 1e-10
    max_iterations: int = 50000

    def __post_init__(self):
        if type(self.n) is not int or not 5 <= self.n <= 257:
            raise ValueError("grid size must be an integer from 5 through 257")
        if not np.isfinite(self.relaxation) or not 0 < self.relaxation <= 1:
            raise ValueError("weighted Jacobi requires 0 < relaxation <= 1")
        if not np.isfinite(self.update_tolerance) or self.update_tolerance <= 0:
            raise ValueError("update tolerance must be finite and positive")
        if type(self.max_iterations) is not int or self.max_iterations < 1:
            raise ValueError("max_iterations must be a positive integer")


PATCH = (0.1, 0.3, 0.6, 0.8)
TOLERANCE = 0.05


def initial_field(problem, n):
    field = np.zeros((n, n))
    field[:, -1], field[:, 0] = problem.top, problem.bottom
    field[0, :], field[-1, :] = problem.left, problem.right
    field[0, -1] = (problem.left + problem.top) / 2
    field[-1, -1] = (problem.right + problem.top) / 2
    field[0, 0] = (problem.left + problem.bottom) / 2
    field[-1, 0] = (problem.right + problem.bottom) / 2
    return field


def residual_rms(field):
    n = len(field)
    residual = ((field[:-2, 1:-1] + field[2:, 1:-1]
                 + field[1:-1, :-2] + field[1:-1, 2:]
                 - 4 * field[1:-1, 1:-1]) * (n - 1)**2)
    return float(np.sqrt(np.mean(residual**2)))


def solve_jacobi(problem, config, *, deadline_seconds=30):
    start = perf_counter()
    field = initial_field(problem, config.n)
    status, update = "iteration_limit", None
    for iteration in range(1, config.max_iterations + 1):
        old = field.copy()
        mean = (old[:-2, 1:-1] + old[2:, 1:-1]
                + old[1:-1, :-2] + old[1:-1, 2:]) / 4
        field[1:-1, 1:-1] = (config.relaxation * mean
                            + (1 - config.relaxation) * old[1:-1, 1:-1])
        update = float(np.sqrt(np.mean((field - old)**2)))
        if not np.all(np.isfinite(field)):
            status = "numerical_failure"
            break
        if update < config.update_tolerance:
            status = "update_threshold_reached"
            break
        if perf_counter() - start >= deadline_seconds:
            status = "timeout"
            break
    return field, {"method": "weighted_jacobi", "status": status,
                   "iterations": iteration, "update_rms": update,
                   "residual_rms": residual_rms(field),
                   "grid_point_iterations": config.n**2 * iteration,
                   "seconds": perf_counter() - start,
                   "configuration": asdict(config), "boundaries": asdict(problem)}


def solve_direct(problem, n):
    """Independent matrix assembly for the same discrete boundary-value problem."""
    Config(n=n)
    start = perf_counter()
    m = n - 2
    one = diags([-np.ones(m-1), 2*np.ones(m), -np.ones(m-1)],
                [-1, 0, 1], format="csc")
    matrix = kron(eye(m), one, format="csc") + kron(one, eye(m), format="csc")
    rhs = np.zeros((m, m))
    rhs[:, -1] += problem.top
    rhs[:, 0] += problem.bottom
    rhs[0, :] += problem.left
    rhs[-1, :] += problem.right
    field = initial_field(problem, n)
    field[1:-1, 1:-1] = spsolve(matrix, rhs.ravel()).reshape(m, m)
    if not np.all(np.isfinite(field)):
        raise ArithmeticError("nonfinite sparse solution")
    return field, {"method": "sparse_direct", "status": "completed",
                   "n": n, "unknowns": m*m, "matrix_nnz": int(matrix.nnz),
                   "residual_rms": residual_rms(field),
                   "seconds": perf_counter() - start, "boundaries": asdict(problem)}


def patch_mean(field, patch=PATCH):
    """Exactly integrate the bilinear interpolant over a rectangular interior patch."""
    field = np.asarray(field, dtype=float)
    if (field.ndim != 2 or field.shape[0] != field.shape[1]
            or field.shape[0] < 3 or not np.all(np.isfinite(field))):
        raise ValueError("expected a finite square field")
    x0, x1, y0, y1 = patch
    if not 0 < x0 < x1 < 1 or not 0 < y0 < y1 < 1:
        raise ValueError("patch must lie strictly inside the unit square")
    grid = np.linspace(0, 1, len(field))
    x = np.r_[x0, grid[(grid > x0) & (grid < x1)], x1]
    y = np.r_[y0, grid[(grid > y0) & (grid < y1)], y1]
    xx, yy = np.meshgrid(x, y, indexing="ij")
    values = RegularGridInterpolator((grid, grid), field)(np.stack([xx, yy], axis=-1))
    along_y = np.sum((values[:, 1:] + values[:, :-1]) * np.diff(y) / 2, axis=1)
    integral = np.sum((along_y[1:] + along_y[:-1]) * np.diff(x) / 2)
    return float(integral / ((x1-x0) * (y1-y0)))


def analysis_source(transpose=False):
    """Self-contained, inspectable study script. Only repository-owned code is executed."""
    # The generated function is also the function executed to produce the report.
    import inspect
    function = inspect.getsource(patch_mean).replace("patch=PATCH", f"patch={PATCH!r}")
    return ("import json\nfrom pathlib import Path\nimport numpy as np\n"
            "from scipy.interpolate import RegularGridInterpolator\n\n" + function
            + "\ndef analyze(field):\n"
            + ("    field = field.T\n" if transpose else "")
            + "    return patch_mean(field)\n\n"
            + "if __name__ == '__main__':\n"
            + "    with np.load(Path(__file__).with_name('trajectory.npz'), allow_pickle=False) as data:\n"
            + "        result = analyze(data['T'])\n"
            + "    print(json.dumps({'Q': result}))\n")


def analyze_owned_source(source, field):
    # Do not expose this to arbitrary input or use it as an agent-code executor.
    if source not in (analysis_source(False), analysis_source(True)):
        raise ValueError("only the two exact repository-owned analysis templates may execute")
    namespace = {"__name__": "study_analysis"}
    exec(compile(source, "owned-study-analysis.py", "exec"), namespace)
    return namespace["analyze"](field)


def reference_mean(problem=Problem(), patch=PATCH, terms=128):
    """Continuous harmonic Fourier-series patch integral; no numerical PDE solver."""
    if type(terms) is not int or terms < 1:
        raise ValueError("positive integer series length required")
    x0, x1, y0, y1 = patch
    if not 0 < x0 < x1 < 1 or not 0 < y0 < y1 < 1:
        raise ValueError("patch must be interior")
    a = np.arange(1, 2*terms, 2, dtype=float) * np.pi

    def top_integral(x0, x1, y0, y1):
        def cosh_over_sinh(y):
            return np.exp(a*(y-1)) * (1 + np.exp(-2*a*y)) / (-np.expm1(-2*a))
        sx = (np.cos(a*x0) - np.cos(a*x1)) / a
        sy = (cosh_over_sinh(y1) - cosh_over_sinh(y0)) / a
        return float(np.sum(4/a * sx * sy))

    integral = (problem.top * top_integral(x0, x1, y0, y1)
                + problem.bottom * top_integral(x0, x1, 1-y1, 1-y0)
                + problem.right * top_integral(y0, y1, x0, x1)
                + problem.left * top_integral(y0, y1, 1-x1, 1-x0))
    return integral / ((x1-x0) * (y1-y0))


def classify(reported, estimate, tolerance=TOLERANCE):
    if not np.isfinite(reported) or not np.isfinite(estimate) or estimate == 0:
        raise ValueError("finite quantities and a nonzero reference are required")
    if not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("positive finite tolerance required")
    error = abs(reported-estimate) / abs(estimate)
    return {"verdict": "ACCEPT" if error <= tolerance else "REJECT", "relative_error": error}


def validate():
    reference = reference_mean(terms=128)
    agreement = abs(reference - reference_mean(terms=256))
    if agreement > 1e-12:
        raise ArithmeticError("Fourier truncation disagreement")
    rows = []
    for n in (33, 65, 129):
        field, info = solve_direct(Problem(), n)
        value = patch_mean(field)
        rows.append({"n": n, "value": value, "relative_error": abs(value-reference)/reference,
                     "transposed_value": patch_mean(field.T), **info})
    if not all(rows[i+1]["relative_error"] < rows[i]["relative_error"] for i in range(2)):
        raise ArithmeticError("nondecreasing grid errors")
    if rows[-1]["relative_error"] > 0.0002:
        raise ArithmeticError("reference and refined matrix solution disagree")
    return {"reference": reference, "fourier_128_256_difference": agreement, "grid_study": rows,
            "reference_scope": "converged Fourier representation, not a certified interval bound"}
