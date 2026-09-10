# Budgeted Science

Lightweight testbeds for scientific agents making decisions under resource
constraints. The goal is to build clear, reproducible decision problems with
objective evaluation, beginning with small CPU-based demonstrations and later
adapting them to domain-specific scientific applications.

**Status:** the CPU allocation pilot is preserved, and a shared viscous-Burgers
foundation now provides numerical tools, observations, budgets, fitting, and
separate planning/inference scoring contracts. Its numerical validation and
scripted contract checks are runnable. No agent experiments or trained
imperfect-model banks have been run or built.
See the [Burgers foundation results](docs/burgers_foundation_results.md),
[OCBA pilot results](docs/ocba_pilot_results.md), and
[pilot reproduction protocol](docs/ocba_pilot_protocol.md).

## Three independent demos

| Demo | Scientific decision | Final evaluation |
| --- | --- | --- |
| [Project planning](demos/planning/README.md) | Allocate a shared budget between target observations, parameter fitting, and forecast computation. | Burgers foundation: error of the actual submitted forecast profile. The preserved allocation pilot has its own integral/selection scores. |
| [Imperfect-model inference](demos/imperfect_model_inference/README.md) | Use fixed approximate models and paid observations to infer a hidden target's parameters. | Held-out reference-response error from the submitted parameters. |
| [Surrogate development](demos/surrogate_development/README.md) | Acquire data and develop a predictor under acquisition, development-compute, and inference-cost limits. | Held-out predictive error and compliance with all three limits. |

## Repository layout

```text
demos/
  planning/                   # Preserved allocation pilot; Burgers planning contract
  imperfect_model_inference/  # Burgers fixed-predictor contract; model banks are future work
  surrogate_development/     # Planned CPU surrogate construction demo
shared/budgeted_science/     # Installable shared package, including burgers/
tests/                       # Shared numerical and tool-contract tests
docs/                        # Protocol notes and proposal-appendix material
tmp/burgers_foundation/      # Ignored validation outputs and backend cache
```

Each demo has its own `README.md`, `src/`, `configs/`, and `tests/`. No demo imports
another demo. The two Burgers facades currently live in the shared package and
are tested independently; neither requires the other demo or surrogate training.

## Install and validate the shared foundation

Python 3.10+ and NumPy/SciPy are required. From the repository root, on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m unittest discover -s demos/planning/tests -v
.\.venv\Scripts\python.exe -m budgeted_science.burgers.validate
```

On POSIX use `.venv/bin/python` instead. After activating the environment,
`python -m budgeted_science.burgers.validate` is the same entry point. No Docker,
GPU, API key, or paid model call is needed. The older allocation pilot still runs
without NumPy/SciPy; see its own README.

Validation writes error/work tables, recoverability diagnostics, two scripted
interaction traces, configuration, software versions, and source hashes under
`tmp/burgers_foundation/`. Those files include private evaluator information and
are not agent inputs. See [shared interfaces and accounting](shared/README.md)
for the scientific contract and limitations.

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

Next experiments can build on these contracts: budget/price sweeps, numerical
policies, and fixed imperfect-model banks. The current validation runner is not
an agent benchmark. Later coding-enabled evaluation needs separate isolation and
must account for lawful shortcuts: this restricted Burgers family also has fast
Cole-Hopf solutions, so it does not make expensive simulation unavoidable.

Raw data, generated models, run outputs, and credentials stay out of Git by
default. Curated, reviewed summaries can go in `docs/` for a self-contained
proposal appendix; readers should not need to inspect code to understand results.
