# Evidence-conditioned follow-up: corrected CPU commissioning

## Bottom line

The intended follow-up branch can be demonstrated, but **the result is an
error/coverage trade-off, not a clear raw-accuracy victory**.

At 32 credits on six development studies, measurement-first adaptive follow-up
gets **33/36 correct, zero wrong, three abstentions**. A fixed strategy that
refines candidate B and always rejects the unresolved intervention claim gets
**34 correct and two wrong**. The ordinary uncertainty-aware fixed fitter gets
30 correct and six abstentions. Under the declared +1/−2/0 utility, the adaptive
policy scores 33 versus the best fixed score of 30; without the wrong-answer
penalty, the 34-correct fixed guess has the larger correct count.

This is not sufficient to claim a generally difficult benchmark or an advantage
over all classical methods. No LLM/API calls were made. The completed CPU
implementation and all intermediate failures are preserved.

## Scientific setup

This opt-in variant preserves the original [paired study](paired_claim_audit_results.md),
planning environment, earlier results and proposal documents. It retains the
same six worlds arranged as three pairs, two supplied candidate fits per
report, sensor-noise streams, seven actions and 1/8/12-credit prices.

The dynamics remain

\[
x'=\theta_1x-\theta_2xy-0.01x^2,\qquad
 y'=0.9\theta_2xy-\theta_3y.
\]

Initial state is (10,5), horizon [0,8], output grid .5,1,...,8. Parameter
bounds remain [.6,1.4], [.04,.12], [.8,2]. Euler step .1 costs **1 credit**;
DOP853 at `rtol=1e-10`, `atol=1e-12` costs **8**; a target scalar measurement
costs **12**. Noise standard deviations are .1 for prey and .05 for predators.
Repeated measurements retrieve the same noisy record for free. Prices are
illustrative scientific credits, not measured runtimes or money conversions.

All acquisition policies share a paid **9-credit initialization**: high
simulation of report candidate A (8), low simulation of alternative B (1).
The report's low A trajectory and low intervention summary are free. Initial
conditions and noisy x(1),y(1) remain free. This initialization is a CPU
comparison convention, not a mandatory future-agent workflow.

Within each pair the public report and early evidence are identical. Two
candidate fits are supplied without a public promise that they exhaust the
model family. They do cover these deliberately constructed targets; the CPU
estimator assumes this. This is not open-ended model identification or
validation against physical-world experiments.

### Six claims

The existing numerical-accuracy claims for baseline x(.5) and the baseline
trapezoidal prey integral are retained, with their actual reported values and
tolerances. The remaining claims concern:

- Total target prey abundance, replacing the directly observed x(4) claim.
- Target composition, y(6)/x(6).
- Late target recovery, x(8)/x(6)−1, replacing the t=4–6 window.
- Peak reduction after increasing theta2 by 10% in the specified model.

Integrals and peaks refer to the half-unit grid, not continuous-time integrals
or extrema. Claims are shuffled using the existing order within each report.

| Pair | Target integral | Target composition | Late recovery | Model intervention reduction |
|---|---|---|---|---|
| 0 | ≥126 | ≥0.25 | ≥0.05 | ≥0.14 |
| 1 | ≥142 | ≤0.19 | ≥0.05 | ≥0.125 |
| 2 | ≥130 | ≥0.21 | ≥−0.40 | ≥0.14 |

These are **development thresholds chosen using the existing systems'
numerical behavior**, not held-out scientific requirements. The final
intervention thresholds were revised during commissioning after a cheap
control invalidated the intermediate result; that history is detailed below.

### Actual numerical disagreement, not an assumed need for refinement

The final catalog requires the matched coarse and fine intervention
calculations to imply opposite verdicts. The coarse effect uses **both coarse
peaks**, not a fine baseline peak mixed with a coarse intervention peak.

| Pair | Matched coarse effect | Checked fine effect | Threshold | Coarse / fine verdict |
|---|---:|---:|---:|---|
| 0 | 0.139046 | 0.143682 | ≥0.14 | REJECT / ACCEPT |
| 1 | 0.130226 | 0.123838 | ≥0.125 | ACCEPT / REJECT |
| 2 | 0.150232 | 0.121534 | ≥0.14 | ACCEPT / REJECT |

Reference labels use the existing independent numerical cross-checks. No
reported numerical answer is fabricated. For example, pair-0 B's coarse/fine
target integrals are 127.623/123.949, and late-recovery fractions are
+0.13798/−0.02950, crossing the target thresholds too.

In pairs 0 and 1 the target-integral and late-recovery labels reverse between
worlds. **All six labels happen to agree between pair 2's worlds.** This case
is retained rather than filtered out. The final catalog contains 18 true and
18 false claims overall. It is six related development reports with one
frozen noise realization per pair, not a statistically independent test set.

## Policies and accounting

All acquisition policies use the same public-evidence-only two-fit estimator.
Numerical uncertainty is still a **heuristic 10% relative standard deviation**,
with a correlated trajectory-error approximation for the integral and a delta
approximation for ratios. A scalar measurement can update fit weights and
individual ratio components; it is not treated as a full measured integral.
Intervention estimates use matched coarse peaks until a high intervention
trajectory is purchased. These probabilities are not calibrated confidence
bounds or error certificates.

The successful `adaptive_followup` policy purchases initialization (9), then
x(4) (12), then chooses the high intervention or high B run by estimated
verdict-utility improvement per credit. It has **11 credits** at that choice:
one high run fits, but both do not. All six episodes spend **29/32 credits**.
The initial measurement is fixed; only the follow-up is adaptive.

`adaptive_full` also chooses its first post-initialization acquisition with
the same one-step greedy rule. Hypothetical outcomes use purchased evidence
only, never hidden references, unpaid simulations or unpurchased target data.

The fixed search includes:

- All 30 scalar measurement locations on the working grid, excluding the
  already-free time-1 readings, each followed by no high run, high intervention,
  or high B: 90 schedules.
- Four no-measurement schedules: no further high run, intervention, B, or both.
- A cheap pointwise high/low A correction transferred to B, followed by the
  ordinary estimator. This is an unvalidated cheap alternative, not new data.
- Three x(4)-then-high-B controls: decide the intervention from the free matched
  coarse point estimate, always ACCEPT it, or always REJECT it.

There are 98 fixed acquisition/estimation controls, two adaptive policies and
three blanket-verdict controls: **103 policies × six studies = 618 CPU
evaluations**. These are not 618 scientific systems or agent samples. Every
policy has its own ledger and purchased evidence. The search covers this
stated menu, not arbitrary continuous parameter queries, other estimators,
or code-writing agents.

Raw correct/wrong/abstain counts are reported with **+1 correct, −2 wrong,
0 abstain**. The uncertainty-aware estimator accepts at p>2/3, rejects at
p<1/3, otherwise abstains. The explicitly labelled cheap/constant controls
instead override the intervention verdict. There is no spending penalty,
savings bonus or full-budget requirement. Explanations are not semantically
graded.

## Final results

| Policy | Correct / 36 | Wrong | Abstain | Utility | Mean credits |
|---|---:|---:|---:|---:|---:|
| Measurement-first adaptive follow-up | **33** | **0** | 3 | **33** | 29 |
| Fixed x(4), high B, uncertainty-aware intervention verdict | 30 | 0 | 6 | 30 | 29 |
| Fixed x(4), high B, always REJECT intervention | **34** | 2 | 0 | 30 | 29 |
| Fixed x(4), high B, always ACCEPT intervention | 32 | 4 | 0 | 24 | 29 |
| Fixed x(4), high B, coarse intervention point estimate | 30 | 6 | 0 | 18 | 29 |
| Fixed high intervention, no measurement | 32 | 4 | 0 | 24 | 17 |
| Fixed x(4), then high intervention | 27 | 1 | 8 | 25 | 29 |
| Fully greedy adaptive acquisition | 27 | 0 | 9 | 27 | 27.67 |
| Cheap transferred-correction control | 29 | 6 | 1 | 17 | 29 |
| Always accept all claims | 18 | 18 | 0 | −18 | 0 |
| Always reject all claims | 18 | 18 | 0 | −18 | 0 |

All 618 episodes completed without budget overruns. The best single fixed
utility is 30, shared by the constant-reject intervention strategy and several
uncertainty-aware high-B strategies. The tie-breaker in the generated report
prefers more correct verdicts, so it names the 34-correct/two-wrong strategy.

### Actual branches

| Evidence supports | Selected follow-up in all three pairs | Outcome per report |
|---|---|---|
| A | High intervention | 6 correct |
| B | High B trajectory | 5 correct, intervention abstained |

The branch is chosen from saved expected-utility scores before execution;
private world identity is used only afterward for reporting. Always refining B
misses the opportunity to resolve the intervention when A is supported.
Always buying the intervention leaves B's target computations vulnerable.
This establishes the branch mechanically, but does not establish that it is
optimal or always preferable.

### Important negative controls and limits

1. **Raw correctness does not favor the adaptive policy.** The fixed reject
   guess has 34 correct versus 33. Adaptation wins by avoiding errors under
   the declared utility, not by having the largest number correct. The utility
   expresses a specified risk preference; it is not a universal scientific
   ranking.
2. **Per-report hindsight can overfit this tiny catalog.** Choosing a fixed
   strategy separately for each pair after seeing its labels gives 36/36:
   accept the intervention in pair 0, reject it in pair 1, and use the
   no-measurement/intervention route in pair 2. This uses hindsight-selected
   label guesses, not a demonstrated deployable policy. It nevertheless
   prevents a claim that all fixed shortcuts have been eliminated. Independent
   reports are needed before interpreting an adaptive advantage broadly.
3. **Pair 2 needs no measurement for correct verdicts.** Its two worlds share
   the same labels; the fixed no-measurement/intervention route gets 12/12.
   The adaptive method gets 11/12 and spends more. It is retained as a genuine
   limitation of this construction.
4. **Greedy acquisition is not enough.** The fully greedy rule buys both high
   simulations in pair 0, leaving seven credits and no affordable measurement;
   it resolves four claims per world. Its 27/36 aggregate shows that fixing the
   initial measurement is a consequential part of the successful policy.
5. **Estimation assumptions remain important.** Structured deterministic solver
   errors are only approximately represented by the Gaussian/delta heuristics.
   Correct labels and abstentions do not establish justified confidence. The
   target belongs to a supplied two-fit set and claims are structured, so
   language interpretation and open-ended discovery are not tested.

Conclusion: the CPU toy now implements a real follow-up/error-control trade-off.
It does **not** yet justify calling the benchmark difficult for LLMs or claiming
that adaptive resource allocation universally wins. No additional scientific
retuning or paid agent run was performed after this final comparison.

## Commissioning history (retained, not pooled)

- The first attempt stopped after 200 completed policy evaluations because a
  write-once logger was asked to reuse an aggregate filename. Unique checkpoint
  names and orchestration/interruption tests fixed the runner.
- Intermediate v1 completed 600 evaluations and initially appeared favorable
  at 33 correct/zero wrong versus a utility-selected fixed score of 30.
- A post-hoc check using the already purchased x(4)/high-B evidence and the
  free, matched-coarse intervention estimate got **36/36 at the same 29 credits**.
  That erased the intermediate advantage. The common estimator also mixed a
  fine baseline peak with a coarse intervention peak unnecessarily.
- Corrected v2 uses matched-fidelity arithmetic, explicitly requires a
  consequential coarse intervention error, and includes the point-estimate
  and constant-label controls. The scientific thresholds were therefore
  revised during development, not represented as preregistered or held out.

The intermediate run, code/test snapshot and superseded draft are preserved at
`demos/paired_claim_audit/runs/20260913T043541Z-followup-pilot-1f252a031a/`.
The runner-interrupted attempt is
`demos/paired_claim_audit/runs/20260913T043258Z-followup-pilot-90703ddf12/`.
Neither is pooled with final v2 results.

## Artifacts and reproduction

[Final full table and all 618 traces](../demos/paired_claim_audit/runs/20260913T044853Z-followup-pilot-a183dde9e0/report.md).
Representative paired adaptive traces:
[A: intervention](../demos/paired_claim_audit/runs/20260913T044853Z-followup-pilot-a183dde9e0/episodes/20260913T044853Z-cpu-followup-db17746150/transcript.md),
[B: refine trajectory](../demos/paired_claim_audit/runs/20260913T044853Z-followup-pilot-a183dde9e0/episodes/20260913T044902Z-cpu-followup-619757920a/transcript.md).
Raw artifacts are local and Git-ignored.

Frozen preparation:
`demos/paired_claim_audit/runs/20260913T044814Z-followup-prepared-3e6ff0218b`.
Python 3.13.5; NumPy 2.3.4; SciPy 1.16.1; parent Git state `aba1079`.

- Source manifest: `4e3ea1e05f33f627b1bdd4cd5678c3fb6290ae2f5e7de4be786e20d937318d92`.
- Catalog hash: `79543b99a111c52c25aff7d851b5a6e99b6cb3c9e660387fc4dcfd47908c6b3d`.

Individual hashes and all policy/case settings are recorded in the manifest.
Final episode runtimes sum to approximately 49.87 seconds, excluding outer
report generation and catalog construction. This timing does not determine
scientific prices.

```powershell
.venv\Scripts\python.exe -m budgeted_science.paired_claim_audit.followup prepare
.venv\Scripts\python.exe -m budgeted_science.paired_claim_audit.followup run <prepared-directory>
.venv\Scripts\python.exe -m budgeted_science.paired_claim_audit.followup render demos/paired_claim_audit/runs/20260913T044853Z-followup-pilot-a183dde9e0
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_paired_claim*.py" -v
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_mixed_claim*.py" -q
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_multi_claim*.py" -q
```

**89 targeted tests passed; one optional inherited test skipped**: 16 follow-up,
13 original paired and 60 inherited passing claim-audit tests. The full
historical suite was not rerun. Final reports and 618 transcripts regenerate
without solver or tool calls; raw journals remain unchanged. Paid-call sums,
budget caps, numerical artifacts, paired public-input equality and matched
coarse/fine intervention-label reversals were audited. No credentials were
read, no API calls were made, and earlier proposal/result files are unchanged.
