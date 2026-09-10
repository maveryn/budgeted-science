# Budgeted scientific inference with imperfect models

**Status:** planned CPU demo; no executable implementation or trained models yet.

## Task and information contract

Use a two-mode diffusion-decay system with a fixed hidden diffusivity and decay
rate. Prepare a bank of three small polynomial ridge models offline, using
different sampling regimes; freeze and reuse the bank across matched episodes.
Provide common known-parameter calibration evidence.

- `predict(model, x, theta)`: approximate predictions at candidate parameters.
- `observe(x)`: paid observations of the fixed target; no candidate `theta` input.
- Numerical analysis tools: fit parameters and bounded discrepancy corrections
  using permitted evidence, charging underlying model calls and computation.
- Submission: one final parameter estimate, with optional uncertainty diagnostics.

There is no exact candidate-simulation API. Model errors and sensitivities must be
measured on development/reference cases, not inferred from sampling labels alone.

## Evaluation and controls

Score the submitted parameters by normalized response error on hidden settings
under a private reference model. Report parameter error separately where recovery
is identifiable. Enforce observation, model-call, and local-compute limits.

Start with fixed acquisition/model fitting and classical adaptive acquisition.
Later compare accurate, dominant, complementary, and shared-bias model banks;
separate acquisition quality from evidence use with matched numerical backends.
The public analytic law permits direct fitting, so the toy alone cannot establish
that using imperfect models is necessary.

## Local structure and first milestone

- `src/`: reference family, offline model preparation, tools, baselines, evaluator,
  and demo entry point.
- `configs/`: public parameter ranges, model recipes, calibration sizes, and budgets.
- `tests/`: reference checks, identifiability controls, accounting, and access rules.
- `data/`, `artifacts/`, `runs/`: generated evidence, model files, and records;
  ignored by Git and never automatically exposed to the agent.

Begin with one condition and three hidden targets. Add setup and run commands
when executable. This demo must not require running surrogate development to
prepare its fixed bank; it owns its preparation path and may reuse shared helpers.
