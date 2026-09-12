"""Trusted-process audit boundary, purchases, deterministic caching and scoring."""

from copy import deepcopy
import math

from budgeted_science.agents.records import digest
from . import VERSION
from . import numerics as num


def relative_error(value, reference):
    if value is None or reference is None:
        return None
    return abs(float(value)-float(reference))/abs(float(reference))


def within(value, reference, tolerance):
    error = relative_error(value, reference)
    return error is not None and error <= tolerance + 1e-12


class Backend:
    def __init__(self, solver=None):
        self.solver = solver or num.solve
        self.cache = {}

    def key(self, system, cfg):
        return digest({"version": VERSION, "system": system, "config": cfg})

    def run(self, system, cfg):
        key = self.key(system, cfg)
        hit = key in self.cache
        if not hit:
            self.cache[key] = self.solver(system, cfg)
        return deepcopy(self.cache[key]), hit


class PublicTools:
    """Only this facade is passed to a policy. Python introspection is not sandboxed."""
    def __init__(self, episode):
        self._episode = episode

    def call(self, name, arguments=None, call_id=None):
        return self._episode.call(name, arguments, call_id)


class Episode:
    def __init__(self, study, credits=4., backend=None, log=None):
        if not math.isfinite(credits) or credits < 0 or not math.isclose(credits*num.WORK_UNIT, round(credits*num.WORK_UNIT)):
            raise ValueError("budget must be a nonnegative integer number of work units")
        self.study = deepcopy(study)
        self.limit = round(credits*num.WORK_UNIT)
        self.spent = 0
        self.backend, self.log = backend or Backend(), log
        self.runs = {"original": deepcopy(study["original"])}
        self.purchases = {}
        self.calls = {}
        self.submission = None
        self.state = "active"
        self.tools = PublicTools(self)

    def budget(self):
        return {"limit": self.limit/num.WORK_UNIT, "spent": self.spent/num.WORK_UNIT,
                "remaining": (self.limit-self.spent)/num.WORK_UNIT}

    def compact(self, run_id):
        run = self.runs[run_id]
        return {"run_id": run_id, "status": run["status"], "reason": run["reason"],
                "config": run["config"], "qois": num.qois(run) if run["status"] == "complete" else None,
                "work": run["work"], "nominal_credits": run["credits"]}

    def call(self, name, arguments=None, call_id=None):
        args = deepcopy(arguments if arguments is not None else {})
        signature = digest({"name": name, "arguments": args})
        if call_id is not None and call_id in self.calls:
            old, answer = self.calls[call_id]
            if old != signature:
                raise ValueError("call ID reused with different request")
            return deepcopy(answer)
        if self.state != "active":
            raise ValueError("episode ended")
        if self.log:
            self.log.event("tool_request", name=name, arguments=args, call_id=call_id)
        try:
            answer = self._execute(name, args)
        except (ValueError, TypeError, KeyError) as exc:
            answer = {"error": str(exc)}
        answer["budget"] = self.budget()
        if self.log:
            self.log.event("tool_result", name=name, call_id=call_id, result=answer)
        if call_id is not None:
            self.calls[call_id] = (signature, deepcopy(answer))
        return answer

    def _execute(self, name, args):
        if not isinstance(args, dict):
            raise ValueError("arguments must be an object")
        if name in ("describe", "budget"):
            if args:
                raise ValueError("no arguments expected")
            if name == "budget":
                return {}
            return {"study": deepcopy(self.study["public"]), "original": self.compact("original"),
                    "notes": "Reference unavailable. Outputs use spatial grid values and linear temporal interpolation. "
                             "Recompute uses only saved samples; comparisons are not certified error bounds."}
        if name in ("quote", "run_verification"):
            cfg = num.validate(self.study["system"], num.config(**args))
            key = self.backend.key(self.study["system"], cfg)
            original_key = self.backend.key(self.study["system"], self.runs["original"]["config"])
            run_id = "original" if key == original_key else self.purchases.get(key)
            price = num.quote(cfg)
            if name == "quote":
                return {"config": cfg, "price": price, "new_credits": 0. if run_id else price["credits"]}
            if run_id:
                return {**self.compact(run_id), "charge": 0., "reuse": True}
            if self.spent+price["work"] > self.limit:
                raise ValueError("insufficient audit budget")
            if self.log:
                self.log.event("execution_started", config=cfg, reserved_work=price["work"])
            self.spent += price["work"]
            try:
                run, hit = self.backend.run(self.study["system"], cfg)
                if not isinstance(run["work"], int) or not 0 <= run["work"] <= price["work"]:
                    raise RuntimeError("invalid solver work accounting")
                if run["status"] == "complete" and run["work"] != price["work"]:
                    raise RuntimeError("completed solve disagrees with work quote")
            except Exception:
                self.state = "aborted"
                raise
            self.spent -= price["work"]-run["work"]
            run_id = "run-"+key[:12]
            self.runs[run_id] = run
            self.purchases[key] = run_id
            if self.log:
                artifact = self.log.write_json("numerical/"+run_id+".json", run)
                self.log.event("numerical_result", run_id=run_id, artifact=artifact, backend_cache_hit=hit,
                               charge=run["credits"], budget=self.budget())
            return {**self.compact(run_id), "charge": run["credits"], "reuse": False, "backend_cache_hit": hit}
        if name in ("inspect_existing_run", "recompute_qoi"):
            allowed = {"run_id", "offset", "limit"} if name == "inspect_existing_run" else {"run_id"}
            if set(args)-allowed or "run_id" not in args:
                raise ValueError("invalid run-inspection arguments")
            run_id = args["run_id"]
            summary = self.compact(run_id)
            if name == "recompute_qoi":
                return summary
            offset, limit = args.get("offset", 0), args.get("limit", 128)
            if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= 256:
                raise ValueError("invalid pagination")
            run = self.runs[run_id]
            end = min(offset+limit, len(run["times"]))
            return {**summary, "times": run["times"][offset:end], "sensor": run["sensor"][offset:end],
                    "next_offset": end if end < len(run["times"]) else None}
        if name == "compare_runs":
            if set(args) != {"run_ids"} or not isinstance(args["run_ids"], list) or not 2 <= len(args["run_ids"]) <= 10:
                raise ValueError("supply 2..10 purchased run IDs")
            summaries = [self.compact(r) for r in args["run_ids"]]
            return {"runs": summaries, "differences": [
                {q: s["qois"][q]-summaries[0]["qois"][q] if s["qois"] and summaries[0]["qois"] and s["qois"][q] is not None and summaries[0]["qois"][q] is not None else None for q in num.QUANTITIES}
                for s in summaries[1:]]}
        if name == "submit":
            if set(args) != {"verdict", "evidence_ids", "justification"}:
                raise ValueError("verdict, evidence_ids and justification required")
            if args["verdict"] not in ("ACCEPT", "REJECT", "ABSTAIN") or not isinstance(args["justification"], str):
                raise ValueError("invalid verdict or justification")
            if not isinstance(args["evidence_ids"], list) or any(not isinstance(r, str) or r not in self.runs for r in args["evidence_ids"]):
                raise ValueError("unknown evidence ID")
            self.submission = deepcopy(args)
            self.state = "submitted"
            return {"status": "submitted"}
        raise ValueError("unknown tool")

    def evaluation(self):
        claim = self.study["public"]["claim"]
        actual = self.study["reference"]["qois"][claim["quantity"]]
        valid = within(claim["value"], actual, claim["tolerance"])
        verdict = self.submission["verdict"] if self.state == "submitted" else None
        return {"valid": valid, "original_relative_error": relative_error(claim["value"], actual),
                "reference": actual, "verdict": verdict,
                "correct": verdict == ("ACCEPT" if valid else "REJECT"),
                "coverage": verdict in ("ACCEPT", "REJECT"), "incomplete": verdict is None,
                "abstention": verdict == "ABSTAIN", "spent": self.spent/num.WORK_UNIT}
