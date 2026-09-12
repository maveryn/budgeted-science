"""Independent CPU audit ledger and public fit/predict interfaces."""
from copy import deepcopy
import math

from ..agents.records import digest
from . import VERSION, numerics as num


class PublicTools:
    def __init__(self, episode):
        self._episode = episode

    def call(self, name, arguments=None, call_id=None):
        return self._episode.call(name, arguments, call_id)


class Episode:
    def __init__(self, study, credits, log=None):
        if isinstance(credits, bool) or not math.isfinite(credits) or credits < 0 or not float(credits*num.WORK_UNIT).is_integer():
            raise ValueError("budget must be nonnegative integer RHS work units")
        self.study, self.log = deepcopy(study), log
        self.limit, self.spent = int(credits*num.WORK_UNIT), 0
        self.work_by_stage = {"calibration": 0, "prediction": 0}
        self.state, self.submission, self.calls = "active", None, {}
        self.runs = {"original-calibration": deepcopy(study["calibration"]),
                     "original-prediction": deepcopy(study["prediction"])}
        self.cache = {self.key(r["theta"], r["experiment"], r["method"]): k for k, r in self.runs.items()}
        self.partial_cache = {}
        self.fits = {"original-fit": deepcopy(study["fit"])}
        self.tools = PublicTools(self)

    @staticmethod
    def key(p, experiment, method):
        return digest({"version": VERSION, "theta": list(p), "experiment": experiment, "method": method,
                       "settings": num.METHODS[method], "cal_times": num.CAL_TIMES.tolist(),
                       "pred_times": num.PRED_TIMES.tolist(), "initials": [num.CAL_INITIAL, num.PRED_INITIAL]})

    def budget(self):
        return {"work_limit": self.limit, "work_spent": self.spent, "work_remaining": self.limit-self.spent,
                "credits_spent": self.spent/num.WORK_UNIT, "credits_remaining": (self.limit-self.spent)/num.WORK_UNIT}

    def emit(self, kind, **data):
        if self.log:
            self.log.event(kind, **data)

    def purchase(self, p, experiment, method, max_work):
        p = num.theta(p)
        if method not in num.METHODS or experiment not in ("calibration", "prediction"):
            raise ValueError("unknown experiment or method")
        num.integer(max_work, "max_work")
        key = self.key(p, experiment, method)
        cap = min(max_work, self.limit-self.spent)
        prior = self.cache.get(key) or self.partial_cache.get((key, cap))
        if prior:
            self.emit("solver_reuse", result_id=prior, charge_work=0)
            return {"result_id": prior, **deepcopy(self.runs[prior]), "charge_work": 0, "reuse": True}
        if cap == 0:
            raise num.WorkExhausted("no work remains for a new solve")
        self.emit("solver_started", theta=p.tolist(), experiment=experiment, method=method, work_cap=cap)
        try:
            run = num.solve(p, experiment, method, cap)
            if type(run["work"]) is not int or not 0 <= run["work"] <= cap:
                raise RuntimeError("invalid work accounting")
        except Exception:
            self.spent += cap  # Retain reservation after an unaccounted failure.
            self.work_by_stage[experiment] += cap
            self.state = "aborted"
            self.emit("unaccounted_failure", retained_work=cap, budget=self.budget())
            raise
        self.spent += run["work"]
        self.work_by_stage[experiment] += run["work"]
        rid = "run-"+digest([key, run["status"], run["work"]])[:14]
        self.runs[rid] = run
        if run["status"] == "budget_exhausted":
            self.partial_cache[key, cap] = rid
        else:
            self.cache[key] = rid
        if self.log:
            artifact = self.log.write_json("numerical/"+rid+".json", run)
        else:
            artifact = None
        self.emit("solver_finished", result_id=rid, status=run["status"], artifact=artifact,
                  charge_work=run["work"], budget=self.budget())
        return {"result_id": rid, **deepcopy(run), "charge_work": run["work"], "reuse": False}

    def call(self, name, arguments=None, call_id=None):
        args = deepcopy({} if arguments is None else arguments)
        signature = digest([name, args])
        if call_id is not None and call_id in self.calls:
            previous, result = self.calls[call_id]
            if previous != signature:
                raise ValueError("call ID conflict")
            return deepcopy(result)
        if self.state != "active":
            raise ValueError("episode is closed")
        self.emit("tool_request", name=name, arguments=args, call_id=call_id)
        try:
            result = self.execute(name, args)
        except (ValueError, KeyError, TypeError, num.WorkExhausted) as exc:
            result = {"error": str(exc)}
        result["budget"] = self.budget()
        self.emit("tool_result", name=name, result=result, call_id=call_id)
        if call_id is not None:
            self.calls[call_id] = (signature, deepcopy(result))
        return result

    def execute(self, name, args):
        if not isinstance(args, dict):
            raise ValueError("arguments must be an object")
        if name in ("describe", "budget"):
            if args:
                raise ValueError("no arguments expected")
            if name == "budget":
                return {}
            return {"study": deepcopy(self.study["public"]), "fit": deepcopy(self.fits["original-fit"]),
                    "prediction": self.summary("original-prediction")}
        if name == "record":
            if set(args) != {"id"}:
                raise ValueError("record id required")
            key = args["id"]
            value = self.fits[key] if key in self.fits else self.runs[key]
            return {"id": key, "record": deepcopy(value)}
        if name == "register_fit":
            if set(args) != {"theta"}:
                raise ValueError("theta required")
            p = num.theta(args["theta"]).tolist()
            fid = "fit-"+digest(p)[:14]
            self.fits.setdefault(fid, {"theta": p, "rmse": None, "result_id": None})
            return {"fit_id": fid, "fit": deepcopy(self.fits[fid]), "note": "Registered, not numerically validated; no simulation executed."}
        if name in ("fit_step", "fit_full"):
            if set(args) != {"fit_id", "method", "max_work"} or args["method"] not in ("dop_loose", "dop_tight"):
                raise ValueError("fit_id, calibration method and max_work required")
            original = self.fits[args["fit_id"]]
            num.integer(args["max_work"], "max_work")
            start_work = self.spent
            def predictor(p):
                remaining = max(0, args["max_work"]-(self.spent-start_work))
                r = self.purchase(p, "calibration", args["method"], remaining)
                if r["status"] != "complete":
                    raise num.WorkExhausted("calibration calculation incomplete")
                return r
            function = num.fit_step if name == "fit_step" else num.fit_full
            outcome = function(original["theta"], self.study["public"]["data"], predictor)
            best = outcome["best"]
            if best is None:
                return {"status": outcome["status"], "fit_id": args["fit_id"], "fit": deepcopy(original), "history": outcome["history"]}
            # Do not compare differently resolved residuals as if exact; register
            # the best completed candidate within this action's declared predictor.
            fid = "fit-"+digest([best["theta"], best["result_id"]])[:14]
            self.fits[fid] = deepcopy(best)
            return {"status": outcome["status"], "fit_id": fid, "fit": deepcopy(best), "history": outcome["history"]}
        if name == "predict":
            if set(args) != {"fit_id", "method", "max_work"}:
                raise ValueError("fit_id, method and max_work required")
            r = self.purchase(self.fits[args["fit_id"]]["theta"], "prediction", args["method"], args["max_work"])
            return {**self.summary(r["result_id"]), "charge_work": r["charge_work"], "reuse": r["reuse"]}
        if name == "submit":
            if set(args) != {"verdict", "evidence_ids", "justification"} or args["verdict"] not in ("ACCEPT", "REJECT", "ABSTAIN") or not isinstance(args["justification"], str):
                raise ValueError("invalid submission")
            if not isinstance(args["evidence_ids"], list) or any(not isinstance(i, str) or i not in self.fits and i not in self.runs for i in args["evidence_ids"]):
                raise ValueError("unknown evidence ID")
            self.submission, self.state = deepcopy(args), "submitted"
            return {"status": "submitted"}
        raise ValueError("unknown action")

    def summary(self, rid):
        r = self.runs[rid]
        return {"result_id": rid, **{k: deepcopy(r[k]) for k in ("theta", "method", "experiment", "status", "q", "work")}}

    def evaluation(self):
        reference = self.study["reference"]["q"]
        claim = self.study["public"]["claim"]
        error = abs(claim["value"]-reference)/abs(reference)
        valid = error <= claim["tolerance"]+1e-12
        verdict = self.submission["verdict"] if self.state == "submitted" else None
        return {"reference": reference, "relative_claim_error": error, "valid": valid, "verdict": verdict,
                "correct": verdict == ("ACCEPT" if valid else "REJECT"),
                "abstained": verdict == "ABSTAIN", "incomplete": verdict is None,
                "spent": self.spent/num.WORK_UNIT, "work_spent": self.spent,
                "work_by_stage": deepcopy(self.work_by_stage)}
