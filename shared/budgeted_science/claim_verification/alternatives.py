"""Optional, genuine numerical alternatives; the original audit is unchanged."""
from copy import deepcopy
import inspect

from ..agents.records import digest
from .environment import ACTIONS, COSTS, Episode
from .numerics import cache_key, configuration, peak
from .studies import configuration_text, trajectory_csv

VERSION = "predator-prey-alternative-tools-1"
EXTRA_COSTS = {"tighten_integration": 1.0, "bisect_output": 1.0,
               "crosscheck_integrator": 3.0}


class AlternativeEpisode(Episode):
    action_names = (*ACTIONS, *EXTRA_COSTS)
    action_costs = {**COSTS, **EXTRA_COSTS}

    # Keep extension dispatch/pricing local: archived experiments verify the
    # original environment's exact source hash, not only its behavior.
    def _dispatch(self, name, arguments, call_id=None):
        if name not in self.action_names or not isinstance(arguments, dict):
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
        return self._result(total=self.limit, spent=self.spent, costs=self.action_costs,
                            ledger=self.ledger, original_run_id=self.study["run_id"])

    def _purchase(self, action, parent_id, config):
        theta = self.study["private"]["theta"]
        key = cache_key(theta, config)
        if key in self.keys:
            return self._compact(self.keys[key], 0.0, True, False)
        charge = self.action_costs[action]
        if charge > self.remaining:
            return self._result("unaffordable", error="insufficient audit credits")
        run_id = "run-" + digest({"case": self.study["case_id"], "config": config})[:14]
        entry = {"action": action, "run_id": run_id, "parent_run_id": parent_id,
                 "charge": charge, "status": "pending"}
        self.ledger.append(entry)
        try:
            self.emit("charged", entry=entry, spent=self.spent, remaining=self.remaining)
        except BaseException:
            entry.update(charge=0.0, status="not_executed")
            raise
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

    def _tighten_integration(self, run_id):
        config = deepcopy(self._run(run_id)["config"])
        if config["method"] == "Euler":
            config["dt"] /= 2
        else:
            config["rtol"] /= 10
            config["atol"] /= 10
        return self._purchase("tighten_integration", run_id, config)

    def _bisect_output(self, run_id):
        config = deepcopy(self._run(run_id)["config"])
        times = config["output_times"]
        config["output_times"] = sorted(set(times + [(a+b)/2 for a, b in zip(times[:-1], times[1:])]))
        return self._purchase("bisect_output", run_id, config)

    def _crosscheck_integrator(self, run_id):
        config = configuration("Radau", rtol=1e-10, atol=1e-12,
                               times=self._run(run_id)["times"])
        return self._purchase("crosscheck_integrator", run_id, config)
