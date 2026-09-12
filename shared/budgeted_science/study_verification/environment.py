"""Artifact-first auditing with explicit input, solver and analysis provenance.

Only numerical solves are charged. Unit arithmetic and analysis of purchased
arrays are free; we do not manufacture a resource trade-off by charging trivial
operations. This is trusted in-process separation, not a code sandbox.
"""

from copy import deepcopy
import math

import numpy as np

from ..agents.records import digest
from ..transport_verification import numerics as num
from ..transport_verification.environment import Backend as TransportBackend, Episode as TransportEpisode
from . import VERSION


def process_inputs(raw, length_m, duration_s):
    for value in (length_m, duration_s):
        if isinstance(value, bool) or not math.isfinite(float(value)) or not .1 <= float(value) <= 10:
            raise ValueError("reference length and duration must be finite, within [0.1,10]")
    length_m, duration_s = float(length_m), float(duration_s)
    return num.physical({"v": raw["velocity_cm_s"]*.01*duration_s/length_m,
                         "D": raw["diffusivity_cm2_s"]*.0001*duration_s/length_m**2,
                         "k": raw["decay_per_s"]*duration_s})


def analyze(run, start, end, method):
    if run["status"] != "complete":
        raise ValueError("cannot analyze an incomplete trajectory")
    if (isinstance(start, bool) or isinstance(end, bool) or
            not all(math.isfinite(float(v)) for v in (start, end)) or not 0 <= start < end <= 1):
        raise ValueError("analysis window must satisfy 0 <= start < end <= 1")
    if method not in ("trapezoid", "left", "right"):
        raise ValueError("unknown quadrature method")
    t, y = np.asarray(run["times"]), np.asarray(run["sensor"])
    times = np.r_[float(start), t[(t > start) & (t < end)], float(end)]
    values = np.interp(times, t, y)
    heights = (values[:-1]+values[1:])/2 if method == "trapezoid" else values[:-1] if method == "left" else values[1:]
    return {"value": float(np.dot(np.diff(times), heights)), "start": float(start), "end": float(end),
            "method": method, "sample_count": len(times),
            "note": "Integral of saved samples with linear endpoint interpolation; not a reference or error bound."}


class Backend(TransportBackend):
    def key(self, system, cfg):
        return digest({"version": VERSION, "system": system, "config": cfg})


class Episode(TransportEpisode):
    def __init__(self, study, credits=4., backend=None, log=None):
        super().__init__(study, credits, backend or Backend(), log)
        self.inputs = {"study-input": deepcopy(study["public"]["processed_inputs"])}
        self.artifacts = deepcopy(study["artifacts"])
        self.analyses = {"study-analysis": deepcopy(study["original_analysis"])}

    def compact(self, run_id):
        run = self.runs[run_id]
        return {"run_id": run_id, "status": run["status"], "reason": run["reason"],
                "config": run["config"], "system_used": run["system_used"],
                "work": run["work"], "nominal_credits": run["credits"],
                "sample_count": len(run["times"])}

    def _execute(self, name, args):
        if not isinstance(args, dict):
            raise ValueError("arguments must be an object")
        if name == "describe":
            if args:
                raise ValueError("no arguments expected")
            return {"study": deepcopy(self.study["public"]), "original": self.compact("original"),
                    "artifacts": [{"id": k, "role": v["role"]} for k, v in self.artifacts.items()]}
        if name == "read_artifact":
            if set(args) != {"id"} or args["id"] not in self.artifacts:
                raise ValueError("unknown artifact")
            return {"id": args["id"], **deepcopy(self.artifacts[args["id"]])}
        if name == "prepare_inputs":
            if set(args) != {"length_m", "duration_s"}:
                raise ValueError("length_m and duration_s required")
            p = process_inputs(self.study["public"]["raw_inputs"], **args)
            input_id = "input-"+digest(p)[:12]
            self.inputs[input_id] = p
            return {"input_id": input_id, "system": p, "normalization": deepcopy(args), "charge": 0.}
        if name in ("quote", "run_simulation"):
            if set(args) != {"input_id", "nx", "dt", "spatial_method", "temporal_method", "output_dt"}:
                raise ValueError("input ID and complete numerical configuration required")
            p = self.inputs[args["input_id"]]
            cfg = num.validate(p, num.config(**{k: v for k, v in args.items() if k != "input_id"}))
            key = self.backend.key(p, cfg)
            original = self.runs["original"]
            original_key = self.backend.key(original["system_used"], original["config"])
            run_id = "original" if key == original_key else self.purchases.get(key)
            price = num.quote(cfg)
            if name == "quote":
                return {"config": cfg, "system_used": p, "price": price,
                        "new_credits": 0. if run_id else price["credits"]}
            if run_id:
                return {**self.compact(run_id), "charge": 0., "reuse": True}
            if self.spent+price["work"] > self.limit:
                raise ValueError("insufficient audit budget")
            if self.log:
                self.log.event("execution_started", config=cfg, input_id=args["input_id"], reserved_work=price["work"])
            self.spent += price["work"]
            try:
                run, hit = self.backend.run(p, cfg)
                if (not isinstance(run["work"], int) or not 0 <= run["work"] <= price["work"] or
                        (run["status"] == "complete" and run["work"] != price["work"])):
                    raise RuntimeError("invalid solver work accounting")
            except Exception:
                self.state = "aborted"
                raise
            self.spent -= price["work"]-run["work"]
            run["system_used"] = deepcopy(p)
            run_id = "run-"+key[:12]
            self.runs[run_id], self.purchases[key] = run, run_id
            if self.log:
                artifact = self.log.write_json("numerical/"+run_id+".json", run)
                self.log.event("numerical_result", run_id=run_id, artifact=artifact,
                               backend_cache_hit=hit, charge=run["credits"], budget=self.budget())
            return {**self.compact(run_id), "charge": run["credits"], "reuse": False, "backend_cache_hit": hit}
        if name == "analyze_run":
            if set(args) != {"run_id", "start", "end", "method"}:
                raise ValueError("run_id, start, end and method required")
            result = {"run_id": args["run_id"], **analyze(self.runs[args["run_id"]], args["start"], args["end"], args["method"])}
            analysis_id = "analysis-"+digest(result)[:12]
            self.analyses[analysis_id] = result
            return {"analysis_id": analysis_id, **result, "charge": 0.}
        if name == "submit":
            if (set(args) != {"verdict", "diagnosis", "evidence_ids", "justification"} or
                    args["verdict"] not in ("ACCEPT", "REJECT", "ABSTAIN") or
                    not all(isinstance(args[k], str) for k in ("diagnosis", "justification"))):
                raise ValueError("invalid verdict, diagnosis or justification")
            available = set(self.artifacts) | set(self.runs) | set(self.inputs) | set(self.analyses)
            if not isinstance(args["evidence_ids"], list) or any(not isinstance(i, str) or i not in available for i in args["evidence_ids"]):
                raise ValueError("unknown evidence ID")
            self.submission, self.state = deepcopy(args), "submitted"
            return {"status": "submitted"}
        if name in ("budget", "inspect_existing_run"):
            return super()._execute(name, args)
        raise ValueError("unknown tool")
