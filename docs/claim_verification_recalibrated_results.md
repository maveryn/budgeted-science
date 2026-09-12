# Claim verification: severity-recalibrated CPU results

## Outcome

Recalibration made integration errors consequential and removed the nearly
perfect single-sampling-check shortcut. It did **not** establish a difficult
allocation task: all four extrapolation-based policies scored **35/35 on the
fresh systems**. Development scores were 34/36 or 35/36.

The experiment generated 36 development studies and 35 fresh studies, with
284 complete CPU policy episodes. One of the 72 requested study slots could
not be populated under the frozen rules. It was retained as a commissioning
failure, not replaced or silently excluded. There were no model/API calls,
credential reads, proposal edits or changes to prior saved results.

## What changed

The predator-prey equations, initial populations (10, 5), interval [0, 8],
original peak claim, **5% tolerance**, **8-credit cap**, and tool prices remain
unchanged from the [incremental pilot](claim_verification_incremental_results.md).
Integration refinement halves the current Euler step for 3 credits; sampling
refinement bisects the current output intervals for 2. Both can be chained.
There is no early-stopping bonus, spending penalty or full-budget requirement.

The new commissioning sweep uses these configurations:

| Error family | Integration steps | Output spacing | Phase fractions |
|---|---|---|---|
| Integration | 0.005, 0.01, 0.02, 0.04, 0.08, **0.16, 0.32** | 0.01 | 0 |
| Sampling | 0.005 | 0.1, 0.25, 0.5, 1, 2, 4 | 0, 0.25, 0.5, 0.75 |
| Mixed | 0.04, 0.08, 0.16, 0.32 | 0.5, 1, 2, 4 | 0, 0.25, 0.5, 0.75 |

Endpoints are included. Each system has 95 candidate numerical studies. All
1,140 candidates across the 12 systems executed successfully; the complete
sweeps, outputs and selection decisions are retained locally.

For each family and system, select one valid and one invalid claim:

- Valid: error between 0.5% and 4%, closest to 2%.
- Invalid: error between 6% and 15%, closest to 8%.
- Ties: configuration order. Selection never uses policy performance.
- Mixed cases additionally require integration and sampling contributions
  each to have magnitude at least 1% of the reference peak.

For commissioning, the integration contribution is the maximum over all Euler
nodes minus the independently checked reference peak. The sampling contribution
is the reported-sample maximum minus that all-node maximum. For piecewise-linear
Euler output, the all-node maximum is its trajectory maximum. Contributions are
signed, so mixed cases can exhibit error cancellation. This decomposition is
private and is never returned by an audit tool.

Claims come from the actual executed pipeline and are rounded to ten significant
digits before scoring. Public reports do not contain family labels, severity
labels, reference peaks or component-error diagnostics. They retain legitimate
numerical settings and outputs. All originals use Euler.

## Development and fresh-system protocol

The complete selection grid, error bands, policies, seeds and costs were frozen
in the manifest before the run. No scientific settings were changed after
examining development or fresh results.

- Development: six existing systems, seeds 7100–7105; 36 studies, 18 valid and
  18 invalid, with 12 studies per family.
- Fresh: six prospectively selected systems, seeds 7200–7205; 35 studies,
  18 valid and 17 invalid. Integration and sampling each have 12; mixed has 11.
- The fresh system at seed 7204 had no eligible **mixed-invalid** configuration.
  Its other five studies were evaluated. No system replacement or band widening
  was performed. Policy accuracies are over generated study inputs; this absent
  slot is a generator failure, not an incomplete policy episode.

The same uniform parameter generator and existing bounds were used. Reference
evaluation retains the independent DOP853/Radau and peak-search checks. This is
a numerically checked reference, not a formal exact-solution certificate.
Fresh systems are unseen instances of the same selected task family, not a
claim of domain or task-family generalization.

## Baselines

The four acquisition policies are unchanged: fixed IIS, fixed ISS, a random
schedule fixed before seeing evidence, and a change-per-credit adaptive rule.
Here I means integration and S means sampling. Adaptive checking starts IS,
then chooses I or S by the larger observed absolute peak change per credit.
These are simple task-specific policies, not general scientific verifiers.

**Extrapolation is now the submitted estimator for every policy**, not a
post-hoc alternative. The common fitter uses only purchased peaks:
`Q(i,s) = Q_limit + a*2^(-i) + b*4^(-s)`, extrapolating only axes that were refined.
It assumes first-order integration and second-order sampling error. Its
estimate is compared with the original printed peak using the 5% rule. Missing
or unusable extrapolation causes abstention, not a reference-based fallback.
No fitting step invokes a physical solver or unpurchased reference.

Policies have independent ledgers and only public tool access. Cache hits
never waive an episode's purchase cost. Random schedules use
`10000 + case ordinal` across the frozen order, one schedule per study. Resource
prices are illustrative flat credits, not measured compute or monetary costs.

## Measured performance

| Policy | Development correct | Fresh correct | Development false accepts / rejects | Fresh false accepts / rejects | Development / fresh credits |
|---|---:|---:|---:|---:|---:|
| Fixed IIS | 35/36 | **35/35** | 1 / 0 | 0 / 0 | 288 / 280 |
| Fixed ISS | 34/36 | **35/35** | 1 / 1 | 0 / 0 | 252 / 245 |
| Random | 35/36 | **35/35** | 1 / 0 | 0 / 0 | 276 / 272 |
| Adaptive change | 35/36 | **35/35** | 1 / 0 | 0 / 0 | 270 / 263 |

All 284 episodes completed with binary submissions, so coverage was 100% and
there were no abstentions or incomplete investigations. Total scientific
expenditure was 2,146 credits across independent episodes. False-acceptance
denominators are 18 invalid development and 17 invalid fresh claims;
false-rejection denominators are 18 valid claims in each cohort.

Every policy solved all integration-only and sampling-only studies. The five
development mistakes across methods occurred in mixed cases. IIS alone was
correct on two cases that ISS missed; ISS alone was correct on one IIS missed.
There was no such disagreement in the fresh cohort. Adaptive checking chose
ISI/ISS 18/18 times in development and 18/17 times in fresh studies.

Using the final purchased peak without extrapolation would give fresh scores
34/35, 28/35, 32/35 and 34/35 respectively. These are same-evidence diagnostic
scores, not the actual submissions. The difference underscores why competent
numerical estimation should remain part of the comparison.

### Shortcut controls

One sampling purchase, evaluated directly without extrapolation, scored
**25/36 development and 25/35 fresh**. The previous near-perfect shortcut is
therefore no longer present on this selected catalog.

A simple zero-purchase metadata control fitted only on development labels chose
the rule: accept when Euler step <=0.08, otherwise reject. It scored 26/36
development and 25/35 fresh. This one-threshold control is not an exhaustive
test for metadata shortcuts. Always accepting scores 18/36 and 18/35.

### Representative mixed-error result

On development case `study-521bfc67cfaf87`, the integration contribution was
+18.353% and sampling contribution -25.955%, leaving a reported error of
7.602%. IIS extrapolated a peak of 26.967 and falsely accepted the reported
27.9006; ISS extrapolated 30.0689 and correctly rejected it. Allocation can
matter on individual mixed cases, but this did not produce a consistent
adaptive-policy advantage or a challenging fresh comparison.

## Budget reachability

Private enumeration checks which refined numerical outputs can be reached.
A margin-resolving output is defined by the sufficient reference-based
diagnostic in the [earlier report](claim_verification_incremental_results.md).
It is not an auditor-visible error certificate or an optimal policy.

| Budget | Development: margin-resolving / within 1% | Fresh: margin-resolving / within 1% |
|---|---:|---:|
| 8 | 34/36 / 24/36 | 34/35 / 26/35 |
| 10 | 35/36 / 27/36 | 35/35 / 33/35 |
| 12 | 35/36 / 34/36 | 35/35 / 35/35 |

These are affordable-endpoint diagnostics, not additional policy evaluations.
Extrapolation can succeed without purchasing an output that passes the private
margin test. No conclusion about justified confidence follows from correct
binary verdicts.

## Verification, records and reproduction

Run: `demos/claim_verification/runs/20260912T021845Z-recalibrated-cpu-1f6f2893c3/`.

- [Full generated report](../demos/claim_verification/runs/20260912T021845Z-recalibrated-cpu-1f6f2893c3/report.md)
- [Aggregate results and controls](../demos/claim_verification/runs/20260912T021845Z-recalibrated-cpu-1f6f2893c3/summary.json)
- [Exact chronological tool records](../demos/claim_verification/runs/20260912T021845Z-recalibrated-cpu-1f6f2893c3/events.jsonl)
- [IIS mixed-error trace](../demos/claim_verification/runs/20260912T021845Z-recalibrated-cpu-1f6f2893c3/episodes/092/transcript.md)
- [ISS trace on the same study](../demos/claim_verification/runs/20260912T021845Z-recalibrated-cpu-1f6f2893c3/episodes/093/transcript.md)

All sweeps, selections, original and purchased trajectories, exact public
responses, submissions, private evaluations, and readable transcripts are
retained in ignored local directories. Raw links will not exist in a fresh
clone until runs are generated or transferred deliberately.

Source-manifest SHA-256:
`e6e5c5508af7028ee1093285c0f38ceaeeebb3f27d1f55039d1e65c6753f22b6`.
Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1. All frozen source hashes matched
after execution. Maximum reference solver/search disagreement was 1.221e-11
relative. All 71 admitted study artifacts passed consistency checks; all 284
actual submissions matched their recorded extrapolated verdicts. All episodes
stayed within their independent eight-credit caps, spending seven or eight. Policy execution
totaled 21.482 seconds, excluding commissioning and using some cached results;
this is not a cold-solver speed comparison.

All **404 tests pass**: 390 root and 14 planning-pilot tests. This includes
10 new checks for severity selection, missing categories, estimator submission,
fresh-label isolation, report consistency and offline regeneration. Reports
regenerate byte-identically without running tools or contacting an API.

From the repository root:

~~~powershell
.\.venv\Scripts\python.exe -B -m budgeted_science.claim_verification_incremental.recalibrated run
.\.venv\Scripts\python.exe -B -m budgeted_science.claim_verification_incremental.recalibrated render demos/claim_verification/runs/20260912T021845Z-recalibrated-cpu-1f6f2893c3
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_claim_recalibrated.py -v
.\.venv\Scripts\python.exe -B -m unittest discover -s tests
.\.venv\Scripts\python.exe -B -m unittest discover -s demos/planning/tests
~~~

## Verdict on this revision

The numerical severity imbalance is corrected: integration-invalid cases now
exceed the claim tolerance across all 12 systems, and mixed cases have both
components present. However, a fixed checking recipe plus simple extrapolation
remains sufficient on every generated fresh study. Retain this as a verification
implementation demo; it does not yet demonstrate that adaptive allocation is
necessary. Do not keep tuning against these fresh results to manufacture a
policy gap. The findings concern this single-peak, two-tool family and do not
show that the broader verification proposal is infeasible.

No GPT evaluation of this revision has been performed, so classical success
does not establish how GPT will perform. Existing model commands still target
the original five-credit, instant-refinement task; no model adapter was changed.
