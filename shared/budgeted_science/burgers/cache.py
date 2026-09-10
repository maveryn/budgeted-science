"""Backend acceleration does not make a new episode's scientific work free."""

import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import perf_counter
from zipfile import BadZipFile

import numpy as np

from .config import RECORD_TIMES, SolverConfig
from .numerics import SimulationResult, solve_candidate


def cache_key(config):
    if not isinstance(config, SolverConfig):
        raise ValueError("config must be SolverConfig")
    return hashlib.sha256(json.dumps(config.identity(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class SimulationCache:
    """Versioned successful simulations only; private backend files, no pickle."""

    def __init__(self, directory=None):
        self._directory = None if directory is None else Path(directory)
        self._memory = {}

    def get(self, config):
        key = cache_key(config)
        if key in self._memory:
            return self._memory[key].copy()
        if self._directory is None:
            return None
        path = self._directory / f"{key}.npz"
        if not path.is_file():
            return None
        try:
            # Own the file handle even if NumPy rejects a truncated archive
            # before it can return a context manager.
            with path.open("rb") as stream, np.load(stream, allow_pickle=False) as data:
                meta = json.loads(str(data["metadata"].item()))
                ts, fields = np.array(data["times"]), np.array(data["fields"])
            if meta["config"] != config.identity() or meta["schema"] != 1:
                return None
            steps, evaluations, work = meta["steps"], meta["evaluations"], meta["work"]
            if any(type(v) is not int or v <= 0 for v in (steps, evaluations, work)):
                return None
            if evaluations != 2 * steps or work != config.resolution * evaluations:
                return None
            if not np.array_equal(ts, np.array((0.0,) + RECORD_TIMES)):
                return None
            if (fields.shape != (6, config.resolution) or fields.dtype.kind not in "iuf"
                    or not np.all(np.isfinite(fields))):
                return None
            result = SimulationResult(config, ts, fields, work, evaluations, steps, 1.0,
                                      "completed", "Completed all requested recording times.", 0.0)
        except (OSError, ValueError, TypeError, KeyError, EOFError, BadZipFile):
            return None
        self._memory[key] = result.copy()
        return result

    def put(self, result):
        if result.status != "completed":
            return
        key = cache_key(result.config)
        self._memory[key] = result.copy(charged_work_units=0)
        if self._directory is None:
            return
        self._directory.mkdir(parents=True, exist_ok=True)
        metadata = {"schema": 1, "config": result.config.identity(),
                    "work": result.work_units, "evaluations": result.rhs_evaluations,
                    "steps": result.completed_steps}
        temporary = None
        try:
            with NamedTemporaryFile(dir=self._directory, suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                np.savez_compressed(stream, metadata=json.dumps(metadata, sort_keys=True),
                                    times=result.times, fields=result.fields)
            os.replace(temporary, self._directory / f"{key}.npz")
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()


class SimulationService:
    """One episode's purchase history plus an optionally shared backend cache."""

    def __init__(self, ledger, cache=None):
        self.ledger = ledger
        self._cache = cache if cache is not None else SimulationCache()
        self._purchased = {}

    def run(self, config):
        key = cache_key(config)
        start = perf_counter()
        if key in self._purchased:
            return self._purchased[key].copy(charged_work_units=0, wall_seconds=perf_counter() - start)
        cached = self._cache.get(config)
        if cached is not None and self.ledger.can_charge_work(cached.work_units):
            self.ledger.charge_work(cached.work_units)
            result = cached.copy(charged_work_units=cached.work_units, wall_seconds=perf_counter() - start)
        else:
            # An unaffordable warm result follows the cold bounded execution path.
            # Preserve partial fields/work/status, without a free full answer.
            result = solve_candidate(config, self.ledger)
            if result.status == "completed":
                self._cache.put(result)
        if result.status == "completed":
            self._purchased[key] = result.copy(charged_work_units=0)
        # Incomplete runs are not resumable or cached in v1. A retry pays again.
        return result
