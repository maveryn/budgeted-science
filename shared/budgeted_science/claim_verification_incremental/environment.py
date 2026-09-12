"""Reuse accounting/artifacts, replacing only the two refinement operations."""
from copy import deepcopy

from ..claim_verification.environment import Episode


def bisect_times(times):
    return sorted(set(times) | {round((a + b) / 2, 14) for a, b in zip(times[:-1], times[1:])})


class IncrementalEpisode(Episode):
    def __init__(self, study, credits=8, backend=None, log=None):
        if study["run"]["config"]["method"] != "Euler":
            raise ValueError("incremental pilot requires an Euler original study")
        super().__init__(study, credits=credits, backend=backend, log=log)

    def _refine_integration(self, run_id):
        config = deepcopy(self._run(run_id)["config"])
        config["dt"] /= 2
        return self._purchase("refine_integration", run_id, config)

    def _refine_sampling(self, run_id):
        config = deepcopy(self._run(run_id)["config"])
        config["output_times"] = bisect_times(config["output_times"])
        return self._purchase("refine_sampling", run_id, config)

    def _budget(self):
        result = super()._budget()
        result["refinement_contract"] = {
            "integration": "halve current Euler timestep, preserve all output times; cost 3",
            "sampling": "bisect every output interval, preserve Euler timestep; cost 2"}
        return result
