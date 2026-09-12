# Incremental claim verification: CPU calibration

## Outcome

The incremental-check implementation works, but this configuration does **not**
yet make a challenging allocation benchmark. All four numerical policies scored
29/30. Extrapolating from the same purchased peaks, without new simulations,
gave 30/30 for every policy. Even a single sampling refinement gave 29/30.
These findings are retained without changing the settings after seeing results.

This is a new development catalog and 120 CPU policy episodes, not another
Luna/Terra evaluation. No API calls or credential access were used. The original
five-credit catalog, instant-refinement tools and model results are unchanged.

## Frozen experiment

The separate package is `budgeted_science.claim_verification_incremental`.
It reuses the original predator-prey equations, initial populations (10, 5),
interval [0, 8], independently checked numerical reference, report templates,
ledger, cache, and verdict scoring. The original claim is still that the
reported maximum of the first population is accurate within 5%.

Six development systems use the original seeds 7100–7105 and parameter bounds.
Five predeclared numerical configurations per system produce 30 new studies.
Unlike the earlier catalog, these configurations were not selected to meet
truth-dependent severity bands. All original runs use Euler. Profile names
below are private commissioning labels, not public report labels.

| Configuration | Euler step | Original output spacing | Phase fraction of spacing |
|---|---:|---:|---:|
| fine | 0.005 | 0.25 | 0.25 |
| integration_coarse | 0.08 | 0.25 | 0.25 |
| sampling_coarse | 0.01 | 2 | 0.25 |
| mixed_moderate | 0.04 | 1 | 0.50 |
| mixed_coarse | 0.08 | 2 | 0.50 |

Both endpoints are always included. Ten reports use each of the three formats.
All 30 studies passed commissioning; there are **23 valid and 7 invalid claims**.
The label is calculated from the actual, ten-significant-digit printed peak,
not a fabricated answer. Always accepting would score 23/30 on this catalog.

### Incremental tools and budget

Each independent episode has **8 credits**:

- Integration refinement (I), cost 3: halve the selected run's Euler timestep,
  retaining its output times.
- Sampling refinement (S), cost 2: bisect every selected output interval,
  retaining the integration method and timestep. Old output nodes remain.
- Artifact inspection, stored-sample peak computation, comparison, retrieval,
  and submission remain free. Checks may be chained.

Sampling obtains new values from the underlying numerical trajectory, not
interpolation of sparse published samples. Repeating a purchased configuration
is free; backend caching never waives a new episode's charge. Failures retain
executed-work charges; invalid or unaffordable requests are rejected uncharged.

Two integration and one sampling refinement cost 8; one integration and two
sampling refinements cost 7; two of each would cost 10. There is no spending
penalty, full-budget requirement, or stopping bonus. These are illustrative
fixed resource prices, not measured runtime or monetary conversions.

## Policies and estimation

All policies inspect the same structured public analysis record. They do not
solve free-form report interpretation and are not general classical verifiers.
They receive only the public tool callable, not parameters, reference peaks,
or labels. Every policy operates on the original claim and chains its checks.

1. **Fixed IIS:** integration, integration, sampling; 8 credits.
2. **Fixed ISS:** integration, sampling, sampling; 7 credits.
3. **Random:** choose uniformly among affordable I/S actions until no purchase
   fits. The complete schedule is fixed before examining evidence, with seed
   `10000 + case ordinal`. One schedule per case, not many random-policy trials.
4. **Adaptive change:** first I then S; spend the remainder on the direction
   with the larger observed absolute peak change per credit, with ties going
   to I. This is a simple heuristic, not a literature-algorithm reproduction
   or an optimal allocation policy.

The primary estimator is the last purchased peak. The verdict compares its
relative difference from the original printed value with 5%. Residual error
can make that decision wrong; no confidence certificate is claimed.

A predeclared, same-evidence sensitivity calculation also fits
`Q(i,s) = Q_limit + a*2^(-i) + b*4^(-s)` by least squares. It assumes first-order
integration error and second-order peak-sampling error; these need not hold
for every run. An axis is extrapolated only if that axis was refined. The
resulting verdict is scored separately, never selected using the hidden label
and never substituted for the primary submission. No additional purchase is
needed. Perfect verdicts do not validate its uncertainty or asymptotic model.

## Measured results

| Policy | Primary correct | Same-evidence extrapolated correct | False accepts / invalid claims | False rejects / valid claims | Total credits |
|---|---:|---:|---:|---:|---:|
| Fixed IIS | 29/30 | 30/30 | 1/7 | 0/23 | 240 |
| Fixed ISS | 29/30 | 30/30 | 1/7 | 0/23 | 210 |
| Random | 29/30 | 30/30 | 1/7 | 0/23 | 229 |
| Adaptive change | 29/30 | 30/30 | 1/7 | 0/23 | 229 |

All 120 episodes submitted a binary verdict. There were no abstentions,
incomplete episodes or numerical failures. Coverage was 100%. Adaptive change
chose ISI on 19 studies and ISS on 11. Different allocations did not improve
verdict accuracy. Only 30 distinct studies on six systems are represented;
the 120 policy episodes are not 120 independent scientific systems.

Private enumeration of all affordable fixed endpoints found that **one S
purchase (2 credits) already gives 29/30** using its peak directly. This is an
endpoint diagnostic, not an extra model episode or a newly trained policy.

### Why it remains easy

Five of the six `integration_coarse` studies still meet the 5% claim tolerance.
Their errors range from 2.70% to 5.49%, so integration is the consequential
source of error in only one member of this group. A sampling check detects
the other invalid claims. Simply requiring incremental checks did not make
both resource choices important enough across these configurations.

All four primary policies miss the same study, `study-ec316754ccda8e`.
Its printed value is 47.62615638, with true error 5.4943%. The IIS purchased
peaks are 47.6261563842 → 46.4059712596 → 45.7412508388 → 45.7412508388.
Comparing the last peak directly to the report produces a false acceptance.
Extrapolation gives 45.1103476637 and correctly rejects the claim. This is
useful evidence that residual numerical error matters, but not evidence of
a difficult general auditing problem.

## Is eight credits sufficient?

All 570 reference-audited refinement endpoints through cost 12 completed.
The following is an evaluator-only diagnostic, not information delivered to
any policy:

| Budget | Studies with an affordable margin-resolving check | Studies with an affordable peak within 1% of reference |
|---|---:|---:|
| 8 | 28/30 | 29/30 |
| 10 | 29/30 | 30/30 |
| 12 | 30/30 | 30/30 |

For positive peak q, define `D(q)=abs(Q_reported-q)-0.05*q`. A check is counted
as margin-resolving if its reference-measured residual satisfies
`1.05*abs(q-Q_reference) < abs(D(Q_reference))`. This is a sufficient private
test that its direct verdict cannot cross the true label boundary. It is not
a bound available to the auditor. Failure to find such an endpoint does not
prove the task is impossible: extrapolation already resolves all verdicts here.
The 10/12-credit rows are endpoint diagnostics, not new policy runs.

## Records and reproduction

Run directory:
`demos/claim_verification/runs/20260912T002021Z-incremental-cpu-e8f1990c75/`.

- [Generated report](../demos/claim_verification/runs/20260912T002021Z-incremental-cpu-e8f1990c75/report.md)
- [Aggregate JSON](../demos/claim_verification/runs/20260912T002021Z-incremental-cpu-e8f1990c75/summary.json)
- [Chronological exact calls, results and charges](../demos/claim_verification/runs/20260912T002021Z-incremental-cpu-e8f1990c75/events.jsonl)
- [Representative IIS episode](../demos/claim_verification/runs/20260912T002021Z-incremental-cpu-e8f1990c75/episodes/104/result.json)

Each episode also retains its prompt, diagnostics, submission, private
evaluation and purchased numerical artifacts. Public study artifacts and
private catalog/reference/endpoint data are stored separately. Detailed raw
files are ignored by Git; these links are local and require retaining the run.

The manifest was frozen before commissioning or evaluation. Source-manifest
SHA-256: `d4efd448cd56738d4a8d8208455be6f0c86ea9d9f43ee83f850ad248f56f32a2`.
Python 3.13.5; NumPy 2.3.4; SciPy 1.16.1. The maximum discrepancy across the
independent reference solver/search checks was 8.682e-12 relative. All
configured study artifacts and printed values passed consistency validation.
Policy execution totaled 3.664 seconds with prewarmed backend caches; this
excludes commissioning and is not a cold-solver runtime benchmark.

From the repository root, using the existing editable installation:

~~~powershell
.\.venv\Scripts\python.exe -B -m budgeted_science.claim_verification_incremental run
.\.venv\Scripts\python.exe -B -m budgeted_science.claim_verification_incremental render demos/claim_verification/runs/20260912T002021Z-incremental-cpu-e8f1990c75
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_claim_incremental.py -v
.\.venv\Scripts\python.exe -B -m unittest discover -s tests
.\.venv\Scripts\python.exe -B -m unittest discover -s demos/planning/tests
~~~

Each `run` creates a unique directory. `render` uses saved records only and was
verified byte-identical without tools or API calls. All **394 tests passed**:
380 root tests (including 18 new tests) and 14 planning-pilot tests.

## Decision and limits

Do not yet use this calibration as evidence that agents face a challenging
resource-allocation test. A simple fixed recipe with extrapolation still
solves it. The next modest development change to investigate is coarser
integration settings that create consequential integration error on several
systems, alongside sampling defects and harmless controls. Freeze and test
that revision separately; do not remove legitimate numerical extrapolation
just because it works.

No agent adapter was changed for this milestone. Existing model commands still
target the original five-credit, instant-refinement task and must not be used
as if they implement these incremental contracts. No physical validation,
semantic diagnosis grading, justified-confidence measurement, efficient
stopping result or adaptive-policy superiority is established.
