# Budgeted Science

Lightweight testbeds for scientific agents making decisions under resource
constraints. The goal is to build clear, reproducible decision problems with
objective evaluation, beginning with small CPU-based demonstrations and later
adapting them to domain-specific scientific applications.

**Status:** repository scaffold only. No runnable demos, agent experiments, or
benchmark results are implemented yet.

## Three independent demos

| Demo | Scientific decision | Final evaluation |
| --- | --- | --- |
| [Project planning](demos/planning/README.md) | Allocate a shared budget across related scientific objectives; reuse evidence and adapt purchases. | Number of objectives meeting their stated tolerances. |
| [Imperfect-model inference](demos/imperfect_model_inference/README.md) | Use fixed approximate models and paid observations to infer a hidden target's parameters. | Held-out reference-response error from the submitted parameters. |
| [Surrogate development](demos/surrogate_development/README.md) | Acquire data and develop a predictor under acquisition, development-compute, and inference-cost limits. | Held-out predictive error and compliance with all three limits. |

## Repository layout

```text
demos/
  planning/                   # Gaussian transport-pulse study
  imperfect_model_inference/  # Fixed models of a diffusion-decay system
  surrogate_development/     # CPU surrogate construction for that family
shared/                      # Small reusable utilities, when needed
docs/                        # Protocol notes and proposal-appendix material
```

Each demo has its own `README.md`, `src/`, `configs/`, and `tests/`. Its eventual
entry point, dependencies, scientific environment, tools, baselines, and evaluator
belong to that demo. Running one must not require installing or running the other
two. No demo imports another demo; common helpers may live in `shared/`.

## Initial implementation principles

- CPU-only scientific computation and training; API-hosted agents may be added
  separately. Classical controls should run without API credentials.
- Structured actions executed by trusted numerical tools. No Docker, GPU, or
  arbitrary execution of agent-generated code is required for the first pilots.
- Explicit budgets, complete action/cost records, and private final evaluation.
  Keep hidden instance state and test answers out of agent-visible evidence.
- Separate scientific credits, actual execution costs, and agent API expenditure.
- Compare against competent numerical baselines; retain failed and abandoned work
  in reporting. Small pilots demonstrate the protocol, not broad agent rankings.

Start with planning, then inference, then construction. Add demo-local setup and
run commands as each becomes executable; there is no root-level runner yet.
Later coding-enabled evaluation will be a separate, isolated execution track.

Raw data, generated models, run outputs, and credentials stay out of Git by
default. Curated, reviewed summaries can go in `docs/` for a self-contained
proposal appendix; readers should not need to inspect code to understand results.
