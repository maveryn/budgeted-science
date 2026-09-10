# Budgeted scientific inference with imperfect models

**Status:** the shared CPU Burgers foundation has an executable fixed-predictor
tool contract and a scripted fit/submission check. Trained model banks,
complementary error profiles, discrepancy correction, and agent runs are not
implemented.

## Current shared Burgers contract

The fixed hidden target has viscosity in `[0.1, 0.3]`. An acquisition buys one
sensor's five-time calibration record; it cannot change the target viscosity or
reveal the forecast experiment. Registered predictors accept candidate viscosity
values. Inference exposes `predict(model_id, viscosity, protocol)` but no
adjustable-resolution or reference-simulation action. Its fitting helper invokes
the chosen fixed predictor and retains the best completed fit on interruption.

The only predictor adapter in this milestone is `FixedNumericalPredictor`: a
resolution-locked numerical fixture for contract testing. It is **not** a trained
surrogate or evidence of complementary model errors. Its internal implementation
uses shared numerical machinery, but caller actions cannot change its resolution.

The agent submits viscosity. Private scoring generates that parameter's reference
forecast and compares it with the target's noise-free forecast at 16 positions,
using RMSE divided by the public amplitude scale 1.5. Absolute viscosity error is
reported separately. Unlike planning, inference does not submit a computed field.
See the [shared APIs and accounting](../../shared/README.md).

After `python -m pip install -e .` from the root in a virtual environment:

```powershell
python -m unittest discover -s tests -p test_burgers.py -v
python -m budgeted_science.burgers.validate
```

The validator's inference smoke uses one fixed 32-point numerical fixture,
an eight-credit acquisition cap, and a 30-credit computation cap. These are
illustrative interface-test settings, not a chosen benchmark budget. Its trace
and private diagnostic outputs live under ignored `tmp/burgers_foundation/`.
See the [measured foundation results](../../docs/burgers_foundation_results.md).

Next steps are a bank preparation/registration path, known-parameter calibration
assets, measured error profiles, and matched acquisition/fitting policies. Model
errors cannot be inferred from training-region labels alone. Later coding-enabled
evaluation must accommodate analytic shortcuts and provide real isolation; the
current trusted in-process facade is not a security sandbox.

## Earlier diffusion-decay sketch (not implemented)

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

This earlier sketch is retained as design history, not the current implemented
physical environment. The Burgers facade and its tests do not require another
demo. Future fixed-bank preparation likewise must not require running surrogate
development; it can reuse shared helpers while owning its preparation path.
