# Budgeted Science

CPU-only research demos for scientific agents making decisions under a finite
resource budget. Two finalized **predator–prey pilots** share numerical tools:
resource-rational parameter investigation and scientific claim verification.
These are small development studies, not a finished benchmark or general model ranking.

## Shared setup

The hidden system follows

```text
x' = theta1*x - theta2*x*y - 0.01*x*x
y' = 0.9*theta2*x*y - theta3*y
```

Initial populations are (10, 5), the horizon is [0, 8], and parameter ranges are
[0.6, 1.4], [0.04, 0.12], and [0.8, 2.0]. Each episode has **32 scientific credits**:

| Resource | Cost |
|---|---:|
| Low-fidelity trajectory (Euler, step 0.1) | 1 |
| High-fidelity trajectory (DOP853) | 8 |
| Scalar observation of the fixed target | 12 |

Agents receive noisy time-1 observations. Observation noise standard deviations
are 0.10 for prey and 0.05 for predators. Purchased evidence can be reused freely.
Scientific credits are controlled resource proxies, separate from API dollars.
The target uses the high-fidelity model: there is no structural model–target mismatch.
Agents use structured tools, not arbitrary Python; they do not receive the equations
or hidden parameters shown here for reproducibility.

- **Planning:** acquire evidence and submit three parameter estimates. Success
  requires every relative error to be at most 5%. Full-budget submission is required.
- **Verification:** audit three claims about an unknown target—report parameter
  accuracy, accumulated prey abundance, and late-time recovery. Return ACCEPT,
  REJECT, or ABSTAIN; a private numerical evaluator checks verdicts. Submission
  is allowed before spending the full budget.

## Recorded results

All three models used **high reasoning**. Planning has five systems; verification
has six development studies and 18 claims. Their scores are not comparable task accuracies.

| Method | Planning pass / 5 | Mean max. error | Median max. error | Verification correct / 18 | Wrong | Abstain |
|---|---:|---:|---:|---:|---:|---:|
| Adaptive multifidelity baseline | 3/5 | 18.09% | 3.69% | 15/18 | 3 | 0 |
| GPT-5.6 Sol | 3/5 | 5.33% | 3.03% | 14/18 | 4 | 0 |
| GPT-5.6 Terra | 2/5 | 19.43% | 20.92% | 16/18 | 2 | 0 |
| GPT-5.6 Luna | 0/5 | 25.76% | 17.66% | 10/18 | 6 | 2 |

Max. error means the largest relative error over three parameters, summarized
across systems. Verification has **9 true and 9 false claims**; either constant
verdict scores 9/18. Luna's verification row includes one explicitly authorized
retry: six submitted studies required seven attempts. Its original first-attempt
counts were 8 correct, 5 wrong, 2 abstentions, and 3 unsubmitted claims.

The numerical baseline uses a multifidelity GP, continuous parameter fitting,
and approximate uncertainty reduction per credit. Verification adds a structured
claim-output adapter, not a general report reader or an unpaid final simulation.
See the [setup, limitations, and provenance](docs/predator_prey_release.md).

## Run without API credentials

Python 3.10+ is supported; the recorded numerical stack was Python 3.13.5,
NumPy 2.3.4, and SciPy 1.16.1. From a clone, activate a virtual environment:

```bash
python -m pip install -e .
python -m budgeted_science.demo_release results
python -m budgeted_science.demo_release cpu
python -m unittest discover -s tests -p test_demo_release.py
```

The results command summarizes saved outcomes without running simulations.
The CPU command reruns five planning and six verification baseline episodes,
records new logs under ignored `tmp/`, and compares them with the saved results.
Neither command reads credentials, contacts a model, or requires Docker/GPU.
Small numerical differences across dependency versions may occur.

Live model evaluation is **optional and paid**, never part of installation or
these commands. See [reproduction and runner guidance](docs/predator_prey_release.md#optional-live-evaluation).

## Repository map

- `shared/budgeted_science/`: numerical environments, policies, scoring, and runners.
- `demos/planning/`, `demos/paired_claim_audit/`: task-specific interfaces/history.
- `examples/predator_prey/`: published development cases, including evaluator truth.
- `results/predator_prey/`: portable per-case results, prompts, schemas, and hashes.
- `tests/`: offline regression tests.
- [Development history](docs/development_history.md): earlier experiments, retained separately.

Published truth is for the evaluator, never an agent input. Credentials, raw API
archives, caches, and local run directories are not included. Historical runner
commands that reference ignored preparations require the original local archive;
use the portable commands above on a fresh clone.
