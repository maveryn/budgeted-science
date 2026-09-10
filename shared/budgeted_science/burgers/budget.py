"""Exact accounting in scientific credits, not dollars or measured FLOPs."""

from fractions import Fraction

from .config import finite_real, integer

# Derived from the public canonical calibration solve: nu=.2, N=64,
# safety=.4, record times .2,.4,.6,.8,1.0. A regression test enforces this.
WORK_PER_CREDIT = 16_512


def credits(value, name):
    finite_real(value, name)
    amount = Fraction(str(value))
    if amount < 0:
        raise ValueError(f"{name} must be nonnegative")
    return amount


class BudgetExceeded(RuntimeError):
    """A rejected next expenditure; earlier work is never refunded."""


class Ledger:
    def __init__(self, *, shared_credits=None, observation_credits=None, compute_credits=None):
        if shared_credits is not None and (observation_credits is not None or compute_credits is not None):
            raise ValueError("choose a shared pool or separate limits, not both")
        if (observation_credits is None) != (compute_credits is None):
            raise ValueError("provide both separate limits")
        self._shared = None if shared_credits is None else credits(shared_credits, "shared_credits")
        self._limits = {
            "observation": None if observation_credits is None else credits(observation_credits, "observation_credits"),
            "compute": None if compute_credits is None else credits(compute_credits, "compute_credits"),
        }
        self._spent = {"observation": Fraction(0), "compute": Fraction(0)}
        self._work = 0
        self._events = []

    @classmethod
    def shared(cls, total):
        return cls(shared_credits=total)

    @classmethod
    def separate(cls, observations, computation):
        return cls(observation_credits=observations, compute_credits=computation)

    @classmethod
    def unlimited(cls):
        """Offline diagnostics only; never an implicit benchmark budget."""
        return cls()

    def _remaining(self, kind):
        if self._shared is not None:
            return self._shared - sum(self._spent.values())
        limit = self._limits[kind]
        return None if limit is None else limit - self._spent[kind]

    def _can_charge(self, kind, amount):
        remaining = self._remaining(kind)
        return remaining is None or amount <= remaining

    def can_charge_work(self, work):
        return self._can_charge("compute", Fraction(integer(work, "work"), WORK_PER_CREDIT))

    def can_charge_observation(self, amount):
        return self._can_charge("observation", credits(amount, "observation charge"))

    def _charge(self, kind, amount, work=0):
        if not self._can_charge(kind, amount):
            raise BudgetExceeded(f"insufficient {kind} budget")
        self._spent[kind] += amount
        self._work += work
        self._events.append({"kind": kind, "credits": float(amount), "work_units": work})

    def charge_work(self, work):
        work = integer(work, "work")
        self._charge("compute", Fraction(work, WORK_PER_CREDIT), work)

    def charge_observation(self, amount):
        self._charge("observation", credits(amount, "observation charge"))

    @property
    def work_units(self):
        return self._work

    def status(self):
        def number(value):
            return None if value is None else float(value)
        return {
            "mode": "shared" if self._shared is not None else (
                "separate" if self._limits["compute"] is not None else "unlimited_diagnostic"),
            "shared_limit": number(self._shared),
            "limits": {k: number(v) for k, v in self._limits.items()},
            "spent": {k: float(v) for k, v in self._spent.items()},
            "total_spent": float(sum(self._spent.values())),
            "remaining": {k: number(self._remaining(k)) for k in self._spent},
            "work_units": self._work,
            "work_per_credit": WORK_PER_CREDIT,
        }

    def events(self):
        return tuple(dict(event) for event in self._events)
