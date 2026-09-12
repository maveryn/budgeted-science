# Numerical fitting and forecast verification: CPU pilot

**Outcome:** implemented and tested, but still not a compelling adaptive-audit
challenge. Fixed-split, full-recompute and adaptive-residual controls each get
10/10 verdicts at the smallest tested budget of four credits. No paid model run
was made. Keep this as a mechanics demonstration; do not launch another Luna
batch or keep tightening this catalog just to obtain failures.

## Question and scope

Can an auditor check a completed study's numerical claim when parameter fitting
and forecasting both require computation? Improving a forecast at the study's
incorrect fitted parameters does not fix the fitting error.

This independent prototype replaces the earlier toy's trivial unit-conversion
stage with an actual numerical inverse problem. It does not replace previous
environments, agent interfaces or saved results. It has no model adapter, API
calls, credential access, physical validation, new target measurements or LLM
judge. All controls are ordinary deterministic CPU procedures with structured
inputs, not baselines for interpreting unrestricted scientific reports.

## Scientific contract

The existing predator-prey dynamics are reused without modifying planning:

```
x' = theta1*x - theta2*x*y - 0.01*x*x
y' = 0.9*theta2*x*y - theta3*y
```

- Parameter bounds: `[0.6,1.4]`, `[0.04,0.12]`, `[0.8,2.0]`.
- Calibration initial state: `(10,5)`. Eight observation times, `0.5,1,...,4`,
  with both populations observed without noise: sixteen supplied scalar data.
- Forecast initial state: `(20,2)`, horizon 24. The claimed quantity is `x(24)`.
- Reference contract: a converged bounded least-squares fit to those fixed data,
  followed by a converged forecast. No additional physical-system evidence.
- Original claim: its printed ten-significant-digit value is within **3%** of
  this reference. The submitted verdict concerns that original value, not the
  auditor's repaired value or the original study's level of confidence.

Public information includes the equations, parameter bounds, complete supplied
data, initial conditions, original fitted parameters, residual, numerical
configuration, calibration output, forecast trajectory and claim. Private
information includes generating parameters, reference calculations and labels.
The in-process facade is a trusted interface, **not a security sandbox**.

### Independent numerical reference

Data and reference trajectories are compared using DOP853 and Radau at
`rtol=1e-11, atol=1e-13`. Three bounded Radau-based least-squares runs start from
normalized parameters `(0.5,0.5,0.5)`, `(0.25,0.75,0.25)`, `(0.75,0.25,0.75)`.
The reference forecast uses the recovered fit, not a direct substitution of
the generating parameters into an auditor's answer. A generating-parameter
forecast is an independent cross-check.

Maximum trajectory disagreement must be below `1e-6`; each fit must recover
all generating parameters to relative error below `1e-6`. The fitted reference
forecast must also agree with the generating-system forecast within `1e-6`
relative error. These are empirical recoverability and reference checks, not
a proof of global identifiability or a mathematically certified error bound.

Measured reference checks:

| System | Reference `x(24)` | Calibration max abs disagreement | Forecast max abs disagreement | Largest recovered parameter error, relative |
|---|---:|---:|---:|---:|
| `(0.9,0.065,1.2)` | 21.4380657476 | 7.55e-10 | 5.12e-10 | 3.33e-11 |
| `(1.2,0.10,1.6)` | 15.9839364203 | 1.95e-9 | 8.86e-10 | 1.98e-11 |

Smallest scaled residual-Jacobian singular values at the converged fits were
approximately 1.266 and 2.757. This checks local sensitivity, not global uniqueness.

## Ten development studies, not a large evaluation dataset

Two deliberately chosen development systems have parameters `(0.9,0.065,1.2)`
and `(1.2,0.10,1.6)`. Each supplies five variants:

1. Converged fit and accurate forecast.
2. Incomplete fit with accurate forecast at that fit.
3. Converged fit with inaccurate forecast integration.
4. Both consequential fitting and forecast-integration errors.
5. An approximate fit/forecast combination whose final claim remains valid.

Original fitted parameters are actual prefixes of a bounded damped
Gauss-Newton calculation, starting at normalized `(0.25,0.75,0.25)`, or the
independently recovered converged fit. Forecasts are actually executed with
tight DOP853 or RK2 steps `0.1,0.2,0.4,0.8`. Reports are derived from the result;
their final values are not perturbed by hand.

There are 90 candidate pipelines in the retained commissioning sweep. Invalid
variants require at least 3.6% error and are selected nearest 8%; harmless
combinations require 0.1–2.4% error and are selected nearest 1.5%. Sound-study
error must be below 0.1%. Both-error variants additionally require consequential
fit-only error and at least 1% effect from forecast numerics. Failed numerical
pipelines remain in the commissioning record and are excluded from admission.
Unfilled categories cause an explicit error rather than hidden substitution.

All ten variants were admitted. Their order is shuffled once with seed
20260913. Selection uses numerical consequence, never policy performance.
There are four valid and six invalid claims, so an always-REJECT rule gets 6/10.

| Variant | System 1 original claim error | System 2 original claim error |
|---|---:|---:|
| Sound | <0.000001% | <0.000001% |
| Fit error | 6.314% | 10.490% |
| Prediction error | 13.320% | 10.145% |
| Both errors | 9.122% | 9.181% |
| Harmless combination | 1.450% | 1.827% |

## Work, interfaces and accounting

One credit equals **256 actual two-component RHS evaluations**. All underlying
calibration solves used by fitting, finite differences and line searches count.
The comparison uses caps of 4, 8 and 16 credits (1,024, 2,048 and 4,096 RHS
evaluations), not arbitrary per-stage flat fees. This is a work proxy, not
FLOPs, measured runtime, dollars or the cost of an experiment.

The numerical menu contains:

| Method | Settings |
|---|---|
| `dop_loose` | DOP853, `rtol=1e-4`, `atol=1e-7` |
| `dop_tight` | DOP853, `rtol=1e-9`, `atol=1e-11` |
| `rk2_0.1` through `rk2_0.8` | Explicit two-stage RK2, fixed timestep |

`describe`, `record`, `budget` and `submit` are free. `fit_step` performs one
bounded damped Gauss-Newton update; `fit_full` performs bounded least squares.
Both use an injected, metered predictor and retain their best completed
evaluated candidate if interrupted. `predict` forecasts at a registered fit
without changing it. `register_fit` allows a freely derived parameter estimate;
it does not secretly simulate or certify that estimate.

Original and purchased deterministic records are reusable for free. Every
episode has its own purchases and ledger. Failed solves retain performed work;
caps are enforced before each RHS call. An unexpected unaccounted exception
retains its work reservation and aborts the episode. Invalid requests are
uncharged. Same-ID tool calls are deduplicated. Interrupted trajectories do not
masquerade as completed forecasts. Partial requests with identical caps can be
reused; a larger request recomputes and charges its actual work rather than
claiming unsupported solver continuation.

Local optimizer algebra, interpolation of existing records and data analysis
are scientifically uncharged. Runtime is recorded. This intentionally admits
the possibility of a legitimate analytic shortcut; it does not ban one to
manufacture a budget challenge. Arbitrary-code accounting is not implemented.

## Frozen CPU controls

All start from the same original study, with no privileged reference access.
Each compares the original claim with its completed check value and submits
ACCEPT if the relative difference is at most 3%, otherwise REJECT. If its chosen
forecast cannot complete, it abstains rather than inventing a repaired answer.

| Control | Fixed algorithm |
|---|---|
| Prediction only | Tight forecast at the original fit, no refitting; identical original tight output is free reuse. |
| Fit focused | Tight-predictor bounded least squares, reserving one credit for an RK2 `dt=0.2` forecast. |
| Fixed split | Half the total work cap for loose-predictor bounded least squares; remainder for a loose adaptive forecast. |
| Adaptive residual | Loose-predictor Gauss-Newton steps, checking residual after each step and reserving two credits for a forecast; optional tight forecast check when the claim/check difference is 1.5–6%. |
| Full recompute | Efficient loose-predictor bounded least squares with a two-credit forecast reserve, then a loose adaptive forecast. |
| Integral match | Estimate parameters directly from supplied data using trapezoidal integral identities and bounded linear least squares, then purchase a loose adaptive forecast. |

The residual policy stops refitting when normalized residual RMSE is at most
0.01, work falls to its reserve, an update is incomplete, or improvement is
less than 0.1%, with at most eight updates. These are heuristics, not a
calibrated forecast-error bound. Bounded least squares uses normalized
parameters, `diff_step=1e-3`, at most 30 residual evaluations as counted by
SciPy's optimizer, and `1e-9` optimizer tolerances; additional finite-difference
forward calls are still charged. All predictor calls are recorded.

The integral control uses the equations' linear parameter identities:

```
log(x/x0) + 0.01*integral(x dt) = theta1*t - theta2*integral(y dt)
log(y/y0)                     = 0.9*theta2*integral(x dt) - theta3*t
```

It estimates the integrals from supplied samples; it does not query hidden
trajectories. Its quadrature approximation can be inaccurate. This is a
deliberately included alternative to repeated numerical forward solves.

Controls vary optimizer, integrator and allocation together. Differences are
practical method comparisons, not causal proof that allocation alone explains
an outcome. The fixed reserve and residual thresholds are not claimed optimal.

## Results and reproducibility

Completed run:
[full comparison](../demos/claim_verification/runs/20260912T081931Z-fit-prediction-cpu-b5be5467dd/report.md),
[frozen manifest](../demos/claim_verification/runs/20260912T081931Z-fit-prediction-cpu-b5be5467dd/manifest.json),
[catalog and references](../demos/claim_verification/runs/20260912T081931Z-fit-prediction-cpu-b5be5467dd/catalog.json).
These local artifacts are intentionally ignored, not distributed in Git.

Correct binary verdicts, denominator ten studies in every cell:

| Control | 4 credits | 8 credits | 16 credits |
|---|---:|---:|---:|
| Prediction only | 2/10 | 7/10 | 7/10 |
| Fit focused | 7/10 | 9/10 | 10/10 |
| Fixed split | **10/10** | **10/10** | **10/10** |
| Adaptive residual | **10/10** | **10/10** | **10/10** |
| Full recompute | **10/10** | **10/10** | **10/10** |
| Integral match | 7/10 | 7/10 | 7/10 |

The 180 policy episodes are six controls times ten studies times three budgets,
**not 180 independent scientific cases**. All completed without harness failure;
six prediction-only episodes abstained at four credits. Those abstentions count
as nonsuccesses. Its other errors were two false accepts at four credits and
three at each larger budget. Fit-focused made three, one and zero false accepts
at 4/8/16 credits respectively. Integral matching made one false accept and two
false rejects at every budget. The three perfect-verdict controls made neither.

Mean credits actually spent:

| Control | 4-credit cap | 8-credit cap | 16-credit cap |
|---|---:|---:|---:|
| Prediction only | 2.400 | 3.115 | 3.115 |
| Fit focused | 3.938 | 7.861 | 13.011 |
| Fixed split | 3.517 | 5.419 | 7.664 |
| Adaptive residual | 2.563 | 3.956 | 3.961 |
| Full recompute | 3.517 | 6.873 | 8.702 |
| Integral match | 1.543 | 1.543 | 1.543 |

At four credits, fixed-split and full-recompute allocate the same fitting
allowance and therefore are identical controls, not independent corroboration.
Their allowances differ at larger caps. Adaptive residual spends less, but
resource saving is not part of the chosen score, and this is not evidence of
an accuracy advantage. Mean episode runtimes, including local logging, range
from 0.034 to 0.361 seconds across method/budget groups on this machine; they
are not portable performance measurements. API expenditure is exactly **$0**.

### What the traces reveal

For system 1's mixed-error claim, adaptive residual uses 370 RHS evaluations
for fitting and 329 for its forecast (2.730 credits total). It correctly rejects
the original 9.122%-error claim; its check forecast differs from the reference
by 0.610%. The fixed-split control also correctly rejects, but its check itself
has 3.243% error. See the
[adaptive trace](../demos/claim_verification/runs/20260912T081931Z-fit-prediction-cpu-b5be5467dd/episodes/20260912T082014Z-adaptive_residual-8a4223a057/transcript.md)
and [fixed trace](../demos/claim_verification/runs/20260912T081931Z-fit-prediction-cpu-b5be5467dd/episodes/20260912T082014Z-fixed_split-114ab66766/transcript.md).

More importantly, on system 2's fit-error claim at four credits, fixed-split
correctly rejects although its own check forecast has **22.085% error**; the
adaptive check has **17.461% error** and also rejects. The verdict is correct,
but neither check is a reliable replacement answer. The study label is still
objectively defined; binary verdict scoring alone does not certify the
auditor's numerical reconstruction or justify its explanation. See the
[fixed trace](../demos/claim_verification/runs/20260912T081931Z-fit-prediction-cpu-b5be5467dd/episodes/20260912T082019Z-fixed_split-b56199a889/transcript.md).

Integral matching is not an exact shortcut here: its supplied-data quadrature
produces forecast errors of approximately 2.370% and 9.379% across the two
systems. Including it exposes a real alternative and its limitations; it was
not prohibited or tuned until successful.

**Decision:** the two computational stages are real and the tool contracts
work, but this catalog does not establish the research challenge we wanted.
Park verification as a main implementation priority for now, preserve the
negative result, and concentrate on the planning/imperfect-model directions.
This is a conclusion about the tested toy, not a claim that scientific
verification is generally solved or unimportant. Proposal documents were not
modified by this milestone.

### Verification and frozen provenance

- 30 new tests pass; the complete regression run passes **584 shared tests plus
  14 planning-pilot tests**, or **598 total**.
- All 180 episode spending totals agree with their chronological solver logs
  and per-stage ledgers and remain within their caps; no accounting failures.
- Source hashes agree with the pre-policy frozen manifest.
- Offline regeneration, with numerical solving and tool execution blocked,
  reproduced both aggregate files and all 180 transcripts byte-for-byte.
- Numerical/claim tests cover independent references, actual printed values,
  stage isolation, injected fitting, best-completed-result retention, failed
  work, strict caps, cache reuse, separate episodes, duplicate calls, invalid
  requests, abstention, boundary scoring and aggregate slot uniqueness.
- Earlier model-runner regression tests use fake/mock transports. Their printed
  synthetic API ledgers do not represent live calls or actual expenditure.

Software: Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1. Source SHA-256 prefixes:
`numerics.py d0b5fa10597a`, `environment.py ae059406c0e8`,
`experiment.py b02d89ae4d0f`, package initializer `9cd7612b49e7`.
Reused planning RHS: `651a467aaa3d`; durable records: `8d1e0b0bbc05`.
The manifest records complete hashes and per-case hashes. Catalog SHA-256:
`5ef38dbf005c310151a929f6d2c4ea7e501c0e7532c54f3afeeb028880a05ced`.
Catalog hashes include runtime metadata; numerical replay is deterministic,
but rerunning on another machine need not reproduce wall times or artifact bytes.

From the repository root:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_fit_prediction_verification.py -v
.\.venv\Scripts\python.exe -B -m budgeted_science.fit_prediction_verification.experiment cpu
.\.venv\Scripts\python.exe -B -m budgeted_science.fit_prediction_verification.experiment render --path PATH_TO_RUN
```

The CPU command creates a unique ignored directory under
`demos/claim_verification/runs/`. It freezes source hashes, software versions,
cases, budgets and policies before acquiring any policy results. Changes to
the implementation during the comparison abort it. Complete catalog/reference
records, commissioning sweeps, original/purchased numerical artifacts,
chronological actions, per-stage work and submissions remain local. The
offline renderer reads saved results and events only and reconstructs reports
and readable policy transcripts without numerical or tool execution.

Scoring reports correct binary verdicts over all ten studies, false accepts,
false rejects, abstentions, incomplete outcomes, resource spending and runtime.
Abstention is a completed response, but not a correct binary answer. There is
no saving bonus, confidence score or semantic grading of explanations.

Limitations: two development systems; related variants and repeated budgets;
known model family, exact data and informative original artifacts; a single
quantity and tolerance; no structural discrepancy or physical validation;
no free-form-report model experiment. A successful prototype does not require
an adaptive-policy victory. If a cheap fixed method resolves the catalog,
retain that finding rather than redesigning repeatedly to force model failures.
