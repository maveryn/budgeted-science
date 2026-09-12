"""Trusted in-process audit facade, exact ledger, cache and objective scoring."""
from copy import deepcopy
from dataclasses import asdict
from math import isfinite
from time import perf_counter

from ..agents.records import digest
from . import VERSION
from .catalog import public_study
from .numerics import DIAGNOSTIC, PROBLEMS, STUDY_PROFILES, charge_units, errors, solve

VERDICTS = ("ACCEPT", "REJECT", "ABSTAIN")


def score(submission, case):
    result = {"complete": submission is not None}
    for name in ("qoi", "order"):
        verdict = submission[name] if submission else None
        truth = case["private"][name+"_truth"]
        correct = verdict == ("ACCEPT" if truth else "REJECT")
        result[name] = {"truth": truth, "verdict": verdict, "correct": correct,
                        "covered": verdict in ("ACCEPT", "REJECT"),
                        "false_accept": verdict == "ACCEPT" and not truth,
                        "false_reject": verdict == "REJECT" and truth}
    result["joint_correct"] = result["qoi"]["correct"] and result["order"]["correct"]
    return result


class Audit:
    def __init__(self, case, budget, *, backend=None, sink=None, executor=solve):
        if isinstance(budget, bool) or not isinstance(budget, (int, float)) or not isfinite(budget) or budget < 0:
            raise ValueError("budget must be nonnegative and finite")
        self._case = case
        self._limit = int(round(budget*289))
        if abs(self._limit/289-budget) > 1e-9:
            raise ValueError("budget must be representable in grid units")
        self._spent, self._requests = 0, 0
        self._backend = {} if backend is None else backend
        self._sink, self._executor = sink, executor
        self._purchases, self._calls = {}, {}
        self._records = {"original": {"id": "original", "kind": "study", "kernel": "audited",
                                     **deepcopy(case["original"])}}
        self._submission = None
        self._started = perf_counter()

    def _event(self, kind, **data):
        if self._sink:
            self._sink(kind, **deepcopy(data))

    def describe(self):
        return {**public_study(self._case), "budget": self.status(),
                "cost_rule": "(grid+1)^2/289 credits per new solve; grid-size proxy, not measured work or runtime."}

    def status(self):
        return {"limit": self._limit/289, "spent": self._spent/289,
                "remaining": (self._limit-self._spent)/289, "submitted": self._submission is not None}

    def artifacts(self):
        return deepcopy(self._records)

    @property
    def submission(self):
        return deepcopy(self._submission)

    def call(self, call_id, action, **arguments):
        if not isinstance(call_id, str) or not call_id:
            raise ValueError("nonempty call ID required")
        fingerprint = digest({"action": action, "arguments": arguments})
        if call_id in self._calls:
            old, response = self._calls[call_id]
            if old != fingerprint:
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
            if action == "run_study":
                result = self._run("study", **arguments)
            elif action == "run_mms":
                result = self._run("mms", **arguments)
            elif action == "record":
                if set(arguments) != {"result_id"} or arguments["result_id"] not in self._records:
                    raise ValueError("unknown record")
                result = deepcopy(self._records[arguments["result_id"]])
            elif action == "budget":
                if arguments:
                    raise ValueError("budget takes no arguments")
                result = self.status()
            elif action == "submit":
                result = self._submit(**arguments)
            else:
                raise ValueError("unknown action")
            response = {"ok": True, "result": result, "budget": self.status()}
        except (ValueError, TypeError, KeyError) as exc:
            response = {"ok": False, "error": str(exc), "budget": self.status()}
        self._calls[call_id] = (fingerprint, deepcopy(response))
        self._event("response", call_id=call_id, response=response)
        return response

    def _run(self, kind, grid, kernel="audited", family=None):
        units = charge_units(grid)
        if kernel not in ("audited", "independent"):
            raise ValueError("unknown kernel")
        if kind == "study" and family is not None:
            raise ValueError("study family cannot be changed")
        if kind == "mms" and family not in PROBLEMS:
            raise ValueError("unknown MMS family")
        family = family if kind == "mms" else self._case["family"]
        profile = DIAGNOSTIC if kind == "mms" else STUDY_PROFILES[family]
        problem = PROBLEMS[family]
        key = digest({"version": VERSION, "kind": kind, "problem": asdict(problem),
                      "profile": asdict(profile), "grid": grid, "kernel": kernel,
                      "flavor": self._case["flavor"] if kernel == "audited" else "sound"})
        if kind == "study" and kernel == "audited" and grid == self._case["grid"]:
            return self._compact(self._records["original"], "episode_reuse", 0)
        if key in self._purchases:
            return self._compact(self._records[self._purchases[key]], "episode_reuse", 0)
        if self._spent+units > self._limit:
            raise ValueError("insufficient scientific budget")
        self._spent += units
        hit = key in self._backend
        self._event("purchase", kind_of_solve=kind, grid=grid, kernel=kernel,
                    charged_units=units, backend_cache_hit=hit, budget=self.status())
        if hit:
            numerical = deepcopy(self._backend[key])
        else:
            try:
                numerical = self._executor(problem, profile, grid, self._case["flavor"], kernel)
            except Exception as exc:
                numerical = {"status": "failed", "grid": grid, "message": type(exc).__name__}
            self._backend[key] = deepcopy(numerical)
        result_id = f"run-{len(self._purchases)+1:03d}"
        result = {"id": result_id, "kind": kind, "family": family, "kernel": kernel, **numerical}
        if kind == "mms" and result["status"] == "complete":
            result["diagnostic_errors"] = errors(result, profile)
        self._records[result_id] = result
        self._purchases[key] = result_id
        self._event("numerical", backend_cache_hit=hit, charged_units=units, artifact=result)
        return self._compact(result, "backend_cache" if hit else "executed", units/289)

    @staticmethod
    def _compact(result, origin, charge):
        return {**{k: deepcopy(v) for k, v in result.items() if k != "field"},
                "origin": origin, "charge": charge}

    def _submit(self, qoi, order, evidence_ids, explanation=""):
        if qoi not in VERDICTS or order not in VERDICTS:
            raise ValueError("verdict must be ACCEPT, REJECT, or ABSTAIN")
        if not isinstance(explanation, str) or not isinstance(evidence_ids, list) or any(
            not isinstance(i, str) or i not in self._records for i in evidence_ids
        ):
            raise ValueError("known purchased evidence IDs and string explanation required")
        self._submission = {"qoi": qoi, "order": order, "evidence_ids": evidence_ids,
                            "explanation": explanation}
        return {"submitted": True}
