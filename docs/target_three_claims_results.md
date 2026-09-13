# Three target-dependent claims: Luna and CPU pilot

## Setup

This variant audits **three claims per study** on six existing predator-prey
worlds: 18 verdicts per investigator. Every claim concerns the unknown fixed
target, not numerical accuracy at specified model parameters:

1. All three reported parameter estimates are within 5% of their true values.
2. Target trapezoidal prey abundance meets or exceeds the stated threshold.
3. Target late recovery, x(8)/x(6)-1, meets or exceeds the stated threshold.

The 32-credit budget, low/high/measurement prices of 1/8/12, noise, parameter
bounds, target worlds and resource interfaces are unchanged. The original
six-claim experiments remain separate and preserved.

The author report is newly fitted using only noisy x(1),y(1), holding theta2
at 0.08. It includes the actual early calibration calculations and an Euler
trajectory at that estimate. The alternative fit and intervention material
were removed. These report changes mean the experiment is **not an isolated
claim-count ablation**. Neither investigator is supplied an exhaustive
two-candidate set. The [protocol](target_three_claims_protocol.md) gives the
complete scientific and operational specification.

## Results

All six authorized Luna/high attempts finished, with **five valid submissions
and one incomplete episode**. No retries, substitutions, budget increases or
changes to the frozen scientific setup occurred during execution.

| Investigator | Correct / 18 | Wrong | Abstain | Unsubmitted claims | Utility | Completed episodes |
|---|---:|---:|---:|---:|---:|---:|
| Luna/high | 8 | 5 | 2 | 3 | -2 | 5/6 |
| Continuous local-fitting CPU | 12 | 6 | 0 | 0 | 0 | 6/6 |

The incomplete Luna episode is not counted as three incorrect verdicts or
three abstentions. It contributes no correct verdicts to the 18-claim total.
On the **same five studies where Luna submitted**, Luna got 8/15 correct,
with five wrong and two abstentions; the CPU got 11/15 correct and four wrong.
Luna solved all three claims in none of its five completed studies; the CPU
solved all three in two of six studies.

| Study / new case ID | Luna correct | Wrong | Abstain | Status | CPU correct / 3 | Luna purchases (low/high/measurement) | API upper bound |
|---|---:|---:|---:|---|---:|---|---:|
| 1 / 007f3916057d | 1 | 0 | 2 | Submitted | 2 | 0/1/2 | $0.03175660 |
| 2 / 046a179e0513 | 2 | 1 | 0 | Submitted | 1 | 0/1/2 | $0.02292395 |
| 3 / 9e34a4196499 | 1 | 2 | 0 | Submitted | 3 | 8/0/2 | $0.05472665 |
| 4 / 255c174d83fd | 0 | 0 | 0 | No submission | 1 | 0/1/2 | $0.03237945 |
| 5 / c1755e3c74d5 | 2 | 1 | 0 | Submitted | 3 | 8/0/2 | $0.06065160 |
| 6 / 7f7aab8b1763 | 2 | 1 | 0 | Submitted | 2 | 8/0/2 | $0.05025600 |

Every investigator spent **32 credits in every study**, including the incomplete
Luna attempt. Luna bought two x measurements in each study, always including
t=8. Its other times were 6, 4.5, 6, 6, 4 and 6.5 respectively. It then used
either one high simulation or eight paid low simulations. Totals: 24 low,
three high and 12 measurements, costing 192 credits.

The 55 model responses used **569,441 input tokens and 91,945 output tokens**,
including reasoning. Total conservative API cost upper bound: **$0.25269425**;
usage-based standard-price lower estimate: **$0.14019136**. These are estimates,
not invoices. All usage was received and all reservations settled, within the
approved $1-per-episode / $6-total ceiling. Episode runtimes were 110-212 seconds.

### The incomplete attempt

Study 4's fifth API response was marked `completed` but contained an empty
final message and no function call. The runner recorded `no_submission` and
retained the complete stream. There were no prose verdicts to recover. That
response used 18,134 output tokens, below the 32,768 allowance: no output-cap
or API-budget exhaustion was reported. This is an output-completion failure,
**not evidence that three scientific claims were answered incorrectly**.
No automatic retry or supplemental scoring was performed.

### CPU comparison and claim breakdown

The independent continuous local-fitting CPU control completed all six studies:
**12/18 correct, 6 wrong, 0 abstentions**, spending 32 credits each. Utility is
0 under +1 correct / -2 wrong / 0 abstain. It bought 12 low trajectories, one
high trajectory and one target scalar per study, in addition to the free
report evidence. It does not use a two-candidate restriction.

| Claim type | Luna correct / 6 | Wrong | Abstain | Unsubmitted | CPU correct / 6 | CPU wrong |
|---|---:|---:|---:|---:|---:|---:|
| Joint parameter accuracy | 2 | 2 | 1 | 1 | 6 | 0 |
| Target abundance | 2 | 2 | 1 | 1 | 2 | 4 |
| Late recovery | 4 | 1 | 0 | 1 | 4 | 2 |

The baseline submits plug-in verdicts from its continuous parameter estimate
and corrected local affine trajectory. These predictions use purchased data,
not a final unpaid physical simulation. Its six correct parameter verdicts
do not imply six parameter estimates within 5%: rejecting an inaccurate report
does not require recovering every true parameter precisely.

## What the recorded errors show

- **Study 1:** Luna used direct x(6),x(8) measurements to verify recovery, but
  abstained on the integral and parameter accuracy. It distinguished a model
  prediction from target truth in its explanation.
- **Studies 3 and 5:** Luna rejected true parameter-accuracy claims, reasoning
  that the conditional early fit was not an accuracy certificate. Lack of a
  certificate does not imply parameter error exceeds 5%; ABSTAIN was available.
  The actual maximum errors were approximately 0.64% and 1.67%.
- **Study 2:** Luna accepted late recovery above 0.05 after measuring x(4.5)
  and x(8), but not x(6). Actual x(8)/x(6)-1 is approximately -0.0295.
- **Study 3:** it rejected the true integral-above-142 claim, using alternative
  low-fidelity trajectories. The reference integral is 148.0957.
- **Study 6:** it accepted the false integral-above-130 claim using a low
  candidate's integral near 147.25. The actual target integral is 126.7017.

These are manual descriptions of saved verdicts and explanations, not extra
semantic grades. The score remains the objective frozen evaluator. They show
that the submitted errors are not entirely explained by the incomplete run,
but do not isolate resource allocation from numerical inference or claim
interpretation. Reducing the claim count did not make this variant trivial
for Luna; it is still only a small development demonstration.

## Local records and reproduction

- [Complete campaign report and Luna/CPU transcript links](../demos/paired_claim_audit/runs/20260913T085926Z-target-three-prepared-cdb738cbfa/campaigns/20260913T090154Z-live-bb54d711bb/report.md)
- [Frozen manifest and six slots](../demos/paired_claim_audit/runs/20260913T085926Z-target-three-prepared-cdb738cbfa/manifest.json)
- [Catalog, including private truth and construction records](../demos/paired_claim_audit/runs/20260913T085926Z-target-three-prepared-cdb738cbfa/catalog.json)
- [Protocol and offline commands](target_three_claims_protocol.md)

Prepared directory:
`demos/paired_claim_audit/runs/20260913T085926Z-target-three-prepared-cdb738cbfa`.
Live campaign: `campaigns/20260913T090154Z-live-bb54d711bb` beneath it.
The scoped implementation checkpoint is `e7cd911`.
Catalog hash:
`086f913625f20a5c49eac56ad8cdafeec19fa2ef5468fef2d9d8b24fca7f1d8b`.
Source-manifest hash:
`0e5802ebbf82391722cde3392275a514a5ab339de9301c18d0eb124eba417af1`.

Before live execution, **139 targeted tests passed**, including 13 new tests,
with no skips. A six-episode scripted rehearsal completed without API calls.
The tests cover three-claim schemas and scoring, author-data isolation,
unchanged targets/noise, real report calculations, continuous baseline fitting,
budget charging, duplicates, hidden-data isolation, API history and cost
accounting, interrupted-stream preservation, frozen payloads and offline
regeneration. No full historical-suite run is claimed.

After execution, all six attempt archives, 55 generation responses, 27 purchased
simulation artifacts, settled API ledgers and source hashes were verified.
All episode transcripts/reports and the aggregate report regenerated exactly
from saved records, without API calls or solver execution. Older frozen source,
catalog and CPU results still matched their hashes. Credentials and raw runs
remain untracked; proposal documents were not edited and nothing was pushed.

## Interpretation limits

The six worlds are three engineered development pairs, with one episode per
world, not six independent random tasks or repeated model samples. All cases
were retained regardless of outcome. Existing abundance/recovery thresholds
were selected during earlier development; reported parameters and their
claims were not chosen using Luna performance.

True parameter-accuracy claims have maximum errors of about 0.81%, 0.64% and
1.67%; false ones have 33.33% maximum error. They are not a calibrated spectrum
around the 5% boundary. Related claims share evidence and can share labels.
No balance or cross-claim truth rule is disclosed to investigators.

The target belongs to the simulator's mathematical family, without structural
discrepancy. All observations are synthetic. This does not establish validation
against physical measurements, general benchmark difficulty, calibrated
confidence or a causal resource-allocation advantage. Correct verdicts do not
certify the explanations; abstentions and wrong verdicts remain separate.
