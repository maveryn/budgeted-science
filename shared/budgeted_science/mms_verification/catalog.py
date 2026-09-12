"""Six development studies; truth is measured, never assigned from a fault flag."""
from dataclasses import asdict

from ..agents.records import digest
from . import VERSION
from .numerics import (DIAGNOSTIC, GRIDS, MMS_GRIDS, ORDER_BAND, PROBLEMS,
                       Q_POINT, STUDY_PROFILES, errors, inputs, order_pass,
                       orders, relative_error, solve)

# Frozen after numerical commissioning, before any policy comparison. Three
# physical problems, six studies; two identical inactive-feature controls.
SLOTS = (
    ("sound", "diffusion", "sound", 16),
    ("coarse_correct", "mixed", "sound", 8),
    ("advection_inaccurate", "advection", "upwind", 8),
    ("boundary_inaccurate", "mixed", "neumann_first", 16),
    ("advection_accurate", "advection", "upwind", 16),
    ("inactive_advection", "diffusion", "upwind", 16),
)


def relevant_family(problem):
    """Simple public study-aware rule; no case labels or error observations."""
    if problem["boundary"] == "mixed":
        return "mixed"
    return "advection" if problem["vx"] != 0 or problem["vy"] != 0 else "diffusion"


def public_study(case):
    return {
        "study_id": case["id"], "equation": "-kappa*Laplacian(u) + vx*u_x + vy*u_y = f",
        "domain": "[0,1]^2", "problem": PROBLEMS[case["family"]].public(),
        "q_point": list(Q_POINT), "reported_q": case["reported_q"],
        "original_grid": case["grid"], "relative_tolerance": .02,
        "order_claim": {"grids": list(MMS_GRIDS), "rms_order_band": list(ORDER_BAND),
                        "scope": "Declared study-relevant MMS family, both successive grid pairs; not universal/asymptotic correctness."},
        "mms_menu": {key: value.public() for key, value in PROBLEMS.items()},
        "diagnostic_exact_profile": asdict(DIAGNOSTIC),
        "boundary_convention": "Mixed: left/bottom Dirichlet; right/top outward derivative (not flux); top-right sums both equations.",
        "report": ("The reported point value has relative error at most 2%. The implementation also meets the declared "
                   "finite-grid near-second-order criterion on the study-relevant manufactured test. Audit these claims separately."),
        "available_kernels": ["audited", "independent"],
        "independent_kernel": "Separate central-difference tensor assembly with second-order boundary formulas; not exact truth.",
    }


def make_catalog():
    cases, sweeps = [], []
    # Retain all candidate study errors, including those not selected.
    for family, problem in PROBLEMS.items():
        for flavor in ("sound", "upwind", "neumann_first"):
            for n in GRIDS:
                result = solve(problem, STUDY_PROFILES[family], n, flavor)
                if result["status"] != "complete":
                    raise RuntimeError("study commissioning solve failed")
                sweeps.append({"family": family, "flavor": flavor, "grid": n,
                               "q": result["q"], **errors(result, STUDY_PROFILES[family])})
    for index, (category, family, flavor, n) in enumerate(SLOTS):
        profile, problem = STUDY_PROFILES[family], PROBLEMS[family]
        result = solve(problem, profile, n, flavor)
        reported = float(format(result["q"], ".10g"))
        e = relative_error(reported, profile.q())
        diag = [solve(problem, DIAGNOSTIC, grid, flavor) for grid in MMS_GRIDS]
        p = orders([errors(r, DIAGNOSTIC)["rms_error"] for r in diag])
        case = {"id": "study-"+digest({"version": VERSION, "slot": index})[:12],
                "category": category, "family": family, "flavor": flavor, "grid": n,
                "reported_q": reported, "original": result,
                "private": {"reference_q": profile.q(), "q_error": e,
                            "qoi_truth": e <= .02, "order_truth": order_pass(p),
                            "observed_orders": p, "study_profile": asdict(profile)}}
        expected = [(True, True), (False, True), (False, False),
                    (False, False), (True, False), (True, True)][index]
        actual = (e <= .02, order_pass(p))
        if actual != expected or abs(e-.02) < .005:
            raise RuntimeError(f"commissioning criteria not met for slot {index}: {actual}, {e}")
        cases.append(case)
    # Executable reference-free audit path: three relevant MMS solves and one
    # independently assembled study solve. This is a feasibility check, not a
    # formal error certificate. Freeze budgets before policy comparisons.
    feasibility = []
    for case in cases:
        profile, problem = STUDY_PROFILES[case["family"]], PROBLEMS[case["family"]]
        runs = [solve(problem, profile, n, kernel="independent") for n in (16, 32)]
        check_error = relative_error(runs[-1]["q"], profile.q())
        estimated_verdict = relative_error(case["reported_q"], runs[-1]["q"]) <= .02
        if check_error >= .005 or estimated_verdict != case["private"]["qoi_truth"]:
            raise RuntimeError("independent audit path not numerically adequate on development catalog")
        feasibility.append({"study_id": case["id"], "independent_32_q_error": check_error,
                            "path_credits": (81+289+1089+1089)/289,
                            "estimated_qoi_truth": estimated_verdict})
    return {"version": VERSION, "status": "development_only", "cases": cases,
            "study_sweep": sweeps, "feasibility": feasibility,
            "budgets": [10, 20], "independent_physical_problems": 3}


def public_original_data(case):
    """Forcing/BC arrays and original field; no exact interior field or labels."""
    problem, profile = PROBLEMS[case["family"]], STUDY_PROFILES[case["family"]]
    return {"numerical_inputs": {k: v.tolist() for k, v in inputs(problem, profile, case["grid"]).items()},
            "result": case["original"]}
