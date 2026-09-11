"""Frozen first-episode settings. Private instance data never enters a prompt."""

from dataclasses import asdict, dataclass
from decimal import Decimal

from budgeted_science.burgers.config import finite_real, integer, viscosity, initial_amplitude_value


@dataclass(frozen=True)
class RunConfig:
    model: str = "gpt-5.6-sol"
    reasoning_effort: str = "high"
    scientific_credits: float = 20.0
    record_price: float = 2.0
    noise_std: float = 0.01
    api_ceiling_usd: str = "2.00"
    max_responses: int = 30
    max_output_tokens: int = 8192
    deadline_seconds: float = 1200.0
    task_variant: str = "viscosity"

    def __post_init__(self):
        if self.task_variant not in ("viscosity", "viscosity_amplitude"):
            raise ValueError("unknown planning task variant")
        if self.model != "gpt-5.6-sol" or self.reasoning_effort != "high":
            raise ValueError("this evaluation is fixed to gpt-5.6-sol with high reasoning")
        for name in ("scientific_credits", "record_price", "noise_std", "deadline_seconds"):
            value = finite_real(getattr(self, name), name)
            if value < 0 or (name in ("record_price", "deadline_seconds") and value == 0):
                raise ValueError(f"invalid {name}")
        if not 1 <= integer(self.max_responses, "max_responses", 1) <= 30:
            raise ValueError("max_responses must be in [1, 30]")
        if not 1 <= integer(self.max_output_tokens, "max_output_tokens", 1) <= 32768:
            raise ValueError("max_output_tokens must be in [1, 32768]")
        amount = Decimal(self.api_ceiling_usd)
        if not amount.is_finite() or not 0 <= amount <= 2:
            raise ValueError("API ceiling must be between zero and the approved $2")
        if self.deadline_seconds > 1200:
            raise ValueError("deadline cannot exceed 20 minutes")

    def public(self):
        return asdict(self)


@dataclass(frozen=True)
class PrivateInstance:
    target_viscosity: float = 0.23
    seed: int = 0
    target_amplitude: float = 1.0

    def __post_init__(self):
        viscosity(self.target_viscosity)
        integer(self.seed, "seed")
        initial_amplitude_value(self.target_amplitude)

    def private(self):
        return asdict(self)
