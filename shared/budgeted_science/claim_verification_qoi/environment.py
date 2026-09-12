"""Purchased-evidence-only facade. Trusted-process isolation, not a sandbox."""
from copy import deepcopy
import inspect
import math

import numpy as np
import scipy

from ..agents.records import digest
from . import VERSION
from .numerics import config, quote, solve, qois, validate_theta
from .studies import validate_study, trajectory_text

ACTIONS = ("describe", "list_artifacts", "read_artifact", "read_run", "quote_check", "run_check",
           "recompute_quantity", "compare_runs", "budget", "submit")


def cache_key(theta, cfg):
    return digest([VERSION, list(validate_theta(theta)), config(**cfg), np.__version__, scipy.__version__])


class Backend:
    def __init__(self, solver=None):
        self.solver = solver or solve
        self.cache = {}

    def get(self, theta, cfg):
        key = cache_key(theta, cfg)
        hit = key in self.cache
        if not hit:
            self.cache[key] = deepcopy(self.solver(theta, cfg))
        return deepcopy(self.cache[key]), hit


class PublicTools:
    __slots__ = ("__episode",)
    def __init__(self, episode):
        self.__episode = episode

    def call(self, name, arguments=None, call_id=None):
        return self.__episode.call(name, {} if arguments is None else arguments, call_id)


class Episode:
    def __init__(self, study, credits=8, backend=None, log=None):
        self.study = deepcopy(validate_study(study))
        if isinstance(credits, bool) or not math.isfinite(credits) or credits < 0 or abs(credits*100-round(credits*100))>1e-9:
            raise ValueError("budget must be nonnegative hundredth credits")
        self.limit_work = round(credits*100)
        self.backend = backend or Backend()
        self.log = log
        self.runs = {study["run_id"]: deepcopy(study["run"])}
        self.keys = {cache_key(study["private"]["theta"], study["run"]["config"]): study["run_id"]}
        self.artifacts = deepcopy(study["artifacts"])
        self.ledger, self.calls = [], {}
        self.state, self.submission, self.reason = "active", None, None
        self.tools = PublicTools(self)

    @property
    def spent(self):
        return sum(r["work"] for r in self.ledger)/100

    @property
    def remaining(self):
        return (self.limit_work-sum(r["work"] for r in self.ledger))/100

    def emit(self, kind, **data):
        if self.log:
            try:
                self.log(kind, **deepcopy(data))
            except BaseException:
                self.state, self.reason = "aborted", "logging interrupted"
                raise

    def result(self, status="success", **data):
        return {"status": status, "remaining": self.remaining, **data}

    def call(self, name, arguments, call_id=None):
        try:
            signature = digest([name, arguments])
        except (TypeError, ValueError):
            return self.result("invalid", error="finite JSON arguments required")
        self.emit("tool_requested", name=name, arguments=arguments, call_id=call_id)
        if call_id is not None and (not isinstance(call_id, str) or not call_id):
            result = self.result("invalid", error="invalid call ID")
        elif call_id in self.calls:
            old, response = self.calls[call_id]
            result = deepcopy(response) if old == signature else self.result("invalid", error="conflicting call ID")
        elif self.state != "active":
            result = self.result("closed", error="episode ended")
        else:
            try:
                if name not in ACTIONS or not isinstance(arguments, dict):
                    raise ValueError("unknown tool or malformed arguments")
                operation = getattr(self, "_"+name)
                inspect.signature(operation).bind(**arguments)
                result = operation(**arguments)
            except (ValueError, TypeError, KeyError) as exc:
                if self.state != "active":
                    raise
                result = self.result("invalid", error=str(exc))
            if call_id is not None:
                self.calls[call_id] = (signature, deepcopy(result))
        self.emit("tool_result", name=name, call_id=call_id, result=result)
        return deepcopy(result)

    def _describe(self):
        return self.result(claim=self.study["claim"], original_run_id=self.study["run_id"],
            original_config=self.study["run"]["config"], scientific_budget=self.limit_work/100,
            pricing="credits=(performed RHS evaluations + recorded output samples)/100; work proxy, not FLOPs or money",
            check_contract={"methods":["Euler", "RK2"], "RK2":"explicit midpoint",
                            "dt_range":[.01,.32], "dt_must_divide":8,
                            "output_step_range":[.01,2], "offset_fraction_range":"[0,1)"})

    def _budget(self):
        return self.result(total=self.limit_work/100, spent=self.spent, ledger=self.ledger)

    def _list_artifacts(self):
        return self.result(artifacts=[{"id":k,"role":a["role"],"run_id":a["run_id"]} for k,a in self.artifacts.items()])

    def _read_artifact(self, id, offset=0, limit=200):
        if not isinstance(id, str) or id not in self.artifacts:
            raise ValueError("unknown artifact")
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1<=limit<=200:
            raise ValueError("invalid pagination")
        a = self.artifacts[id]; lines = a["content"].splitlines(keepends=True)
        end = min(len(lines), offset+limit)
        return self.result(id=id, role=a["role"], run_id=a["run_id"], content="".join(lines[offset:end]),
                           next_offset=end if end<len(lines) else None, total_lines=len(lines))

    def _run(self, run_id):
        if not isinstance(run_id, str) or run_id not in self.runs or self.runs[run_id]["status"] != "success":
            raise ValueError("successful purchased run required")
        return self.runs[run_id]

    def _read_run(self, run_id):
        run = self._run(run_id)
        return self.result(run_id=run_id, config=run["config"], times=run["times"], values=run["values"], qois=qois(run))

    def _quote_check(self, method, dt, output_step, output_offset=0):
        cfg = config(method, dt, output_step, output_offset)
        key = cache_key(self.study["private"]["theta"], cfg)
        price = quote(cfg)
        return self.result(**price, config=cfg, episode_reuse=key in self.keys,
                           charge=0 if key in self.keys else price["credits"])

    def _run_check(self, method, dt, output_step, output_offset=0):
        cfg = config(method, dt, output_step, output_offset)
        key = cache_key(self.study["private"]["theta"], cfg)
        if key in self.keys:
            return self._compact(self.keys[key], 0, True)
        price = quote(cfg)
        if price["work"] > self.limit_work-sum(r["work"] for r in self.ledger):
            return self.result("unaffordable", charge=0, quoted_credits=price["credits"])
        run_id = "run-" + digest([self.study["physical_study_id"], cfg])[:16]
        entry = {"run_id":run_id, "config":cfg, "quoted_work":price["work"], "work":price["work"], "status":"pending"}
        self.ledger.append(entry)
        try:
            self.emit("work_reserved", entry=entry)
        except BaseException:
            entry.update(work=0, status="not_executed")
            raise
        try:
            run, hit = self.backend.get(self.study["private"]["theta"], cfg)
            if (type(run["work"]) is not int or not 0<=run["work"]<=price["work"]
                    or run["credits"] != run["work"]/100):
                raise RuntimeError("invalid performed-work accounting")
        except BaseException:
            entry["status"] = "interrupted_work_unknown"
            self.state, self.reason = "aborted", "numerical execution/accounting interrupted"
            raise
        entry.update(work=run["work"], status=run["status"])
        self.runs[run_id], self.keys[key] = run, run_id
        if run["status"] == "success":
            self.artifacts[run_id+"-trajectory"] = {"role":"trajectory", "run_id":run_id, "content":trajectory_text(run)}
            self.artifacts[run_id+"-analysis"] = {"role":"analysis", "run_id":run_id, "content":str(qois(run))}
        self.emit("numerical_artifact", run_id=run_id, artifact=run, backend_cache_hit=hit)
        self.emit("work_charged", entry=entry, spent=self.spent)
        return self._compact(run_id, entry["work"]/100, False)

    def _compact(self, run_id, charge, reused):
        run = self.runs[run_id]
        return self.result(run["status"], run_id=run_id, config=run["config"], charge=charge,
                           episode_reuse=reused, qois=qois(run) if run["status"]=="success" else None)

    def _recompute_quantity(self, run_id, quantity):
        values = qois(self._run(run_id))
        if quantity not in values:
            raise ValueError("unknown quantity")
        return self.result(run_id=run_id, quantity=quantity, value=values[quantity], qois=values)

    def _compare_runs(self, run_ids, quantity):
        if not isinstance(run_ids, list) or len(run_ids)<2 or len(set(run_ids))!=len(run_ids):
            raise ValueError("two distinct run IDs required")
        values = [self._recompute_quantity(r, quantity)["value"] for r in run_ids]
        return self.result(quantity=quantity, runs=[{"run_id":r,"value":v} for r,v in zip(run_ids,values)],
                           differences=[v-values[0] for v in values[1:]], certified=False)

    def _submit(self, verdict, diagnosis, evidence_ids, justification):
        if verdict not in ("ACCEPT", "REJECT", "ABSTAIN"):
            raise ValueError("invalid verdict")
        if any(not isinstance(t,str) or not t.strip() for t in (diagnosis,justification)):
            raise ValueError("explanation required, not semantically scored")
        if (not isinstance(evidence_ids,list) or any(not isinstance(e,str) for e in evidence_ids)
                or len(set(evidence_ids))!=len(evidence_ids)
                or any(e not in self.runs and e not in self.artifacts for e in evidence_ids)):
            raise ValueError("evidence must identify purchased information")
        self.submission = dict(verdict=verdict,diagnosis=diagnosis,evidence_ids=evidence_ids,justification=justification)
        self.state = "submitted"
        return self.result("submitted", submission=self.submission)

    def abort(self, reason):
        if self.state == "active":
            self.state, self.reason = "aborted", str(reason)

    def evaluate(self):
        attempted = self.submission["verdict"] if self.submission else None
        verdict = attempted if self.state == "submitted" else None
        truth = self.study["private"]["claim_valid"]
        return {"case_id":self.study["case_id"], "claim_valid":truth, "verdict":verdict, "attempted_verdict":attempted,
                "correct":verdict==("ACCEPT" if truth else "REJECT"),
                "covered":verdict in ("ACCEPT","REJECT"), "abstained":verdict=="ABSTAIN",
                "incomplete":self.state!="submitted", "false_accept":verdict=="ACCEPT" and not truth,
                "false_reject":verdict=="REJECT" and truth, "spent":self.spent,"remaining":self.remaining,
                "reference":self.study["private"]["reference"], "reason":self.reason, "explanation_scored":False}
