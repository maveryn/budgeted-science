# Paired claim audit: CPU commissioning results

## Finding

**Target measurements matter, but adaptive acquisition does not improve
accuracy over a simple fixed measurement-first policy on this catalog.**
All three measurement-first controls and the adaptive heuristic correctly
classify all 36 claims at both budgets. This is a useful evidence-dependence
check, not a demonstrated difficult resource-allocation benchmark. No paid
agent experiment was run.

## Setup

The independent `paired_claim_audit` package reuses the planning environment,
without modifying the old planning, mixed-claim or agent implementations:

\[
x'=\theta_1x-\theta_2xy-0.01x^2,\qquad
y'=0.9\theta_2xy-\theta_3y.
\]

Initial populations are (10,5), horizon [0,8], and outputs are at
0.5,1,...,8. Parameter bounds remain [0.6,1.4], [0.04,0.12], [0.8,2.0].
Low fidelity is Euler with step 0.1; high fidelity is DOP853 at
`rtol=1e-10`, `atol=1e-12`. The hidden target uses the same high-accuracy
physical family, not a structurally different simulator.

| Resource | Scientific price | Returned information |
|---|---:|---|
| New low simulation | 1 | Both populations on the full working time grid at requested parameters |
| New high simulation | 8 | The same outputs at high numerical accuracy |
| New target scalar measurement | 12 | One variable/time from the fixed hidden target, with Gaussian sensor noise |
| Reuse, evidence, status, comparisons, submission | 0 | Already available information or bookkeeping |

Noise standard deviations remain 0.1 for prey and 0.05 for predators. Repeating
the same measurement retrieves the same noisy record, not a new independent
sample. The initial conditions and noisy x(1),y(1) are free. Each episode has
its own 24- or 32-credit ledger. Prices are illustrative resource credits,
not measured runtimes or a monetary conversion. Local policy calculations
are uncharged; actual runtime is recorded.

### Six studies: three matched pairs

Within a pair, two parameter vectors produce the same early calibration but
different later trajectories. Reports, supplied candidate fits, claim order
and initial noisy evidence are identical between the two worlds. The free
observations are rounded to eight decimals, far below the sensor noise,
to prevent tiny numerical fitting residuals from identifying the member.

| Pair | Common noise-free x(1), y(1) | Target A x(4) | Target B x(4) | A recovery x(6)/x(4)−1 | B recovery |
|---|---|---:|---:|---:|---:|
| 0 | 16.715378, 4.269177 | 14.332563 | 9.706535 | −31.98% | +63.54% |
| 1 | 17.224696, 3.535370 | 18.095060 | 10.863027 | −35.10% | +66.21% |
| 2 | 18.251211, 4.483640 | 11.365468 | 9.073526 | −10.66% | +105.97% |

Anchor vectors A are (1,.08,1.1), (1,.08,1.3), (1.1,.08,1.1). Vectors B
have theta2=.12 and growth/death coefficients fitted to the same early data;
full-precision values are preserved in the frozen catalog. Pair selection
followed a 12-anchor feasibility check. These are **designed development
cases**, not held-out systems or independent random replications.

The report gives two competing parameter fits but does not identify the
true one or guarantee they are exhaustive. Both policies and future agents
would pay for new predictions. In this restricted catalog the target is
always one of those two fits, and the CPU estimator assumes that model set
is sufficient. This simplifying input is a material difference from the
earlier one-report Luna/Sol experiment.

One noise seed per pair (8400–8402) is shared across members and policies.
Claim shuffling uses 8200–8202. Opaque case identifiers and complete paired
public-input equality are tested. Case-selection metadata stays private.

### Claims and independent labels

Each report has six shuffled claims:

1. Numerical accuracy of the reported baseline x(0.5).
2. Numerical accuracy of the reported trapezoidal prey integral on the fixed
   grid—not the continuous-time integral.
3. At least a stated reduction in the grid peak after increasing theta2 by 10%.
4. Agreement of the reported x(4) with the fixed target.
5. Agreement of the reported y(6)/x(6) with the fixed target.
6. At least 20% target recovery between t=4 and t=6.

Reports contain actual Euler outputs and a low-fidelity intervention summary;
reported numerical values are not replaced with fabricated errors. All three
target-related verdicts reverse within each pair. Numerical verdicts are
shared within a pair but vary across reports. Every claim family contains
both true and false examples; overall there are 17 true and 19 false claims.

| Pair | Point tolerance | Integral tolerance | Target x(4) tolerance | Target ratio tolerance | Intervention threshold |
|---|---:|---:|---:|---:|---:|
| 0 | 5% | 5% | 5% | 15% | 5% |
| 1 | 0.05% | 0.05% | 5% | 15% | 20% |
| 2 | 5% | 0.05% | 10% | 10% | 14% |

Labels use the literal reported values and independently checked numerical
references. Maximum DOP853–Radau reference disagreement is **5.50e-9**;
maximum high-service/reference disagreement is **1.40e-8**. The maximum
within-pair early-data discrepancy before rounding is **1.36e-13**.
Target claim margins are at least 0.005 from their decision boundaries.
These are numerical cross-checks, not mathematically certified exact values
or validation against physical-world data.

## CPU policies and scoring

Five acquisition policies share the same paid initialization: high simulation
at the report parameters (8) plus low simulation at the other supplied fit
(1). This costs 9 credits; it is **not** a mandatory future-agent workflow.
The original report's low baseline trajectory is free.

All use the same two-fit estimator: initially equal weights, Gaussian
likelihoods for purchased target measurements, and a heuristic 10% relative
standard deviation for low-model predictions. Direct measurements replace
corresponding predicted quantities. Ratio/recovery uncertainty uses a delta
approximation. A high baseline run checks the two numerical claims. The
intervention uses either its published low summary or a purchased high run.
Neither estimator nor hypothetical acquisition evaluation calls an unpaid
physical solver, hidden target or evaluator.

The fixed post-initialization orders are:

- `simulation_first`: high intervention, high other fit, then x(4).
- `measure_x4_intervention`: x(4), high intervention, then high other fit.
- `measure_y6_intervention`: y(6), high intervention, then high other fit.
- `measure_x4_fit`: x(4), high other fit, then high intervention.

Unaffordable requests are rejected without charge. The last three fixed
policies use the same measurement-only continuation at 24 credits where
their requested high follow-ups are unaffordable, so the two x(4) variants
are identical policies at that budget—not independent evidence.

`adaptive_utility` considers unpurchased target measurements on the grid and
high runs for the intervention/other fit. It chooses the largest expected
increase in verdict utility per credit, using three-point Gaussian quadrature
for scalar outcomes and nine correlated trajectory fantasies for high-fit
refinement. Hypothetical draws use only its current approximate belief.
This is a custom one-step heuristic, not an optimal policy or a reproduction
of a published algorithm. It stops when no candidate is affordable or its
estimated gains are nonpositive. No claim of justified stopping is made.

The three no-purchase controls always accept, always reject, or accept all
specified-model claims and reject all target claims.

We retain correct/wrong/abstain counts and additionally report the proposed
utility **+1 correct, −2 wrong, 0 abstain**. Under the heuristic probabilities,
ACCEPT requires p>2/3 and REJECT p<1/3; otherwise the policy abstains. These
probabilities are **not validated confidence**. There is no savings bonus,
spending penalty or full-budget requirement. Explanations are preserved but
not semantically graded. Earlier agent results used different inputs and
scoring and are not directly comparable.

## Measured results

Each method/budget has six studies and 36 claims. All 96 method–budget–case
episodes completed. There were no budget overruns or API calls.

| Method | Correct / 36 at 24 and 32 | Wrong | Abstain | Utility | Spent at 24 | Spent at 32 |
|---|---:|---:|---:|---:|---:|---:|
| Adaptive utility | 36 | 0 | 0 | 36 | 21 | 29 |
| Fixed x(4), then intervention | 36 | 0 | 0 | 36 | 21 | 29 |
| Fixed y(6), then intervention | 36 | 0 | 0 | 36 | 21 | 29 |
| Fixed x(4), then other fit | 36 | 0 | 0 | 36 | 21 | 29 |
| Simulation first | 18 | 0 | 18 | 18 | 17 | 25 |
| Always accept | 17 | 19 | 0 | −21 | 0 | 0 |
| Always reject | 19 | 17 | 0 | −15 | 0 | 0 |
| Accept numerical / reject target | 17 | 19 | 0 | −21 | 0 | 0 |

The adaptive policy selects prey measurements at t=4,6,3.5 for pairs 0,1,2,
respectively. At 32 credits it then buys the high intervention trajectory.
Its sequence is identical within each pair; it does not show a successful
result-dependent change of route after receiving the differing measurements.
The extra eight credits improve its modeled confidence but **not measured
verdict accuracy** here.

Final episode runtimes sum to about 5.07 seconds, excluding catalog
construction and outer report generation. Adaptive mean runtime is 0.127s
at 24 credits and 0.143s at 32; the fixed x(4)-then-intervention policy takes
0.039s and 0.077s respectively. These are local CPU observations, not resource
price calibration.

### What this establishes—and does not

- **It removes the particular no-observation shortcut.** Within each pair,
  every possible candidate-simulation result is the same while target labels
  flip. The same no-target-evidence verdict on a target claim cannot be
  correct for both members. The previous blanket-rejection advantage does
  not survive these pairs.
- **It does not make allocation difficult.** One measurement distinguishes
  two widely separated alternatives; the rest of the target predictions
  follow from that choice. Even a fixed x(4) or y(6) measurement is sufficient
  here. Intervention claims can already be correctly classified from the
  supplied coarse summary under this estimator's assumptions at 24 credits.
- **Changing measurement location is not evidence of an adaptive benefit.**
  The adaptive heuristic changes locations across reports, but fixed choices
  tie it. More compute at 32 credits does not change the observed score.
- **This is not an open-world verification benchmark.** There are three
  pairs, one noise realization each, two supplied fits, deliberately selected
  margins/tolerances and approximate uncertainty rules. New claims, uncertain
  model coverage and repeated noisy trials remain untested. Structured claim
  fields also remove language interpretation for these CPU policies.

The result supports a small demonstration of evidence-dependent verification,
not a claim that resource-adaptive auditing has been established. Another
agent run would not by itself fix the remaining fixed-policy shortcut.

## Artifacts and reproduction

Final frozen preparation:
`demos/paired_claim_audit/runs/20260913T041036Z-paired-prepared-651e58b03e`.

[Complete result table and all 96 traces](../demos/paired_claim_audit/runs/20260913T041038Z-paired-pilot-bc0ffc6214/report.md).
Representative 24-credit traces for one paired member:
[adaptive](../demos/paired_claim_audit/runs/20260913T041038Z-paired-pilot-bc0ffc6214/episodes/20260913T041039Z-cpu-7b5aeb57ce/transcript.md),
[fixed measurement-first](../demos/paired_claim_audit/runs/20260913T041038Z-paired-pilot-bc0ffc6214/episodes/20260913T041039Z-cpu-ca35075dd2/transcript.md),
[simulation-first](../demos/paired_claim_audit/runs/20260913T041038Z-paired-pilot-bc0ffc6214/episodes/20260913T041039Z-cpu-b1bc058a42/transcript.md).
Raw artifacts are local and Git-ignored; these links require this workspace.

```powershell
.venv\Scripts\python.exe -m budgeted_science.paired_claim_audit prepare
.venv\Scripts\python.exe -m budgeted_science.paired_claim_audit pilot <new-prepared-directory>
.venv\Scripts\python.exe -m budgeted_science.paired_claim_audit render demos/paired_claim_audit/runs/20260913T041038Z-paired-pilot-bc0ffc6214
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_paired_claim_audit.py" -v
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_mixed_claim*.py" -q
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_multi_claim*.py" -q
```

Python 3.13.5; NumPy 2.3.4; SciPy 1.16.1. Parent Git state `4057aab`.
The final manifest records every shared Python source and new test-file hash:

- Source manifest SHA-256: `68868ed5b900f0eccb0342ac0f467d0617caa6c2d547d9a443af7f6cd3c0fd44`.
- Catalog SHA-256: `17ff2583917f2636aeeae63b6fa609fc5c3947ff646af13cf7735eaa11223ec6`.

The first CPU pilot (`20260913T040753Z-paired-pilot-18c47cde95`) is preserved.
A relative-path bug in offline report rendering was fixed, then the unchanged
scientific protocol was rerun under the final source freeze. All verdicts,
submissions and scientific ledgers match exactly. This is a reproducibility
repeat, not six additional independent studies; only the final pilot is
tabulated above. No policy or case was retuned after observing results.

Verification: **13 new tests plus 60 inherited tests passed; one optional
inherited test skipped (74 discovered total)**. Full historical-suite execution
was not repeated. The final report and all 96 transcripts regenerated
byte-for-byte without solvers or tool execution; raw journals were unchanged.
All paid-event totals match their ledgers, all numerical artifact links exist,
and paired public inputs are identical. Logs, credentials and generated
studies remain untracked. No credentials were read, no API expenditure was
incurred, and no standalone proposals or earlier results were modified.
