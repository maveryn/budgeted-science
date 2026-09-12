"""Raw numerical service for sandbox analysis; no agent code runs on the host."""
from copy import deepcopy
import inspect

from .environment import Episode
from .numerics import cache_key, configuration, output_grid
from ..agents.records import digest

VERSION = "prey-raw-analysis-v1"
ACTIONS = ("simulate", "run_record", "budget", "submit")


def public_run(run_id, run):
    """Explicit allowlist: no theta, internal interpolation, reference, or label."""
    result = {"run_id": run_id, "status": run["status"], "config": deepcopy(run["config"]),
              "columns": ["x", "y"]}
    if run["status"] == "success":
        result.update(times=list(run["times"]), values=deepcopy(run["values"]))
    return result


def requested_config(source, method, dt, rtol, atol, output_spacing, output_phase):
    if not (0 <= output_phase < 1 and (output_spacing == 0 or .0025 <= output_spacing <= 4)):
        raise ValueError("spacing must be 0 (inherit) or [0.0025,4]; phase in [0,1)")
    if not (.001 <= dt <= .32 and 1e-12 <= rtol <= 1e-3 and 1e-14 <= atol <= 1e-6):
        raise ValueError("numerical settings outside declared service bounds")
    if output_spacing == 0 and output_phase != 0:
        raise ValueError("inherited schedule requires phase=0")
    times = source["times"] if output_spacing == 0 else output_grid(output_spacing, output_phase)
    return configuration(method, dt=dt, rtol=rtol, atol=atol, times=times)


def settings_charge(source, config):
    integration = lambda c: {k: v for k, v in c.items() if k != "output_times"}
    return (3.0 * (integration(source["config"]) != integration(config))
            + 2.0 * (source["times"] != config["output_times"]))


class RawEpisode(Episode):
    """Reuse verdicts/cache mechanics, but do not expose specialized audit actions."""
    def _dispatch(self, name, arguments, call_id=None):
        if name not in ACTIONS or not isinstance(arguments, dict):
            return self._result("invalid", error="unknown action or malformed arguments")
        if call_id is not None and (not isinstance(call_id, str) or not call_id):
            return self._result("invalid", error="invalid call ID")
        signature = digest([name, arguments])
        if call_id in self.calls:
            old = self.calls[call_id]
            return (deepcopy(old["result"]) if old["signature"] == signature else
                    self._result("invalid", error="call ID conflict"))
        if self.state != "active":
            return self._result("closed", error="episode closed")
        try:
            operation = getattr(self, "_" + name)
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
        return self._result(total=self.limit, spent=self.spent, ledger=self.ledger,
                            original_run_id=self.study["run_id"])

    def _run_record(self, run_id):
        if run_id not in self.runs:
            raise ValueError("unknown or unpurchased run")
        return self._result(run=public_run(run_id, self.runs[run_id]))

    def _simulate(self, source_run_id, method, dt, rtol, atol, output_spacing, output_phase):
        source = self._run(source_run_id)
        config = requested_config(source, method, dt, rtol, atol, output_spacing, output_phase)
        theta = self.study["private"]["theta"]
        key = cache_key(theta, config)
        if key in self.keys:
            run_id = self.keys[key]
            return self._result(self.runs[run_id]["status"], run_id=run_id, reused=True,
                                run=public_run(run_id, self.runs[run_id]))
        charge = settings_charge(source, config)
        if charge > self.remaining:
            return self._result("unaffordable", error="insufficient audit credits")
        run_id = "run-" + digest({"case": self.study["case_id"], "config": config})[:14]
        entry = {"action": "simulate", "run_id": run_id, "parent_run_id": source_run_id,
                 "charge": charge, "status": "pending"}
        self.ledger.append(entry)
        try:
            self.emit("charged", entry=entry, spent=self.spent, remaining=self.remaining)
        except BaseException:
            entry.update(charge=0, status="not_executed")
            raise
        try:
            run, hit = self.backend.get(theta, config)
        except BaseException:
            entry["status"] = "interrupted"
            self.abort("computation interrupted")
            raise
        self.runs[run_id], self.keys[key] = run, run_id
        entry["status"] = run["status"]
        self.emit("numerical_artifact", run_id=run_id, parent_run_id=source_run_id,
                  artifact=run, backend_cache_hit=hit)
        return self._result(run["status"], charge=charge, run_id=run_id, reused=False,
                            run=public_run(run_id, run))


def fixed_raw_audit(episode):
    """Transparent fixed CPU comparison using only public report and raw service."""
    # Report is public. The reference and case category never enter this policy.
    import re
    report = next(a["content"] for a in episode.artifacts.values() if a["role"] == "report")
    reported = float(re.search(r"maximum population.*? is ([\d.eE+-]+),", report).group(1))
    original = episode.study["run_id"]
    result = episode.tools.call("simulate", dict(source_run_id=original, method="DOP853",
        dt=.01, rtol=1e-10, atol=1e-12, output_spacing=.0025, output_phase=0), "cpu-solve")
    verdict, evidence = "ABSTAIN", [original]
    checked = None
    if result["status"] == "success":
        checked = max(pair[0] for pair in result["run"]["values"])
        verdict = "ACCEPT" if abs(reported-checked)/abs(checked) <= .05 else "REJECT"
        evidence.append(result["run_id"])
    episode.tools.call("submit", dict(verdict=verdict, diagnosis="Fixed numerical comparison",
        evidence_ids=evidence, justification=f"Reported Q={reported}; computed sample peak={checked}. "
        "Not a certified error bound."), "cpu-submit")
    return {"evaluation": episode.evaluate(), "submission": episode.submission,
            "reported_q": reported, "checked_q": checked}
