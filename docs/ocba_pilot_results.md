# OCBA pilot results

Run date: 2026-09-10. This is a classical-baseline experiment, not an LLM result.
The [protocol](ocba_pilot_protocol.md) records the objective distinction, equations,
cost model, scenario definitions, limitations, and reproduction commands.

## Verdict

Cost-aware OCBA is runnable and improves correct selection on the original
three-curve **Monte Carlo selection variant**, but it is not uniformly better.
Two near-tie variants expose a strong failure: early observations can miss a
narrow peak, underestimate variance, and leave a misleading estimate uncorrected.
The original success case alone would overstate its robustness.

For the original **estimate-all-integrals** task, adaptive quadrature scheduling
is the relevant baseline. OCBA solves a different objective. We should not change
the proposal's objective simply to make OCBA fit, nor conclude an LLM is needed
because this small-sample implementation fails in some variants.

## Execution and verification

- Main run: 96,000 episodes = eight scenarios x three budgets x four policies x
  1,000 seeds, with five initial samples per study.
- Sensitivity: another 32,000 episodes at budget 120, with ten initial samples.
  Same scenarios and seeds; no settings selected to maximize the main result.
- Actual CPU wall times: 92.53 s main, 17.40 s sensitivity on this machine.
  These are whole experiment timings, not per-policy speed comparisons.
- Python 3.12.14, standard library only. Zero API calls, no GPU rental.
- Twelve unit tests pass: analytic references versus independent integration,
  OCBA identities including unequal costs, sunk spending, caching/refinement
  charges, budget enforcement, random-stream pairing, and reproducibility.
- All sampling episodes spend exactly their disclosed budget. The fixed-grid
  integration policies can leave unused credits when a full refinement does not fit.
- Script SHA-256 for both recorded runs:
  `d0dea94ab60ad44c6fbe949cf344b1ede7ab87094133fb19fdb68b28b321d07c`.

## 1. Original deterministic integration task

Shared cap: 120 credits. Lower mean absolute error is better. The grid controller
chooses which study to double next based only on existing estimates, never truth.

| Policy | Final intervals for the three studies | Credits spent | MAE |
| --- | --- | ---: | ---: |
| Equal-spend refinement | 32, 32, 16 | 106 | 0.00657302 |
| Adaptive refinement | 8, 32, 32 | 114 | 0.0000103679 |

The adaptive controller stopped refining the linear curve earlier and bought
more resolution for the narrow peak. This is roughly a 634-fold error reduction
on **one hand-designed example under the same cap, not identical actual spending**.
It is not a general algorithm ranking, a certified-error result, or an OCBA result.
Local adaptive quadrature, other estimators, shifted peak locations, and stronger
static allocation controls have not yet been evaluated.

## 2. Monte Carlo selection variant: all results

Return the study with the smallest expected response. All methods see only paid
samples, and all estimates are sample means. Numbers below are percentages of
correct selections out of 1,000 independent runs per entry. Higher is better.

Labels S1-S6 identify this report's six fixed shifted-curve scenarios, not proposal
labels. The tuple gives the true means of the linear, broad-peak, and narrow-peak
curves respectively. These values are evaluator-only during each episode.

| Scenario | True means |
| --- | --- |
| Original | (1.1000, 0.55366, 0.44814) |
| S1 | (0.50, 0.55, 0.90) |
| S2 | (0.50, 0.90, 0.55) |
| S3 | (0.55, 0.50, 0.90) |
| S4 | (0.55, 0.90, 0.50) |
| S5 | (0.90, 0.50, 0.55) |
| S6 | (0.90, 0.55, 0.50) |
| Gaussian control | (0.50, 0.55, 0.90), each standard deviation 0.15 |

### Budget 120

| Scenario | Equal cost | Equal samples | Variance/MSE | Cost-aware OCBA |
| --- | ---: | ---: | ---: | ---: |
| Original | 73.7 | 73.8 | 85.8 | 86.0 |
| S1 | 80.1 | 76.6 | 81.0 | 84.9 |
| S2 | 58.4 | 59.5 | 34.9 | 38.0 |
| S3 | 80.0 | 76.0 | 83.3 | 87.0 |
| S4 | 65.0 | 65.6 | 80.5 | 81.5 |
| S5 | 54.5 | 59.2 | 30.9 | 30.3 |
| S6 | 64.9 | 64.5 | 78.6 | 78.7 |
| Gaussian control | 92.8 | 88.7 | 92.6 | 95.2 |

The equally weighted S1-S6 mean is 66.73% for OCBA and 67.15% for equal cost:
no aggregate advantage is demonstrated by the near-tie panel at this budget.
This average is conditional on this deliberately balanced six-case panel, not a
population estimate over scientific tasks.

Selected uncertainty estimates, with complete values in `summary.json`:

- Original: OCBA 86.0%, Wilson 95% CI [83.7%, 88.0%]; equal cost 73.7%,
  CI [70.9%, 76.3%]. Paired improvement: +12.3 percentage points,
  approximate 95% CI [+9.5, +15.1].
- Original versus variance/MSE: +0.2 points, paired CI [-0.2, +0.6]. Thus there
  is no clear evidence that OCBA outperforms that simpler adaptive comparator here.
- S2: OCBA minus equal cost -20.4 points, paired CI [-23.5, -17.3].
- S5: OCBA minus equal cost -24.2 points, paired CI [-27.4, -21.0].
- Gaussian control: OCBA minus equal cost +2.4 points, paired CI [+1.0, +3.8].

These intervals are pointwise, not adjusted for multiple comparisons.

### Budget 240

| Scenario | Equal cost | Equal samples | Variance/MSE | Cost-aware OCBA |
| --- | ---: | ---: | ---: | ---: |
| Original | 79.1 | 81.2 | 91.4 | 91.8 |
| S1 | 88.9 | 85.1 | 88.6 | 94.4 |
| S2 | 62.7 | 66.3 | 40.8 | 45.0 |
| S3 | 88.3 | 83.5 | 89.4 | 95.9 |
| S4 | 65.3 | 69.2 | 82.8 | 84.2 |
| S5 | 63.5 | 66.7 | 36.7 | 36.9 |
| S6 | 67.5 | 68.6 | 82.9 | 83.2 |
| Gaussian control | 98.1 | 96.7 | 97.6 | 99.3 |

### Budget 480

| Scenario | Equal cost | Equal samples | Variance/MSE | Cost-aware OCBA |
| --- | ---: | ---: | ---: | ---: |
| Original | 87.3 | 90.4 | 95.6 | 95.6 |
| S1 | 95.8 | 93.7 | 94.3 | 99.3 |
| S2 | 69.7 | 75.1 | 47.6 | 50.9 |
| S3 | 95.3 | 92.9 | 96.0 | 99.4 |
| S4 | 70.5 | 72.9 | 86.8 | 88.4 |
| S5 | 69.4 | 74.7 | 41.8 | 43.0 |
| S6 | 73.1 | 78.3 | 86.4 | 86.4 |
| Gaussian control | 99.8 | 99.4 | 99.6 | 100.0 |

More budget raises OCBA's success rates here, but does not remove its relative
weakness on S2/S5. The allocation rule is asymptotic and uses estimated variances;
these are small samples of strongly non-Gaussian curve responses.

## 3. What the trace shows

In S5, seed 0, budget 120, the narrow curve is actually slightly worse than the
broad curve (means 0.55 versus 0.50). After five samples per curve, its sample mean
is about 0.3023: the initial points largely missed the narrow peak.

OCBA ends with sample counts **[5,99,5]**, estimates
**[0.9194,0.5445,0.3023]**, and selects the narrow curve incorrectly. It never buys
another narrow-curve observation after initialization. This is an observed trace,
not merely a proposed explanation. An under-estimated empirical variance makes
the apparent best study look settled, sending the remaining samples elsewhere.

Conversely, in the original instance the narrow curve really is best. An
optimistic underestimate can therefore produce a correct final choice without
accurate evidence. PCS alone cannot distinguish those mechanisms. On the original
instance at 120 credits, all-means MAE is **0.08111 for OCBA** versus **0.06616 for
equal cost**, even though OCBA has higher PCS. This is not a fair reason to reject
a selection algorithm: it illustrates why the two objectives must stay distinct.

## 4. Sensitivity to initialization

Ten initial samples per study consume 46 of the same 120 credits, versus 26 with
five samples. All policies pay for this initialization. The static methods end
with the same final counts and samples, so their scores are unchanged.

| Scenario | OCBA, warmup 5 | OCBA, warmup 10 | Variance/MSE, warmup 10 | Equal cost |
| --- | ---: | ---: | ---: | ---: |
| Original | 86.0 | 81.0 | 81.0 | 73.7 |
| S1 | 84.9 | 83.8 | 78.2 | 80.1 |
| S2 | 38.0 | 49.9 | 46.2 | 58.4 |
| S3 | 87.0 | 86.3 | 80.1 | 80.0 |
| S4 | 81.5 | 72.9 | 71.8 | 65.0 |
| S5 | 30.3 | 45.0 | 45.2 | 54.5 |
| S6 | 78.7 | 72.8 | 72.6 | 64.9 |
| Gaussian control | 95.2 | 94.8 | 92.5 | 92.8 |

More initial coverage helps the two failure variants but does not fully fix them;
it reduces the favorable-case PCS in several other scenarios. This is consistent
with initialization sensitivity and asymmetric optimism. It is not a controlled
proof that variance estimation is the sole cause: warmup also changes means and
the budget available for adaptation. A safeguard or oracle-variance ablation has
not been run.

## Implication for the project

Keep this as a transparent baseline pilot. It establishes a runnable budget loop
and shows why objective choice and early-evidence quality matter. For the current
all-estimates planning formulation, continue with stronger adaptive numerical
baselines on varied curves. If a design-selection task is retained, use OCBA as
one baseline or an agent-accessible numerical tool, with better exploration and
small-budget controls. No result here establishes that agents will outperform
classical methods, or validates a broad scientific-planning benchmark.

Raw reproducible runs are in `demos/planning/runs/ocba_pilot/` and
`demos/planning/runs/ocba_warmup10/`, ignored by Git. The code, tests, protocol, and
this curated report are the shareable checkpoint; nothing was pushed or published.
