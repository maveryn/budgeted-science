"""Costed numerical services for the unchanged four heat-workflow studies.

Prices are declared synthetic service tariffs, not measured dollars or FLOPs.
No exact reference or verdict is available through these services.
"""
from copy import deepcopy
from dataclasses import asdict
from fractions import Fraction
from time import perf_counter

import numpy as np

from ..agents.records import digest
from .numerics import Problem, initial_field, patch_mean, residual_rms, solve_direct

VERSION = "heat-costed-1"
GRIDS = (17, 33, 65)
SWEEPS = (256, 1024, 4096)
PAID = ("iterate", "remesh", "solve_matrix", "perturb_boundary")


def tariff(name, n, sweeps=None):
    if n not in GRIDS or type(n) is not int:
        raise ValueError("grid must be 17, 33, or 65 nodes per axis")
    if name in ("iterate", "remesh"):
        if sweeps not in SWEEPS or type(sweeps) is not int:
            raise ValueError("sweeps must be 256, 1024, or 4096")
        return Fraction(n*n*sweeps, 33*33*1024)
    if name in ("solve_matrix", "perturb_boundary"):
        return Fraction(4*n*n, 33*33)
    raise ValueError("unknown numerical service")


def boundaries(values):
    if not isinstance(values, dict) or set(values) != {"top", "bottom", "left", "right"}:
        raise ValueError("four boundary values required")
    if any(type(v) not in (float, int) or not np.isfinite(v) or not -2 <= v <= 2 for v in values.values()):
        raise ValueError("boundary values must be finite numbers in [-2, 2]")
    return Problem(**values)


def relax(field, sweeps, omega):
    """Exactly the purchased number of weighted-Jacobi sweeps; no stop oracle."""
    start = perf_counter()
    field = np.array(field, dtype=float, copy=True)
    for i in range(sweeps):
        old = field.copy()
        field[1:-1, 1:-1] = (1-omega)*old[1:-1, 1:-1] + omega/4*(
            old[:-2, 1:-1]+old[2:, 1:-1]+old[1:-1, :-2]+old[1:-1, 2:])
        if not np.all(np.isfinite(field)):
            raise ArithmeticError("nonfinite iteration")
    return field, {"status": "requested_sweeps_completed", "iterations": sweeps,
                   "update_rms": float(np.sqrt(np.mean((field-old)**2))),
                   "grid_point_iterations": field.size*sweeps, "seconds": perf_counter()-start}


class Audit:
    def __init__(self, public, credits=8, sink=None):
        if type(credits) not in (int, float) or not np.isfinite(credits) or credits < 0:
            raise ValueError("invalid scientific budget")
        self.public = deepcopy(public)
        self.cap, self.spent = Fraction(str(credits)), Fraction(0)
        self.by_tool = {name: Fraction(0) for name in PAID}
        self.purchases, self.cache, self.records = [], {}, {}
        self.sink = sink or (lambda kind, **data: None)
        artifacts = self.public["artifacts"]
        field = np.asarray(artifacts["trajectory.json"]["T"], dtype=float)
        if field.shape != (33, 33) or not np.all(np.isfinite(field)):
            raise ValueError("expected original finite 33-node heat field")
        self._save("original", field, artifacts["run_config.json"]["boundaries"],
                   artifacts["solver_log.json"], "original", {})

    def _save(self, ident, field, bc, info, action, args):
        record = {"id": ident, "n": len(field), "boundaries": deepcopy(bc),
                  "T": field.tolist(), "x": np.linspace(0, 1, len(field)).tolist(),
                  "y": np.linspace(0, 1, len(field)).tolist(), "info": deepcopy(info),
                  "action": action, "arguments": deepcopy(args)}
        record["info"]["residual_rms"] = residual_rms(field)
        self.records[ident] = record
        self.sink("numerical", record=deepcopy(record))

    def status(self):
        return {"cap": float(self.cap), "spent": float(self.spent),
                "remaining": float(self.cap-self.spent), "paid_calls": len(self.purchases),
                "by_tool": {k: float(v) for k, v in self.by_tool.items()},
                "price_scope": "synthetic numerical-service credits; not API dollars"}

    def record(self, run_id):
        if run_id not in self.records:
            raise ValueError("unknown or unpurchased numerical record")
        return self.records[run_id]

    def compact(self, run_id):
        r = self.record(run_id)
        return {k: deepcopy(r[k]) for k in ("id", "n", "boundaries", "info", "action", "arguments")}

    def purchase(self, name, args):
        args = deepcopy(args)
        source = None
        if name in ("iterate", "remesh", "perturb_boundary"):
            source = self.record(args["run_id"])
            if source["info"].get("status") == "failed":
                raise ValueError("failed record has no usable field")
        if name in ("iterate", "remesh"):
            n = source["n"] if name == "iterate" else args["n"]
            bc = deepcopy(source["boundaries"])
            omega = args["relaxation"]
            if type(omega) not in (int, float) or not np.isfinite(omega) or not 0 < omega <= 1:
                raise ValueError("relaxation must be in (0,1]")
            cost = tariff(name, n, args["sweeps"])
        elif name == "solve_matrix":
            bc, n = asdict(boundaries(args["boundaries"])), args["n"]
            cost = tariff(name, n)
        elif name == "perturb_boundary":
            bc, n = deepcopy(source["boundaries"]), source["n"]
            edge, delta = args["edge"], args["delta"]
            if edge not in bc or type(delta) not in (int, float) or not np.isfinite(delta):
                raise ValueError("invalid boundary perturbation")
            bc[edge] += delta
            bc = asdict(boundaries(bc))
            cost = tariff(name, n)
        else:
            raise ValueError("unknown paid tool")
        # Complete configuration and input field participate in deterministic reuse.
        key = digest({"version": VERSION, "tool": name, "args": args,
                      "source": source, "boundaries": bc})
        if key in self.cache:
            run_id = self.cache[key]
            self.sink("reuse", run_id=run_id, tool=name)
            return {"ok": True, "charge": 0.0, "reused": True, **self.compact(run_id)}
        if self.spent+cost > self.cap:
            return {"ok": False, "error": "insufficient_scientific_budget", "required": float(cost), "charge": 0.0}
        run_id = f"run-{len(self.purchases)+1:03d}"
        self.spent += cost
        self.by_tool[name] += cost
        purchase = {"id": run_id, "tool": name, "args": args, "charge": float(cost),
                    "exact_charge": str(cost), "key": key}
        self.purchases.append(purchase)
        self.sink("purchase_started", **purchase, budget=self.status())
        start = perf_counter()
        try:
            if name in ("iterate", "remesh"):
                field = source["T"] if name == "iterate" else initial_field(Problem(**bc), n)
                field, info = relax(field, args["sweeps"], omega)
            else:
                field, info = solve_direct(Problem(**bc), n)
            self._save(run_id, field, bc, info, name, args)
        except Exception as exc:
            # Flat job tariffs: execution failures retain the purchase charge.
            self.records[run_id] = {"id": run_id, "n": n, "boundaries": bc,
                "info": {"status": "failed", "error": str(exc), "seconds": perf_counter()-start},
                "action": name, "arguments": args}
            self.sink("numerical", record=deepcopy(self.records[run_id]))
        self.cache[key] = run_id
        return {"ok": True, "charge": float(cost), "reused": False, **self.compact(run_id)}

    def inspect(self, name, args):
        if name == "budget":
            return self.status()
        if name == "read_artifact":
            artifact = args["name"]
            if artifact not in self.public["artifacts"]:
                raise ValueError("unknown public artifact")
            if artifact == "trajectory.json":
                raise ValueError("use record('original', start_row, row_count) for the field")
            return {"name": artifact, "content": deepcopy(self.public["artifacts"][artifact])}
        if name == "record":
            r = self.record(args["run_id"])
            start, count = args["start_row"], args["row_count"]
            if type(start) is not int or type(count) is not int or not 0 <= start < r["n"] or not 1 <= count <= 16:
                raise ValueError("invalid field page")
            return {**self.compact(r["id"]), "x": r.get("x", [])[start:start+count],
                    "y": r.get("y", []), "T_rows": r.get("T", [])[start:start+count],
                    "start_row": start, "array_convention": "T[i,j] at (x[i], y[j])"}
        if name == "integrate_field":
            r = self.record(args["run_id"])
            if "T" not in r:
                raise ValueError("failed record has no field")
            if type(args["transpose"]) is not bool:
                raise ValueError("transpose must be boolean")
            field = np.asarray(r["T"])
            region = tuple(args[k] for k in ("x0", "x1", "y0", "y1"))
            value = patch_mean(field.T if args["transpose"] else field, region)
            return {"run_id": r["id"], "area_mean": value, "patch": list(region), "transpose": args["transpose"],
                    "note": "Bilinear-interpolant integral of this purchased field, not an error bound or truth."}
        raise ValueError("unknown inspection action")
