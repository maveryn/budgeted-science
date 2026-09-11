"""Budgeted public audit facade and private verdict evaluation.

This is trusted-process separation, not a sandbox against Python introspection.
"""

from copy import deepcopy
import inspect
from math import fsum

from ..agents.records import digest
from .numerics import Backend, cache_key, configuration, number, output_grid, peak
from .studies import configuration_text, trajectory_csv, validate_study


ACTIONS = ("list_artifacts", "read_artifact", "recompute_peak", "refine_integration",
           "refine_sampling", "compare_runs", "budget", "submit")
COSTS = {"refine_integration": 3.0, "refine_sampling": 2.0}


class PublicTools:
    __slots__ = ("__episode",)

    def __init__(self, episode):
        self.__episode = episode

    def call(self, name, arguments=None, call_id=None):
        return self.__episode.dispatch(name, {} if arguments is None else arguments, call_id)

    def list_artifacts(self):
        return self.call("list_artifacts")

    def read_artifact(self, id, offset=0, limit=200):
        return self.call("read_artifact", dict(id=id, offset=offset, limit=limit))

    def recompute_peak(self, run_id):
        return self.call("recompute_peak", dict(run_id=run_id))

    def refine_integration(self, run_id):
        return self.call("refine_integration", dict(run_id=run_id))

    def refine_sampling(self, run_id):
        return self.call("refine_sampling", dict(run_id=run_id))

    def compare_runs(self, run_ids):
        return self.call("compare_runs", dict(run_ids=run_ids))

    def budget(self):
        return self.call("budget")

    def submit(self, verdict, diagnosis, evidence_ids, justification):
        return self.call("submit", dict(verdict=verdict, diagnosis=diagnosis,
                                       evidence_ids=evidence_ids, justification=justification))


class Episode:
    def __init__(self, study, credits=5, backend=None, log=None):
        self.study = deepcopy(validate_study(study))
        self.limit = number(credits, "credits")
        if self.limit < 0:
            raise ValueError("budget cannot be negative")
        self.backend = Backend() if backend is None else backend
        self.log = log
        self.state, self.submission, self.reason = "active", None, None
        self.ledger, self.calls = [], {}
        self.artifacts = deepcopy(study["artifacts"])
        self.runs = {study["run_id"]: deepcopy(study["run"])}
        self.keys = {cache_key(study["private"]["theta"], study["run"]["config"]): study["run_id"]}
        self.tools = PublicTools(self)

    @property
    def spent(self):
        return fsum(item["charge"] for item in self.ledger)

    @property
    def remaining(self):
        return self.limit - self.spent

    def emit(self, kind, **data):
        if self.log:
            try:
                self.log(kind, **deepcopy(data))
            except BaseException:
                self.state, self.reason = "aborted", "logging interrupted"
                raise

    def _result(self, status="success", charge=0.0, **data):
        return {"status": status, "charge": charge, "remaining": self.remaining, **data}

    def dispatch(self, name, arguments, call_id=None):
        # Record every delivered request/result, including rejected requests and
        # exact duplicate replies. Only the internal dispatcher can buy work.
        try:
            digest({"name": name, "arguments": arguments, "call_id": call_id})
        except (ValueError, TypeError):
            self.emit("tool_call", malformed_request=repr(
                {"name": name, "arguments": arguments, "call_id": call_id}))
            result = self._result("invalid", error="request must contain finite JSON values")
            self.emit("tool_result", result=result)
            return result
        self.emit("tool_call", name=name, arguments=arguments, call_id=call_id)
        result = self._dispatch(name, arguments, call_id)
        self.emit("tool_result", name=name, call_id=call_id, result=result)
        return deepcopy(result)

    def _dispatch(self, name, arguments, call_id=None):
        if name not in ACTIONS or not isinstance(arguments, dict):
            return self._result("invalid", error="unknown action or malformed arguments")
        if call_id is not None and (not isinstance(call_id, str) or not call_id):
            return self._result("invalid", error="call ID must be a nonempty string")
        try:
            signature = digest({"name": name, "arguments": arguments})
        except (ValueError, TypeError):
            return self._result("invalid", error="arguments must be finite JSON values")
        if call_id in self.calls:
            previous = self.calls[call_id]
            if previous["signature"] != signature:
                return self._result("invalid", error="call ID reused with different arguments")
            self.emit("duplicate_call", call_id=call_id)
            # Deliver the original result verbatim; no re-execution or repurchase.
            return deepcopy(previous["result"])
        if self.state != "active":
            return self._result("closed", error="episode is closed")
        operation = getattr(self, "_" + name)
        try:
            inspect.signature(operation).bind(**arguments)
            result = operation(**arguments)
        except (ValueError, TypeError, KeyError) as exc:
            if self.state != "active":
                raise
            result = self._result("invalid", error=str(exc))
        if call_id is not None:
            self.calls[call_id] = {"signature": signature, "result": deepcopy(result)}
        return deepcopy(result)

    def _budget(self):
        return self._result(total=self.limit, spent=self.spent, costs=COSTS,
                            ledger=self.ledger, original_run_id=self.study["run_id"])

    def _list_artifacts(self):
        return self._result(artifacts=[{"id": key, "role": artifact["role"],
                                      "media_type": artifact["media_type"],
                                      "run_id": artifact["run_id"]}
                                     for key, artifact in self.artifacts.items()])

    def _read_artifact(self, id, offset=0, limit=200):
        if not isinstance(id, str) or id not in self.artifacts:
            raise ValueError("unknown or unavailable artifact")
        if (type(offset) is not int or offset < 0 or type(limit) is not int
                or not 1 <= limit <= 200):
            raise ValueError("offset must be nonnegative; limit must be in [1, 200]")
        artifact = self.artifacts[id]
        lines = artifact["content"].splitlines(keepends=True)
        end = min(offset + limit, len(lines))
        return self._result(id=id, role=artifact["role"], media_type=artifact["media_type"],
                            run_id=artifact["run_id"], content="".join(lines[offset:end]),
                            offset=offset, total_lines=len(lines),
                            next_offset=end if end < len(lines) else None)

    def _run(self, run_id):
        if not isinstance(run_id, str) or run_id not in self.runs:
            raise ValueError("unknown or unavailable run")
        if self.runs[run_id]["status"] != "success":
            raise ValueError("run did not complete")
        return self.runs[run_id]

    def _recompute_peak(self, run_id):
        return self._result(run_id=run_id, **peak(self._run(run_id)))

    def _compare_runs(self, run_ids):
        if not isinstance(run_ids, list) or len(run_ids) < 2 or len(set(run_ids)) != len(run_ids):
            raise ValueError("provide at least two distinct purchased run IDs")
        values = [{"run_id": key, **peak(self._run(key))} for key in run_ids]
        base = values[0]["q"]
        differences = [{"run_id": row["run_id"], "signed_difference": row["q"] - base,
                        "absolute_difference": abs(row["q"] - base),
                        "relative_difference_wrt_first": abs(row["q"] - base) / abs(base)}
                       for row in values[1:]]
        return self._result(runs=values, differences=differences,
                            warning="Differences are not certified error bounds or claim verdicts.")

    def _refine_integration(self, run_id):
        run = self._run(run_id)
        config = configuration(rtol=1e-10, atol=1e-12, times=run["times"])
        return self._purchase("refine_integration", run_id, config)

    def _refine_sampling(self, run_id):
        config = deepcopy(self._run(run_id)["config"])
        config["output_times"] = output_grid(.0025)
        return self._purchase("refine_sampling", run_id, config)

    def _compact(self, run_id, charge, episode_reuse, backend_hit):
        run = self.runs[run_id]
        fields = {"run_id": run_id, "episode_reuse": episode_reuse, "backend_cache_hit": backend_hit,
                  "numerical_settings": {k: v for k, v in run["config"].items() if k != "output_times"},
                  "artifact_ids": [key for key, a in self.artifacts.items() if a["run_id"] == run_id]}
        if run["status"] == "success":
            fields.update(peak(run))
        else:
            fields["error"] = "verification computation failed"
        return self._result(run["status"], charge=charge, **fields)

    def _purchase(self, action, parent_id, config):
        theta = self.study["private"]["theta"]
        key = cache_key(theta, config)
        if key in self.keys:
            return self._compact(self.keys[key], 0.0, True, False)
        charge = COSTS[action]
        if charge > self.remaining:
            return self._result("unaffordable", error="insufficient audit credits")
        run_id = "run-" + digest({"case": self.study["case_id"], "config": config})[:14]
        entry = {"action": action, "run_id": run_id, "parent_run_id": parent_id,
                 "charge": charge, "status": "pending"}
        self.ledger.append(entry)
        try:
            self.emit("charged", entry=entry, spent=self.spent, remaining=self.remaining)
        except BaseException:
            # The backend was never entered; a failed write is not scientific work.
            entry.update(charge=0.0, status="not_executed")
            raise
        # Backend retrieval is permitted, but does not waive this episode's charge.
        try:
            run, hit = self.backend.get(theta, config)
        except BaseException:
            entry["status"] = "interrupted"
            self.state, self.reason = "aborted", "computation interrupted"
            raise
        self.runs[run_id], self.keys[key] = run, run_id
        entry["status"] = run["status"]
        if run["status"] == "success":
            content = [("solver_log", "text/plain", configuration_text(config) + "\n"),
                       ("trajectory", "text/csv", trajectory_csv(run)),
                       ("analysis", "text/plain", f"Maximum of stored x samples: {peak(run)['q']:.17g}\n")]
            for index, (role, media, text) in enumerate(content):
                self.artifacts[run_id + f"-a{index + 1}"] = {
                    "role": role, "media_type": media, "content": text, "run_id": run_id}
        self.emit("numerical_artifact", run_id=run_id, parent_run_id=parent_id,
                  artifact=run, backend_cache_hit=hit)
        return self._compact(run_id, charge, False, hit)

    def _submit(self, verdict, diagnosis, evidence_ids, justification):
        if verdict not in ("ACCEPT", "REJECT", "ABSTAIN"):
            raise ValueError("verdict must be ACCEPT, REJECT, or ABSTAIN")
        if any(not isinstance(text, str) or not text.strip() for text in (diagnosis, justification)):
            raise ValueError("diagnosis and justification must be nonempty strings")
        if (not isinstance(evidence_ids, list) or any(not isinstance(k, str) for k in evidence_ids)
                or len(set(evidence_ids)) != len(evidence_ids)):
            raise ValueError("evidence IDs must be a list of distinct strings")
        if any(key not in self.artifacts and key not in self.runs for key in evidence_ids):
            raise ValueError("evidence must refer to available artifacts or runs")
        self.submission = {"verdict": verdict, "diagnosis": diagnosis,
                           "evidence_ids": evidence_ids, "justification": justification}
        self.state = "submitted"
        return self._result("submitted", submission=self.submission)

    def abort(self, reason):
        if self.state == "active":
            self.state, self.reason = "aborted", str(reason)

    def evaluate(self):
        valid = self.state == "submitted"
        verdict = self.submission["verdict"] if valid else None
        truth = self.study["private"]["claim_valid"]
        return {"case_id": self.study["case_id"], "status": self.state,
                "valid_submission": valid, "incomplete": not valid,
                "verdict": verdict, "claim_valid": truth,
                "correct": verdict == ("ACCEPT" if truth else "REJECT"),
                "covered": verdict in ("ACCEPT", "REJECT"),
                "abstained": verdict == "ABSTAIN",
                "false_accept": verdict == "ACCEPT" and not truth,
                "false_reject": verdict == "REJECT" and truth,
                "spent": self.spent, "remaining": self.remaining,
                "reason": self.reason, "reference_q": self.study["private"]["reference_q"],
                "reported_q": self.study["reported_q"],
                "relative_error": self.study["private"]["relative_error"],
                "explanation_scored": False}


def summarize(evaluations):
    count = len(evaluations)
    invalid = sum(not item["claim_valid"] for item in evaluations)
    valid = count - invalid
    total = lambda key: sum(bool(item[key]) for item in evaluations)
    return {"episodes": count, "correct": total("correct"),
            "accuracy": total("correct") / count if count else None,
            "coverage": total("covered") / count if count else None,
            "abstentions": total("abstained"), "incomplete": total("incomplete"),
            "false_accepts": total("false_accept"), "invalid_claims": invalid,
            "false_acceptance_rate": total("false_accept") / invalid if invalid else None,
            "false_rejects": total("false_reject"), "valid_claims": valid,
            "false_rejection_rate": total("false_reject") / valid if valid else None,
            "credits_spent": [item["spent"] for item in evaluations]}
