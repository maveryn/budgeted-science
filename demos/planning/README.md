# Resource-rational scientific project planning

**Status:** planned CPU demo; no executable implementation yet.

## Task

Use an analytic Gaussian transport pulse with hidden transport speed,
diffusivity, and mass. At a specified downstream location, estimate peak timing,
peak concentration, and cumulative exposure within disclosed time windows and
tolerances. Measurements can inform several objectives at once.

The agent chooses point readings, time series, spatial profiles, and numerical
analysis under one scientific budget. A later matched variant adds uncertain
sensor gain and a purchasable calibration measurement. Supply competent fitting,
peak search, integration, and uncertainty tools.

## Evaluation and controls

- Submit one final answer or abstention per objective. Each answer within its
  tolerance earns one point; budget violations are invalid.
- Compare question-by-question allocation, a fixed shared purchase plan, and an
  adaptive shared plan using the same numerical estimator.
- Preserve lawful analytic/global-fit solutions. Shared calibration alone does
  not prove a need for adaptive planning; include an always-calibrate-first control.
- Keep hidden truth and endpoint scores private until the episode ends.

## Local structure and first milestone

- `src/`: environment, tools, baseline policies, evaluator, and demo entry point.
- `configs/`: public task settings, observation menus, budgets, and tolerances.
- `tests/`: analytic checks, resource enforcement, scoring, and leakage tests.
- `runs/`: generated local records and summaries; ignored by Git.

Implement a baseline-only loop first, then a structured-action agent interface.
An initial smoke test may use three hidden worlds and one or two agents. Add
installation and run commands here once implemented. This demo must work without
the inference or surrogate-development demos.
