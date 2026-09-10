# Resource-rational scientific project planning

**Status:** CPU-only classical baseline pilot implemented. No LLM runs yet.

## Current pilot

The initial executable toy is deliberately simpler than the transport-pulse idea
below: estimate three curve integrals under a shared computation budget. It has
equal-spend and adaptive-refinement baselines. A separate Monte Carlo
best-alternative-selection variant compares cost-aware OCBA, equal spending,
equal sample counts, and a variance-based allocator. These are different tasks;
OCBA is not presented as a quadrature algorithm.

From the repository root, using Python 3.10 or later and no extra packages:

```powershell
python -m unittest discover -s demos/planning/tests -v
python demos/planning/src/ocba_pilot.py
```

See the [protocol](../../docs/ocba_pilot_protocol.md) for assumptions, costs,
references and sensitivity commands, and the
[results](../../docs/ocba_pilot_results.md) for the measured outcome.
Generated episode records live under `runs/` and are ignored by Git.

## Earlier transport-pulse sketch (not implemented)

Use an analytic Gaussian transport pulse with hidden transport speed,
diffusivity, and mass. At a specified downstream location, estimate peak timing,
peak concentration, and cumulative exposure within disclosed time windows and
tolerances. Measurements can inform several objectives at once.

The agent chooses point readings, time series, spatial profiles, and numerical
analysis under one scientific budget. A later matched variant adds uncertain
sensor gain and a purchasable calibration measurement. Supply competent fitting,
peak search, integration, and uncertainty tools.

### Evaluation and controls for that sketch

- Submit one final answer or abstention per objective. Each answer within its
  tolerance earns one point; budget violations are invalid.
- Compare question-by-question allocation, a fixed shared purchase plan, and an
  adaptive shared plan using the same numerical estimator.
- Preserve lawful analytic/global-fit solutions. Shared calibration alone does
  not prove a need for adaptive planning; include an always-calibrate-first control.
- Keep hidden truth and endpoint scores private until the episode ends.

## Local structure and later work

- `src/`: environment, tools, baseline policies, evaluator, and demo entry point.
- `configs/`: public task settings, observation menus, budgets, and tolerances.
- `tests/`: analytic checks, resource enforcement, scoring, and leakage tests.
- `runs/`: generated local records and summaries; ignored by Git.

The baseline-only allocation pilot is complete. A structured-action agent
interface, randomized scientific instances, and a broader numerical-baseline suite
remain future work. This demo works without the inference or surrogate-development
demos. The pilot is not a finalized benchmark specification.
