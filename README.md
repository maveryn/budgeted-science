# Budgeted Science

Lightweight testbeds for scientific agents making decisions under resource
constraints. The goal is to build clear, reproducible decision problems with
objective evaluation, beginning with small CPU-based demonstrations and later
adapting them to domain-specific scientific applications.

**Harder planning toy (v2):** doubled parameter-range widths, noisy observations,
5% parameter tolerance, and a paid-data-only local least-squares baseline. The
new baseline passed 28/40 fresh cases, versus 0/40 for each GP control. The budget
remains 40 after a development sweep at 40/32/24. No v2 agent run was performed.
See the [v2 setup, results, and commands](docs/resource_planning_v2_results.md).

**Preserved planning toy (v1):** an independent predator-prey inverse problem compares
randomized nonadaptive acquisition with a cost-aware GP policy under 40 shared
credits. It uses live low/high-fidelity solvers and protected target measurements,
without LLM/API calls. See the [protocol](docs/resource_planning_toy_protocol.md)
and [paired CPU pilot results](docs/resource_planning_toy_results.md). An optional
[logged GPT adapter](docs/resource_planning_agent_run.md) now adds the shared
purchased-evidence fitter and a separate `run_resource_agent.py` entry point.
Explicit checkpoint/resume now preserves conversation, purchases, and cumulative
API charges. The first resumed predator-prey episode submitted successfully at
40/40 scientific credits; see the linked audit for limits and the single-instance result.
It does not replace the Burgers demo or its earlier agent runs.

**Status:** the CPU allocation pilot is preserved, and a shared viscous-Burgers
foundation now provides numerical tools, observations, budgets, fitting, and
separate planning/inference scoring contracts. Its numerical validation and
scripted contract checks are runnable. A single-episode planning runner now has
complete local audit logs, an offline fake-model mode, and an optional GPT-5.6 Sol
integration. Offline checks and its fixed-policy CPU comparison pass. Two live
attempts are retained: the first exposed a fixed replay-integration defect; the
post-fix attempt progressed for 11 responses and spent 19.17 scientific credits,
but reached its per-response output cap before submission. A subsequent
two-parameter episode completed: agent normalized RMSE 0.01834 at 19.80 credits,
versus 0.01812 at 17.88 credits for its fixed-policy comparison. This is one
development instance, not evidence of an adaptive-planning advantage. No trained
imperfect-model bank exists. See the [completed-run audit](docs/planning_two_parameter_agent_run.md).
See the [planning runner protocol](docs/planning_agent_runner.md).
See the [Burgers foundation results](docs/burgers_foundation_results.md),
[OCBA pilot results](docs/ocba_pilot_results.md), and
[pilot reproduction protocol](docs/ocba_pilot_protocol.md).

An [opt-in two-parameter CPU trial](docs/burgers_two_parameter_trial.md) now adds
unknown initial amplitude alongside viscosity. Reference/recoverability checks
and four budgeted fixed recipes run locally. The default agent task remains
one-parameter; `--two-parameter` now enables a logged amplitude/viscosity episode
with the same scientific budget and actual-profile scoring.

## Three independent demos

| Demo | Scientific decision | Final evaluation |
| --- | --- | --- |
| [Project planning](demos/planning/README.md) | Allocate a shared budget between target observations and computations. | Predator-prey toy: worst normalized parameter error and all-parameter success. Preserved Burgers: actual forecast-profile error. Allocation pilot: its own integral/selection scores. |
| [Imperfect-model inference](demos/imperfect_model_inference/README.md) | Use fixed approximate models and paid observations to infer a hidden target's parameters. | Held-out reference-response error from the submitted parameters. |
| [Surrogate development](demos/surrogate_development/README.md) | Acquire data and develop a predictor under acquisition, development-compute, and inference-cost limits. | Held-out predictive error and compliance with all three limits. |

## Repository layout

```text
demos/
  planning/                   # Preserved allocation pilot; logged Burgers agent runner
  imperfect_model_inference/  # Burgers fixed-predictor contract; model banks are future work
  surrogate_development/     # Planned CPU surrogate construction demo
shared/budgeted_science/     # Independent resource_planning/, burgers/, optional agents/
tests/                       # Numerical, tool-contract and offline runner tests
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

- CPU-only scientific computation and training; API-hosted agents use a separate
  optional integration. Classical controls run without API credentials.
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

## Logged planning episode

The dry-run uses a scripted fake model, does not read credentials, and makes no
network calls. After installing the numerical package:

```powershell
python demos/planning/src/run_agent.py --dry-run
```

Each run writes a frozen prompt/schema, full API-visible event log, complete
numerical records, readable transcript and paired comparison report under ignored
`demos/planning/runs/`. Inspect the [protocol](docs/planning_agent_runner.md) before
authorizing `--live`. Live mode requires `pip install -e '.[agents]'`, uses
`gpt-5.6-sol` with high reasoning, and enforces a separate $2 API spending bound.
Installation, tests and ordinary imports never start paid calls.
