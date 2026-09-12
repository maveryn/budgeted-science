# Verification follow-up: reconstruction and forecast ambiguity

This milestone has two separate parts: an immutable, post-hoc analysis of the
saved ten-study CPU pilot, and a new two-case evidence-sufficiency demonstration.
No LLM/API calls, credentials, new surrogate stages, proposal edits or physical
validation are included. Earlier environments and experiments remain unchanged.

## 1. Reassess the existing results without rerunning them

The original claim asked whether the reported forecast was within 3% of its
reference. Correct binary verdicts did not imply accurate check forecasts.
The new diagnostic reads the original catalog, submissions, tool responses and
numerical artifacts and scores **only the forecast explicitly cited in the
submission**. It never selects the best historical prediction after seeing truth.

Report both original verdict accuracy and check-forecast relative error. A
supplementary **joint diagnostic** requires the verdict to be correct and the
cited forecast to be within the same 3% tolerance. Abstained/missing check
forecasts do not count as successful reconstructions. Error summaries use
available cited forecasts only and report their denominator.

Joint results out of ten studies:

| Existing CPU policy | 4 credits | 8 credits | 16 credits |
|---|---:|---:|---:|
| Adaptive residual | 8/10 | 10/10 | 10/10 |
| Fixed split | 6/10 | 8/10 | 10/10 |
| Full recompute | 6/10 | 9/10 | 10/10 |
| Fit focused | 6/10 | 6/10 | 9/10 |
| Integral matching | 5/10 | 5/10 | 5/10 |
| Prediction only | 2/10 | 6/10 | 6/10 |

At four credits, adaptive residual, fixed split and full recompute all had
10/10 original verdict accuracy; their cited forecasts passed the 3% check in
eight, six and six cases respectively. Fixed split and full recompute are the
same policy at that budget, not independent confirmations. Prediction-only
produced four available cited forecasts at four credits; all other
method/budget combinations produced ten. No original score is overwritten.

**Interpretation:** the old conclusion that accurate full reproduction was
universally cheap was too strong. Verdict accuracy hid a reconstruction-quality
difference. This is a post-hoc diagnostic on ten related studies from two
development systems, not a prospective demonstration of agent superiority or
proof that allocation alone caused the difference. The CPU methods also differ
in numerical algorithms. No policy was retuned for this analysis.

An accurate replacement forecast is not necessary for every legitimate
rejection: a counterexample or bound may suffice. Consequently the joint
diagnostic is **not** proposed as a universal scientific-verification score.

Saved [rescore report](../demos/claim_verification/runs/20260912T085606Z-verification-rescore-adce2586eb/report.md)
and [provenance manifest](../demos/claim_verification/runs/20260912T085606Z-verification-rescore-adce2586eb/manifest.json).
The manifest hashes consumed source artifacts. Original case hashes, literal
claims, evaluations and cited tool/artifact values are checked for consistency.
Input files are rehashed at the end; the original run is read-only throughout.

## 2. A minimal new claim about forecast support

Reuse the same predator-prey equations, with calibration initial state `(10,5)`
and forecast initial state `(20,2)`. The forecast remains prey population at
time 24. The nominal parameter vector is `(1.0,0.08,1.4)` and its forecast is
approximately **19.2949**. There is no injected solver, optimization or surrogate
error in this new example.

The claim now explicitly means:

> Every listed parameter setting consistent with the supplied bounded-error
> observations forecasts inside approximately `[18.7161,19.8738]`.

This is a claim about what evidence constrains, **not** the accuracy of the
nominal point estimate and **not** a 95% confidence or Bayesian credible interval.

### A deliberately finite universe

The public candidate universe is the Cartesian product of these axes:

```
theta1: 0.6, 0.8, 1.0, 1.2, 1.4
theta2: 0.04, 0.06, 0.08, 0.10, 0.12
theta3: 0.8, 1.1, 1.4, 1.7, 2.0
```

There are **125 candidate parameter settings, not 125 studies**. This permits
exhaustive reference labels without pretending that a numerical optimizer
proved a global continuous bound. A demonstrated candidate outside the claimed
range also refutes the corresponding continuous-universe claim, but acceptance
over the grid establishes nothing about untested settings between grid points.

### Two matched cases, one underlying system

Both cases have the same nominal fit, nominal forecast and claimed interval:

| Supplied observations | Compatible grid candidates | Compatible forecast range | Claim |
|---|---:|---:|---|
| Sparse: prey at time 0.5 | 4 | approximately 19.295–55.520 | Unsupported |
| Rich: both populations at times 0.5,1,...,4 | 1 | approximately 19.295–19.295 | Supported **on the grid** |

The observation error bounds are absolute: `0.1` for prey and `0.05` for
predators. A candidate must satisfy every supplied observation's bound.
The record is generated without a random perturbation; the public evidence
contract nevertheless supplies bounds, not a guarantee of exact measurement.
This is a bounded-error consistency test, not a fitted probability model.

The sparse case admits `(0.8,0.04,1.4)`, `(0.8,0.04,1.7)` and `(0.8,0.04,2.0)`
as well as the nominal candidate. Their forecasts differ substantially despite
matching that observation within its bound. The nominal point forecast is
accurate in both cases, so rechecking it alone cannot settle the support claim.
One compatible grid candidate in the rich case does **not** establish continuous
parameter identifiability.

### Numerical tools, evidence and resources

Public tools expose the study, stored records, `check(candidate, stage)` for
calibration or forecast, and `submit(verdict, witness)`. There is no target-data
acquisition, hidden-reference tool, surrogate or live-model adapter. Original
nominal records and repeated purchased results are free; separate episodes
have independent purchases and budgets. The facade is trusted in-process
separation, not an arbitrary-code sandbox.

Each new calculation uses DOP853 at `rtol=1e-9, atol=1e-11`. One credit is
256 actual RHS calls, including interrupted/failed work. Sparse calibration
only integrates to time 0.5; rich calibration integrates to time 4. Forecasts
integrate to time 24. Analysis is free. Budgets are **32 and 256 credits**;
these cover a different workload from the earlier 4/8/16-credit fitting pilot.

The private evaluator independently checks all grid settings using Radau at
`rtol=1e-11, atol=1e-13` and an algebraically separate RHS. Candidate/reference
outputs must agree within `1e-5` absolute error. Classification boundaries have
explicit commissioning margins; disagreement causes failure, not silent
relabeling. These are independently checked numerical references, not formal
interval-arithmetic certificates for the differential equation.

Score verdict correctness and mechanically supported correctness separately:

- **REJECT:** the cited candidate must have completed purchased calibration and
  forecast checks, agree numerically with the private reference, satisfy all
  observation bounds, and forecast outside the claim interval. Guessing an
  actual counterexample without checking it is not evidence-backed success.
- **ACCEPT:** all 125 candidates must be covered: either a completed calibration
  check excludes the candidate, or completed calibration and forecast checks
  place its forecast inside the claim interval. Original nominal records count.
- **ABSTAIN:** a completed response but not a correct binary/evidence-backed
  verdict. Failure to find a counterexample is not automatically acceptance.

These are explicit numerical evidence contracts, not semantic grades for
free-form explanations or a uniquely correct "primary limiting stage" label.

### CPU controls and results

Three controls use the same public candidate order (NumPy permutation, seed 0):

1. **Nominal only:** asserts the claim based on its one stored fitted forecast.
   This is deliberately a verdict-only weak control, not a valid proof rule.
2. **Fixed full checking:** buys calibration and forecast for each candidate,
   even if its calibration already rules it out; rejects when it finds a witness.
3. **Screened search:** checks calibration first and only buys a forecast for
   compatible candidates. Rejects on a witness; accepts only after full coverage.

Both search controls abstain if the budget prevents completion. The screened
control is an ordinary classical search procedure, not an oracle or an agent.
The two cases times three policies times two budgets give **12 CPU episodes**,
not a statistical evaluation across independent systems.

Completed [CPU comparison](../demos/claim_verification/runs/20260912T090212Z-forecast-ambiguity-cpu-5c0876c378/report.md)
and [frozen manifest](../demos/claim_verification/runs/20260912T090212Z-forecast-ambiguity-cpu-5c0876c378/manifest.json).
All twelve episodes completed; there were no numerical, accounting or harness
failures in the corrected run. API expenditure is exactly **$0**.

| Case | Budget | Nominal only | Fixed full checking | Screened search |
|---|---:|---|---|---|
| Sparse | 32 | Incorrect ACCEPT | ABSTAIN, 32 credits | Verified REJECT, **7.668** credits |
| Sparse | 256 | Incorrect ACCEPT | Verified REJECT, 132.391 credits | Verified REJECT, **7.668** credits |
| Rich | 32 | Correct ACCEPT, no coverage | ABSTAIN, 32 credits | ABSTAIN, 32 credits |
| Rich | 256 | Correct ACCEPT, no coverage | ABSTAIN, 256 credits | Covered ACCEPT, **125.574** credits |

Nominal-only spends zero credits, but neither of its assertions is
evidence-backed under the declared contracts. Screened search needs only one
counterexample to reject, whereas its positive result covers the whole finite
universe. At 32 credits it cannot complete the rich-case coverage certificate;
that abstention is not evidence of bad reasoning. Alternative analytical
certificates could be cheaper, but this prototype does not implement them.

### Concrete rejection evidence

The sparse observation is prey population **13.106903** at time 0.5, with an
absolute error bound of 0.1. Screened search finds candidate `(0.8,0.04,1.4)`:

- Its calibration prediction is **13.025679**, a difference of **0.081224**,
  which is within the permitted measurement bound.
- Its independently checked forecast is **38.820225**, outside the claimed
  interval **[18.716064,19.873759]**.
- Both calculations were purchased and charged. This is an actual
  counterexample to the support claim, not a lucky rejection caused by an
  inaccurate check forecast.

See the [counterexample trace](../demos/claim_verification/runs/20260912T090212Z-forecast-ambiguity-cpu-5c0876c378/episodes/20260912T090502Z-screened-e0c3a73c14/transcript.md)
and the [rich-case coverage trace](../demos/claim_verification/runs/20260912T090212Z-forecast-ambiguity-cpu-5c0876c378/episodes/20260912T090507Z-screened-79369e39a9/transcript.md).

### What this does and does not establish

The example cleanly separates an accurate point prediction from a forecast
range supported by the available evidence, and makes a rejection's numerical
evidence checkable. It also illustrates the ordinary classical benefit of
screening incompatible candidates before buying expensive forecasts.

It is **not** a demonstrated hard LLM task or evidence that adaptive agents
outperform strong classical methods. The screened procedure is itself a simple
classical method. The comparison uses one system, one candidate ordering, two
observation designs and a coarse public grid. Fixed-full checking is a naive
control; its waste does not establish an advantage over all competent fixed
procedures. No significance claim, statistical-coverage claim or continuous
identifiability claim is warranted.

Keep these findings separate: the existing toy's reconstruction diagnostic is
more informative than verdict accuracy, and the new support claim has different
semantics and evidence requirements. Neither requires adding more failure
stages or launching another paid model batch now.

## Verification and provenance

- All **584 pre-existing shared tests** passed in the regression run, and the
  **14 planning-pilot tests** passed separately. One new test initially assumed
  filesystem ordering; that fixture was corrected, and the finalized **26 new
  diagnostic tests** passed. Thus 624 distinct current tests have passed across
  the regression and focused runs, not all in one clean aggregate invocation.
- The saved rescore's **536 consumed original artifacts** still match their
  recorded hashes. No original numerical solve, policy or model was rerun.
- All twelve new episode spending totals agree with chronological solver
  events and remain within their caps. Full source hashes and the reloaded
  catalog hash match the frozen manifest.
- Offline regeneration, with tools/solvers blocked, reproduces the two rescore
  report files and all fourteen ambiguity report/transcript files byte-for-byte.
- The maximum candidate/Radau output disagreements were `2.90e-8` for the
  sparse design and `1.38e-6` for the rich design, below the `1e-5` check.
- Tests cover counterfeit evidence, guessed witnesses, incomplete acceptance
  coverage, JSON-safe catalog hashes, failed/interrupted work, same-ID
  deduplication, independent episode budgets, immutable source analysis,
  ambiguous forecast citations, malformed inputs and offline rendering.

Runtime versions: Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1.
Ambiguity source SHA-256:
`e8e58df42fe66353682c8c406a281b1af04847a6b8100960885d449010059b5d`.
Reloadable catalog SHA-256:
`24c0864dace2a0d06120b4b810bcfdb90c661993829b9449bfb447e0b02300d8`.
Complete source/input hashes are in the linked manifests. Runtime metadata
means fresh-run artifact bytes need not match across executions or machines.

## Reproduce and inspect

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -B -m budgeted_science.verification_diagnostics.rescore rescore demos/claim_verification/runs/20260912T081931Z-fit-prediction-cpu-b5be5467dd
.\.venv\Scripts\python.exe -B -m budgeted_science.verification_diagnostics.rescore render PATH_TO_RESCORE_RUN
.\.venv\Scripts\python.exe -B -m budgeted_science.verification_diagnostics.ambiguity cpu
.\.venv\Scripts\python.exe -B -m budgeted_science.verification_diagnostics.ambiguity render --path PATH_TO_AMBIGUITY_RUN
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_verification_diagnostics.py -v
```

Every analysis/run creates a unique ignored directory. The ambiguity run stores
the public inputs, private reference bank and labels separately, with complete
numerical artifacts, chronological tool/charge logs, frozen configuration and
source hashes, actual submissions and per-episode evaluations. Offline renders
read saved records only. Credentials and raw runs stay untracked.

The first commissioning attempt stopped on integer JSON keys in the new
catalog, before any policy episode. That raw reference-generation directory
(`20260912T085732Z-forecast-ambiguity-cpu-309c4e1006`) is retained. The fix uses
string candidate keys, with saved-catalog round-trip and hash tests; no physical
configuration, claim, budget or policy was changed in response to outcomes.
