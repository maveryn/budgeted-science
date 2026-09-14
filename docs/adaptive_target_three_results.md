# Shared adaptive multifidelity baseline: verification results

The unchanged planning investigator, with a verification-output adapter,
answered **15/18 claims correctly**, with **3 wrong verdicts, no abstentions,
and no incomplete episodes**. The previous local-fitting control obtained
12/18. All six runs spent exactly 32 credits. No LLM experiments were rerun.

This provides one shared numerical investigation method for both prototype
tasks: [planning 3/5 successful systems](adaptive_multifidelity_design_results.md)
and verification 15/18 correct claims. The tasks have different outputs,
scoring rules, and systems; these two fractions are not comparable accuracies.

## What changed

Only the output adapter changes. The acquisition algorithm, GP settings,
continuous parameter fitting, approximate local covariance, action scores,
and policy seed 0 are exactly the planning implementation. The policy file's
SHA-256 remains:
bd4853332b31b6dc2d874cf735a78821ec13c7be888c4dbcf4fdc032359e2617.

The verification wrapper gives it the same public evidence as the old numerical
control, including the free report's original Euler trajectory. It purchases
additional simulations and target measurements through the existing logged,
schema-validated audit tools.

At submission:

- Compare the reported parameter vector with the investigator's fitted vector.
- Predict the target trajectory with its fitted multifidelity GP.
- Restore physical population values from the GP's transformed outputs.
- Compute trapezoidal prey abundance on 0,0.5,...,8 and recovery x(8)/x(6)-1.
- Apply the existing structured claim inequalities to these plug-in estimates.

This final prediction is **not an unpaid high-fidelity simulation**. It is
numerical analysis of the public and purchased data. Verdicts use exactly the
old helper's comparison rules. Invalid/nonpositive/nonfinite final trajectory
predictions trigger its existing all-abstain behavior, not clipping or a
fabricated trajectory. No new confidence-based abstention policy was added.

## Frozen protocol

The six original three-target-claim studies, report formats, claim ordering,
thresholds, hidden target parameters, noise seeds, and reference labels are
unchanged. The catalog was loaded from the saved preparation, not regenerated.
Its canonical hash is:
086f913625f20a5c49eac56ad8cdafeec19fa2ef5468fef2d9d8b24fca7f1d8b.

Each episode starts with **32 credits**, plus the already available report,
original low trajectory, known initial conditions, and noisy time-1 observations.
Prices are **1 low trajectory / 8 high trajectory / 12 target scalar**.
All claim types may reuse evidence. Repeated purchases and the original
trajectory remain free to retrieve. Measurements use the existing half-unit
time grid and standard deviations 0.1 for prey and 0.05 for predator.

The investigator retains the existing CPU limits of 300 seconds and 60 tool
requests. It used 47 requests per study. Verification permits early submission;
this shared policy elects to keep acquiring until no new action is affordable.
The task does not require full expenditure or reward saving credits.

Score remains +1 correct, -2 wrong, 0 abstain. Private references, not an LLM,
determine correctness. Explanations and approximate uncertainty are not graded.

## Results

Every row purchased **12 low trajectories, one high trajectory, and one target
measurement**, in addition to the free original low trajectory. Locations and
ordering were selected adaptively, not taken from a fixed acquisition schedule.

| Study | Case | Correct / 3 | Wrong | Abstain | Credits | Seconds |
|---:|---|---:|---:|---:|---:|---:|
| 1 | 007f3916057d | 2 | 1 | 0 | 32 | 1.41 |
| 2 | 046a179e0513 | 2 | 1 | 0 | 32 | 1.65 |
| 3 | 9e34a4196499 | 3 | 0 | 0 | 32 | 2.26 |
| 4 | 255c174d83fd | 3 | 0 | 0 | 32 | 1.88 |
| 5 | c1755e3c74d5 | 3 | 0 | 0 | 32 | 2.34 |
| 6 | 7f7aab8b1763 | 2 | 1 | 0 | 32 | 2.12 |

Total: 84 paid actions, 192 credits, 11.65 seconds of recorded episode runtime,
and **$0 new API expenditure**. All six episodes completed on their first run.
There were two false acceptances and one false rejection. Coverage was 100%;
three studies had all claims correct. Total utility was 9.

| Claim type | Correct / six |
|---|---:|
| Reported parameter accuracy | 6/6 |
| Accumulated prey abundance | 4/6 |
| Late-time recovery | 5/6 |

Correctly classifying a parameter-accuracy claim does not imply recovering every
true parameter within 5%; rejecting a sufficiently inaccurate report is an
easier requirement.

### Saved comparison

| Investigator | Correct / 18 | Wrong | Abstain | Utility |
|---|---:|---:|---:|---:|
| Shared adaptive multifidelity baseline | 15 | 3 | 0 | 9 |
| Previous local-fitting baseline | 12 | 6 | 0 | 0 |
| GPT-5.6 Sol, high | 14 | 4 | 0 | 6 |
| GPT-5.6 Terra, high | 16 | 2 | 0 | 12 |
| GPT-5.6 Luna, high, completed-study view | 10 | 6 | 2 | -2 |

All older results are imported from saved files. The Luna row uses five original
completed episodes and the already authorized retry of study 4; six submissions
required seven attempts. No retry or model call was performed for this evaluation.
Equal per-study scientific caps do not imply equal computation or equal attempts.

### Three remaining errors

- **Study 1, abundance:** predicted 124.71 versus reference 126.25.
  The claim is abundance at least 126, so the baseline incorrectly rejected it.
- **Study 2, recovery:** predicted 0.308 versus reference -0.0295.
  The claim requires at least 0.05, so the baseline incorrectly accepted it.
- **Study 6, abundance:** predicted 130.85 versus reference 126.70.
  The claim requires at least 130, so the baseline incorrectly accepted it.

These are errors in fitted scientific quantities, not runner failures.
No error-driven tuning or extra study attempts followed this evaluation.

## Verification and reproducibility

The adapter tests check exact planning-policy reuse, free report inclusion,
private-information isolation, transformation and verdict arithmetic, no
physical simulation at submission, invalid-prediction abstention, metered
full-budget operation, duplicate calls, interruption handling, saved-contract
validation, and offline report regeneration. Planning and prior verification
regressions were also run; 69 targeted tests passed.

Post-run checks verified:

- All six unique study IDs and the unchanged shared policy, adapter, numerical
  implementation, verdict helper, and tool schemas.
- All 52 imported source-artifact files unchanged.
- All 84 purchases and six ledgers; no credit overrun or incomplete result.
- Untorn episode logs and byte-identical offline report/transcript regeneration.

After execution, the runner's provenance checks and partial-campaign reporting
were strengthened. Those changes did not alter the policy, adapter, scientific
code, verdicts, or six recorded episodes. The run manifest retains the source
hashes actually used at execution; the audit records this distinction.

Software: Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1.

~~~powershell
python -m unittest discover -s tests -p test_adaptive_target_three.py
# Explicitly starts six new CPU investigations, not model/API runs:
python -m budgeted_science.paired_claim_audit.adaptive_target_three_pilot run
# Saved logs only; no tools, fitting, or solvers:
python -m budgeted_science.paired_claim_audit.adaptive_target_three_pilot render <RUN_DIRECTORY>
~~~

Saved run:
demos/paired_claim_audit/runs/20260914T033437Z-adaptive-target-three-cpu-77c1fae6be/.

- [Complete report, claim-level values, and all six transcripts/acquisition traces](../demos/paired_claim_audit/runs/20260914T033437Z-adaptive-target-three-cpu-77c1fae6be/report.md)
- [Machine-readable outcomes](../demos/paired_claim_audit/runs/20260914T033437Z-adaptive-target-three-cpu-77c1fae6be/summary.json)
- [Frozen execution manifest](../demos/paired_claim_audit/runs/20260914T033437Z-adaptive-target-three-cpu-77c1fae6be/manifest.json)
- [Post-run audit](../demos/paired_claim_audit/runs/20260914T033437Z-adaptive-target-three-cpu-77c1fae6be/audit.json)

Raw runs remain local and untracked; these provenance links are not included
in a clean repository clone. No proposal documents or earlier results changed.

## Interpretation

Using this same investigator for both toy tasks is technically coherent.
However, its acquisition score still targets parameter covariance, not expected
claim utility. It may improve parameters without changing a claim's verdict.
The GP and local covariance are approximations, not certified uncertainty.

These six worlds form three engineered development pairs. The 15/18 outcome is
a small prototype result, not evidence that this method generally outperforms
Sol or that the task assesses free-form scientific verification in general.
The method receives structured claim definitions and uses fixed verdict rules.
