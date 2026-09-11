"""Public task settings, deliberately excluding the model and solver details."""

from dataclasses import dataclass, field
from math import isfinite
from numbers import Real
from types import MappingProxyType
from typing import Mapping


THETA_BOUNDS = ((0.8, 1.2), (0.06, 0.10), (1.1, 1.7))
DEBUG_THETA = (1.0, 0.08, 1.4)
WORKING_TIMES = tuple(index / 2 for index in range(1, 17))


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite real number") from exc
    if not isfinite(result):
        raise ValueError(f"{name} must be a finite real number")
    return result


def _sequence(value, name):
    if isinstance(value, (str, bytes, Mapping)):
        raise ValueError(f"{name} must be a numeric sequence")
    try:
        return tuple(value)
    except TypeError as exc:
        raise ValueError(f"{name} must be a numeric sequence") from exc


@dataclass(frozen=True)
class Config:
    """Immutable episode settings; ``public()`` returns fresh JSON data.

    Public keys: ``bounds`` (three parameter intervals), ``initial`` ([x0, y0]),
    ``working_times`` (baseline evidence grid), ``costs`` (low/high/measurement),
    ``budget`` (shared credits), and ``tolerance`` (relative parameter tolerance).
    Overrides support controlled tests; the default is the approved milestone.
    """

    ranges: tuple = THETA_BOUNDS
    initial: tuple = (10.0, 5.0)
    working_times: tuple = WORKING_TIMES
    costs: Mapping = field(default_factory=lambda: {"low": 1, "high": 8, "measurement": 12})
    budget: float = 40
    tolerance: float = 0.1

    def __post_init__(self):
        ranges = []
        for interval in _sequence(self.ranges, "ranges"):
            pair = _sequence(interval, "range")
            if len(pair) != 2:
                raise ValueError("each range must have two endpoints")
            low, high = (_number(value, "range endpoint") for value in pair)
            if not 0 < low < high:
                raise ValueError("ranges must be positive and increasing")
            ranges.append((low, high))
        if len(ranges) != 3:
            raise ValueError("ranges must contain three intervals")
        initial = tuple(_number(value, "initial") for value in _sequence(self.initial, "initial"))
        if len(initial) != 2 or min(initial) <= 0:
            raise ValueError("initial must contain two positive values")
        times = tuple(_number(value, "working time")
                      for value in _sequence(self.working_times, "working_times"))
        if (not times or any(not 0 <= time <= 8 for time in times)
                or any(left >= right for left, right in zip(times, times[1:]))):
            raise ValueError("working_times must increase strictly within [0, 8]")
        if not isinstance(self.costs, Mapping) or set(self.costs) != {"low", "high", "measurement"}:
            raise ValueError("costs must contain exactly low, high, and measurement")
        costs = {key: _number(self.costs[key], f"{key} cost") for key in ("low", "high", "measurement")}
        if min(costs.values()) <= 0:
            raise ValueError("costs must be positive")
        budget = _number(self.budget, "budget")
        tolerance = _number(self.tolerance, "tolerance")
        if budget < 0 or not 0 < tolerance <= 1:
            raise ValueError("budget must be nonnegative and tolerance in (0, 1]")
        object.__setattr__(self, "ranges", tuple(ranges))
        object.__setattr__(self, "initial", initial)
        object.__setattr__(self, "working_times", times)
        object.__setattr__(self, "costs", MappingProxyType(costs))
        object.__setattr__(self, "budget", budget)
        object.__setattr__(self, "tolerance", tolerance)

    @property
    def bounds(self):
        return self.ranges

    def public(self):
        return {"bounds": [list(pair) for pair in self.ranges],
                "initial": list(self.initial), "working_times": list(self.working_times),
                "costs": dict(self.costs), "budget": self.budget, "tolerance": self.tolerance}

    def _cache_key(self):
        return (self.ranges, self.initial, self.working_times,
                tuple(self.costs.items()), self.budget, self.tolerance)

    @classmethod
    def from_public(cls, public):
        """Rebuild configuration from JSON, including across spawned workers."""
        expected = {"bounds", "initial", "working_times", "costs", "budget", "tolerance"}
        if not isinstance(public, Mapping) or set(public) != expected:
            raise ValueError("public config must contain exactly the documented fields")
        return cls(ranges=public["bounds"], initial=public["initial"],
                   working_times=public["working_times"], costs=public["costs"],
                   budget=public["budget"], tolerance=public["tolerance"])
