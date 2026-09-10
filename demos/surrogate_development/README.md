# Resource-constrained scientific surrogate development

**Status:** planned CPU demo; no training loop or benchmark results yet.

## Task

Build a new predictor for a two-mode diffusion-decay system. Here diffusivity
and decay rate are known prediction inputs, not hidden parameters to infer.
Predict a fixed position-time response grid at new parameter settings.

Provide a small initial training set, purchasable parameter runs, bounded
validation feedback, and polynomial ridge learners with configurable capacity
and regularization. The agent can acquire a run, train a candidate, validate it,
and submit a frozen fitted model. It does not select from the inference demo's
pretrained bank.

## Evaluation and resources

Measure held-out predictive error subject to three separate constraints:

1. Acquisition allowance, charged per parameter run.
2. Development-compute allowance, including all fits, diagnostics, validation,
   feature construction, and failed or abandoned work.
3. Complete-prediction inference-cost cap, including feature generation.

Audit the compute convention for supported learners. Label provisional work
credits as proxies rather than measured FLOPs. Split whole parameter runs before
preprocessing; keep sealed-test feedback unavailable during development.

Compare fixed/adaptive acquisition crossed with fixed/adaptive model development.
The analytic toy demonstrates this loop; its reconstructable labels do not prove
acquisition scarcity in an unrestricted coding setting. A small cylinder
sim-to-real application remains a later extension, not a prerequisite.

## Local structure and first milestone

- `src/`: acquisition pool, learners, development tools, baselines, evaluator,
  and demo entry point.
- `configs/`: public data recipes, learner options, validation policy, and budgets.
- `tests/`: whole-run splits, cost counting, artifact submission, and leakage checks.
- `data/`, `artifacts/`, `runs/`: generated datasets, fitted models, and records;
  ignored by Git.

Build a baseline-only acquire/fit/submit loop, then evaluate one or two agents on
a small set of instances. Add setup and run commands when implemented. Own the
data-generation path here; this demo must not depend on running the inference demo.
