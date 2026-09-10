# OCBA baseline pilot: protocol and interpretation

This is an implemented CPU-only numerical pilot, not an agent benchmark result.
It uses only the Python standard library. No Docker, API key, GPU, or third-party
package is required. Standalone proposals and the other two demos are unchanged.

## Two different tasks

1. **Original integration task.** Return the integrals of three deterministic
   response curves over [0,1]. Score mean absolute error (MAE), with equal weights
   and common units. Compare equal-spend scheduling and an adaptive refinement
   heuristic, using the same nested composite trapezoid estimator. Neither is OCBA.
2. **Monte Carlo selection variant.** A paid replication draws an independent
   U ~ Uniform[0,1] and returns f_i(U). Its expectation is the same integral, but
   the requested decision is now which curve has the **smallest** integral.
   Evaluate probability of correct selection (PCS) over repeated runs and mean
   selection regret. Also report MAE of all three sample means as a secondary,
   deliberately objective-mismatched diagnostic for OCBA.

Randomness in the second task comes from the random input, not additive sensor
noise or a broken simulator. No true error profile or variance is given to any
policy. A separate Gaussian-observation sanity control is explicitly labeled.

These tasks change both the query protocol and the objective. Their errors cannot
be compared as a controlled test of allocation policies. In particular, plain
Monte Carlo is not a competitive way to integrate smooth one-dimensional curves
when the policy can freely choose evaluation points. We have not prohibited
fitting, adaptive quadrature, or other lawful numerical methods for a future agent
track. The restricted sampling variant only checks an OCBA-compatible controller.

## Environment and costs

Private evaluator curves, disclosed here for reproducibility, are:

```text
f_1(x) = 1 + 0.2*x
f_2(x) = 0.2 + exp(-((x - 0.4)/0.2)^2)
f_3(x) = 0.2 + 4*exp(-((x - 0.62)/0.035)^2)
```

Their reference integrals are 1.1, 0.5536577478043857, and
0.44814353912664284. Closed-form erf references are checked against dense midpoint
integration independently. Curves and truth are not inputs to allocation rules.
This separation is logical within trusted Python code, not a sandbox that can hide
source files from an untrusted coding agent.

Costs are 2 credits to start each study once and [1,1,2] per new evaluation or MC
replication. These are synthetic prices, not actual execution time. All policies
must initialize all three studies, so the six startup credits are fixed overhead,
not an interesting planning choice in this pilot.

Integration starts with 4- and 8-interval grids. Cached point values are free;
doubling an n-interval grid costs n new evaluations. Stop when no complete
doubling fits the remaining budget. Equal-spend scheduling chooses the affordable
study with least cumulative point cost. Adaptive scheduling chooses the largest
observed |T_n-T_(n/2)|/3 divided by the next refinement cost. This proxy is not a
certified error bound; unseen peaks can fool it. Only whole-grid refinement is
implemented here, not a comprehensive adaptive quadrature library.

## Sampling policies

All four receive the same initial five observations per study, charged to the
budget. They then buy one affordable replication at a time until the budget is
exhausted. A separate warmup-ten sensitivity run can be invoked without changing
the main configuration.

- **Equal cost:** sample the study with the least cumulative replication spending.
- **Equal samples:** sample the study with the fewest replications.
- **Variance/MSE heuristic:** maximize s_i^2 / (n_i*(n_i+1)*c_i), the estimated
  one-step reduction of summed sample-mean variance per credit. This is a plug-in
  MSE heuristic, not an optimal MAE rule; adaptive stopping also complicates the
  unbiasedness argument.
- **Cost-aware OCBA:** target credit shares from the OCBAS rule, specialized to
  fixed per-replication costs, and choose the largest affordable replication-count
  deficit. Recompute after each observation, looking ahead by max(c_i)=2 credits.
  Target shares respect all spending already committed. This integer scheduling
  implementation is not a reproduction of a published experiment.

For the apparent best study b, gap d_i = mean_i - mean_b, estimated variance v_i,
and cost c_i, unnormalized OCBA **credit** weights are:

```text
r_i = v_i*c_i / d_i^2                             (i != b)
r_b = sqrt(v_b*c_b * sum(r_i^2/(v_i*c_i), i != b))
```

These are [Jia's Theorem 2, equations (3)-(4)](https://arxiv.org/pdf/1206.5865),
with constant simulation time. They reduce to ordinary equal-cost OCBA when costs
match. Unit tests check this and the exact two-alternative unequal-cost ratio.
Tiny variance and gap floors prevent numerical singularities; they are not
confidence bounds or a forced-exploration safeguard. Small-budget performance on
non-Gaussian samples has no guarantee from the asymptotic allocation rule.

[Chen et al. (2003)](https://doi.org/10.1016/S1569-190X(02)00095-3) provides the
product-design motivation for allocating simulation effort to correct selection,
rather than precise estimation of every alternative. The implemented formula is
from Jia, not a claimed replication of Chen et al.'s circuit experiments.

## Fixed experiment design

Main run: 1,000 seeds (0-999), budgets 120/240/480, four policies, eight scenarios.
This is 96,000 episodes. Scenario definitions and policy settings are specified
before the main run; all scenarios are retained in reporting.

- Original curves, unshifted.
- Six shifted-curve scenarios: assign means [0.50,0.55,0.90] to the three original
  shapes in every permutation, changing only vertical offsets. Shapes, variance,
  and costs remain fixed. This balances which shape is best or irrelevant, but
  is not a general randomized benchmark or evidence across scientific domains.
- Gaussian sanity control: means [0.50,0.55,0.90], standard deviation 0.15 for
  each study, costs [1,1,2]. This changes the observation distribution; do not pool
  it with the curve scenarios or treat it as a physical simulation.

Independent per-study random streams are keyed by scenario, seed, and study ID.
Policies within each scenario/seed receive identical prefixes for the same study;
different studies do not use common random numbers. Report Wilson 95% intervals
for PCS and paired normal-approximation 95% intervals for differences in PCS.
Intervals are pointwise, not simultaneous across all comparisons. They measure
sampling uncertainty within these fixed scenarios, not generalization to others.

## Reproduction and output

From repository root:

```powershell
python -m unittest discover -s demos/planning/tests -v
python demos/planning/src/ocba_pilot.py
python demos/planning/src/ocba_pilot.py --warmup 10 --output demos/planning/runs/ocba_warmup10
```

Use separate output directories to retain multiple runs; reusing a directory
overwrites that run's generated files. Outputs are ignored by Git:

- `summary.json`: protocol, script hash, runtime, references, integration traces,
  sampling summaries, and paired PCS differences.
- `episodes.jsonl`: every episode's counts, estimates, cost, decision, and score.
- `trace_examples.json`: each purchase for the first seed at the first budget,
  for every scenario and policy. All other traces can be reproduced by seed.
- `summary.csv`: compact machine-readable sampling summaries.

No LLM has been tested. A result favoring a classical policy would support its use
as a baseline or agent-accessible tool, not show a need for an LLM. Conversely, a
failure at a small budget would motivate diagnosis of initialization, distribution,
and objective assumptions before claiming a general limitation of OCBA.
