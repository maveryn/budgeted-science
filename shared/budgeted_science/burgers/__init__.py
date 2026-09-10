"""Restricted periodic viscous-Burgers foundation, not a validated benchmark."""

from .config import SolverConfig
from .budget import BudgetExceeded, Ledger
from .numerics import SimulationResult, solve_candidate

__all__ = ["SolverConfig", "BudgetExceeded", "Ledger", "SimulationResult", "solve_candidate"]
