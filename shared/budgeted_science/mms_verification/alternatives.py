"""Optional checks; the frozen MMS environment and claims remain unchanged."""
from copy import deepcopy
from dataclasses import asdict
from math import isfinite
from time import perf_counter

import numpy as np
from scipy.sparse.linalg import LinearOperator, gmres, spilu

from ..agents.records import digest
from .environment import Audit
from .numerics import (DIAGNOSTIC, PROBLEMS, STUDY_PROFILES, Profile, Q_POINT,
                       assemble, independent_assemble, inputs, errors, charge_units)

VERSION = "mms-alternatives-1"
EXTRA_ACTIONS = ("run_affine_mms", "crosscheck_linear_solver", "richardson")
AFFINE = Profile(amplitude=0., axy=0.)


def iterative_solve(problem, profile, n, flavor="sound", kernel="audited"):
    """ILU-preconditioned GMRES on the SAME equations as the selected kernel."""
    start = perf_counter()
    units = charge_units(n)
    data = inputs(problem, profile, n)
    a, b = independent_assemble(problem, n, data) if kernel == "independent" else assemble(problem, n, data, flavor)
    ilu = spilu(a.tocsc(), drop_tol=1e-4, fill_factor=10)
    preconditioner = LinearOperator(a.shape, matvec=ilu.solve)
    residuals = []
    u, info = gmres(a, b, M=preconditioner, rtol=1e-12, atol=1e-13,
                    restart=50, maxiter=200, callback=residuals.append, callback_type="pr_norm")
    result = {"status": "complete" if info == 0 and np.all(np.isfinite(u)) else "failed",
              "grid": n, "linear_solver": "ILU-GMRES", "iterations": len(residuals),
              "solver_info": int(info), "work_units": units, "credits": units/289,
              "seconds": perf_counter()-start}
    if result["status"] == "complete":
        field = u.reshape(n+1, n+1)
        result.update(field=field.tolist(), q=float(field[int(Q_POINT[1]*n), int(Q_POINT[0]*n)]),
                      matrix_nnz=int(a.nnz), scaled_residual=float(np.linalg.norm(a@u-b)/max(1., np.linalg.norm(b))))
    return result


class AlternativeAudit(Audit):
    def __init__(self, *args, iterative_executor=iterative_solve, **kwargs):
        super().__init__(*args, **kwargs)
        self._iterative_executor = iterative_executor

    def call(self, call_id, action, **arguments):
        if action not in EXTRA_ACTIONS:
            return super().call(call_id, action, **arguments)
        if not isinstance(call_id, str) or not call_id:
            raise ValueError("nonempty call ID required")
        fingerprint = digest({"action": action, "arguments": arguments})
        if call_id in self._calls:
            previous, response = self._calls[call_id]
            if previous != fingerprint:
                raise ValueError("call ID reused with different arguments")
            self._event("duplicate_call", call_id=call_id)
            return deepcopy(response)
        self._event("request", call_id=call_id, action=action, arguments=arguments)
        try:
            if self._submission is not None:
                raise ValueError("episode already submitted")
            if self._requests >= 30 or perf_counter()-self._started > 300:
                raise ValueError("episode request/runtime limit reached")
            self._requests += 1
            result = getattr(self, "_"+action)(**arguments)
            response = {"ok": True, "result": result, "budget": self.status()}
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            response = {"ok": False, "error": str(exc), "budget": self.status()}
        self._calls[call_id] = (fingerprint, deepcopy(response))
        self._event("response", call_id=call_id, response=response)
        return response

    def _run_affine_mms(self, family, grid, kernel):
        return self._extra_purchase("affine_mms", family, grid, kernel, AFFINE, "direct")

    def _crosscheck_linear_solver(self, result_id):
        record = self._records.get(result_id)
        if not record or record.get("status") != "complete" or record.get("kind") not in ("study", "mms", "affine_mms"):
            raise ValueError("successful purchased numerical run required")
        kind, family = record["kind"], record.get("family", self._case["family"])
        profile = STUDY_PROFILES[family] if kind == "study" else DIAGNOSTIC if kind == "mms" else AFFINE
        result = self._extra_purchase(kind, family, record["grid"], record["kernel"], profile, "iterative")
        if result["status"] == "complete":
            result["comparison"] = {"source_id": result_id, "q_difference": result["q"]-record["q"],
                                    "interpretation": "Same discrete operator; different algebraic solver."}
        return result

    def _extra_purchase(self, kind, family, grid, kernel, profile, algorithm):
        units = charge_units(grid)
        if family not in PROBLEMS or kernel not in ("audited", "independent"):
            raise ValueError("unknown family or kernel")
        problem = PROBLEMS[family]
        key = digest({"version": VERSION, "kind": kind, "problem": asdict(problem), "profile": asdict(profile),
                      "grid": grid, "kernel": kernel, "algorithm": algorithm,
                      "flavor": self._case["flavor"] if kernel == "audited" else "sound"})
        if key in self._purchases:
            return self._compact(self._records[self._purchases[key]], "episode_reuse", 0)
        if self._spent+units > self._limit:
            raise ValueError("insufficient scientific budget")
        self._spent += units
        hit = key in self._backend
        self._event("purchase", kind_of_solve=kind, grid=grid, kernel=kernel,
                    algorithm=algorithm, charged_units=units, backend_cache_hit=hit, budget=self.status())
        if hit:
            numerical = deepcopy(self._backend[key])
        else:
            try:
                executor = self._iterative_executor if algorithm == "iterative" else self._executor
                numerical = executor(problem, profile, grid, self._case["flavor"], kernel)
            except Exception as exc:
                numerical = {"status": "failed", "grid": grid, "message": type(exc).__name__}
            self._backend[key] = deepcopy(numerical)
        result_id = f"run-{len(self._purchases)+1:03d}"
        result = {"id": result_id, "kind": kind, "family": family, "kernel": kernel,
                  "linear_solver": "ILU-GMRES" if algorithm == "iterative" else "sparse-direct", **numerical}
        if kind in ("mms", "affine_mms") and result["status"] == "complete":
            result["diagnostic_errors"] = errors(result, profile)
        if kind == "affine_mms":
            result["diagnostic_exact_profile"] = asdict(AFFINE)
        self._records[result_id], self._purchases[key] = result, result_id
        self._event("numerical", backend_cache_hit=hit, charged_units=units, artifact=result)
        return self._compact(result, "backend_cache" if hit else "executed", units/289)

    def _richardson(self, coarse_id, fine_id, assumed_order):
        if (isinstance(assumed_order, bool) or not isinstance(assumed_order, (int, float))
                or not isfinite(assumed_order) or not .1 <= assumed_order <= 8):
            raise ValueError("assumed_order must be finite and within [0.1,8]")
        coarse, fine = self._records.get(coarse_id), self._records.get(fine_id)
        if not coarse or not fine or any(r.get("status") != "complete" or r.get("kind") != "study" for r in (coarse, fine)):
            raise ValueError("two successful original-study calculations required")
        if coarse["kernel"] != fine["kernel"] or coarse["grid"] >= fine["grid"]:
            raise ValueError("same numerical kernel and increasing grid resolution required")
        ratio = fine["grid"]/coarse["grid"]
        correction = (fine["q"]-coarse["q"])/(ratio**assumed_order-1)
        key = digest([coarse_id, fine_id, assumed_order])[:16]
        result = {"id": "derived-"+key, "kind": "richardson", "coarse_id": coarse_id, "fine_id": fine_id,
                  "assumed_order": assumed_order, "grid_ratio": ratio, "extrapolated_q": fine["q"]+correction,
                  "estimated_fine_grid_error": abs(correction), "charge": 0,
                  "interpretation": "Assumes leading error proportional to h^p at supplied p; not a certified error bound or order test."}
        self._records[result["id"]] = result
        self._event("derived_record", artifact=result)
        return deepcopy(result)
