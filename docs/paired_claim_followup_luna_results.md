# Corrected follow-up toy: Luna/high results

## Outcome

All **six authorized episodes completed**, with one independent episode per
frozen development study. GPT-5.6 Luna used high reasoning and a 32-credit
scientific cap, choosing its own acquisitions from an initially unspent budget.
There were no retries, model substitutions, API-limit increases or incomplete
episodes. The scientific setup and CPU results were unchanged.

Luna returned **29/36 correct verdicts, 4 wrong verdicts and 3 abstentions**.
Correct verdicts account for 80.6% of all claims; coverage is 33/36. Utility
under the announced +1 correct / -2 wrong / 0 abstain rule is **21**.

| Investigator | Correct / 36 | Wrong | Abstain | Utility | Mean credits |
|---|---:|---:|---:|---:|---:|
| Luna/high | 29 | 4 | 3 | 21 | 30.17 |
| Measurement-first adaptive CPU | 33 | 0 | 3 | 33 | 29.00 |
| Fixed x(4), fit refinement, uncertainty-aware verdicts | 30 | 0 | 6 | 30 | 29.00 |
| Fixed x(4), fit refinement, constant intervention rejection | 34 | 2 | 0 | 30 | 29.00 |
| Fixed high-fidelity intervention, no target measurement | 32 | 4 | 0 | 24 | 17.00 |
| Greedy adaptive CPU over the full action menu | 27 | 0 | 9 | 27 | 27.67 |

CPU rows are the saved comparisons from the earlier commissioning pilot, not
new executions. Fixed policies were examined on these development cases; they
are not baselines selected on an independent training set. The CPU methods use
a restricted two-fit estimator and paid 9-credit initialization. Luna receives
the same public fits and tool menu but neither that estimator nor initialization.
This is a practical method comparison, not an isolated test of allocation alone.

## Per-study results and spending

Counts below are **new paid purchases**, excluding free retrievals and repeats.
Low/high simulations cost 1/8 credits; target scalar measurements cost 12.

| Study / case ID | Correct | Wrong | Abstain | Low | High | Measurements | Credits | API upper bound |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 / fecf156f60a7 | 5 | 1 | 0 | 2 | 2 | 1 | 30 | $0.02369325 |
| 2 / b387548dec7b | 4 | 1 | 1 | 4 | 2 | 1 | 32 | $0.04031930 |
| 3 / 868e59454f9b | 4 | 0 | 2 | 1 | 3 | 0 | 25 | $0.02743575 |
| 4 / 9599324ac351 | 4 | 2 | 0 | 4 | 2 | 1 | 32 | $0.03275760 |
| 5 / 9778d9e366b9 | 6 | 0 | 0 | 4 | 2 | 1 | 32 | $0.03306490 |
| 6 / baa95d258e0a | 6 | 0 | 0 | 2 | 2 | 1 | 30 | $0.02902315 |

Total: **181 scientific credits**, 17 low simulations, 13 high simulations and
5 target measurements. All measurements and simulations are synthetic CPU
resources; scientific credits are not dollars or measured runtime.

The 48 model responses used 386,755 input tokens and 74,671 output tokens,
including reasoning. Total conservative API cost bound is **$0.18629395**;
the usage-based standard-price lower estimate is $0.11054636. These are estimates,
not invoices. All usage was received and all reservations settled. The frozen
ceiling was $1 per episode, $6 total. Episode runtimes ranged from 109 to 207 seconds.

## What failed, and what did not

| Claim referent | Correct | Wrong | Abstain |
|---|---:|---:|---:|
| Specified numerical model | 18 | 0 | 0 |
| Unknown fixed target | 11 | 4 | 3 |

The four errors were one false rejection and three false acceptances:

- **Study 1, C1 (target integral):** Luna rejected a true assertion. Its
  explanation adjusted the target fit using noisy observations and estimated
  an integral near 124.8, below the threshold 126. The private reference is
  126.2461068, just above the threshold. This is a target-inference error, not
  failure to recompute the specified report-model integral.
- **Study 2, C5 (late target recovery):** Luna accepted a false recovery claim;
  the actual recovery is about -0.03, below the 0.05 threshold. It abstained
  on the target integral in the same episode.
- **Study 4, C3 and C5 (target integral and late recovery):** Luna used a
  low-fidelity, manually adjusted candidate to accept both claims. The actual
  target integral is 138.9484, below 142, and late recovery is about -0.07495,
  below 0.05. The supplied candidate family contains substantially different
  later trajectories despite similar early predictions.

**Study 3 gives a concrete allocation trace:** Luna bought three high-fidelity
simulations and one low-fidelity simulation, spending 25 credits. Only 7 remained,
so it could not buy a 12-credit target measurement. It correctly noted the
ambiguity between the two early-data-compatible trajectories and abstained on
the target integral and late recovery. This demonstrates a binding budget trade-off
in the executed trace; it does not by itself prove that a different allocation
would improve an arbitrary agent or establish calibrated confidence.

These are manual descriptions of saved tool traces and explanations, not extra
semantic scores. Numeric verdict grading remains the frozen objective evaluator.

## Records and verification

The [protocol](paired_claim_followup_luna_protocol.md) records model settings,
pricing verification, tools, reproduction commands and preservation rules.

- [Complete comparison, all six transcripts and per-episode reports](../demos/paired_claim_audit/runs/20260913T051751Z-followup-luna-prepared-db46c28d52/campaigns/20260913T051840Z-live-e24616a723/report.md)
- [Frozen preparation manifest](../demos/paired_claim_audit/runs/20260913T051751Z-followup-luna-prepared-db46c28d52/manifest.json)
- [All results and private evaluations](../demos/paired_claim_audit/runs/20260913T051751Z-followup-luna-prepared-db46c28d52/campaigns/20260913T051840Z-live-e24616a723/results.json)

These local ignored paths retain every available API request, streaming event,
response, returned reasoning summary, opaque encrypted reasoning item, exact
tool result and numerical artifact. Hidden internal reasoning is not available.
Each transcript contains links to its corresponding numerical artifacts.

Before paid execution, **143 targeted tests ran successfully, with one optional
test skipped**, including 11 new adapter tests. A separate six-episode scripted
rehearsal completed without API access. After execution, all six event streams
were checked for intact sequence/tail, all 48 generation responses were present,
all 30 purchased numerical artifacts were retained, source hashes matched the
frozen campaign, and episode/campaign regeneration reproduced the reports and
transcripts exactly without tool or API calls. No full historical-repository
test run is claimed. Credentials, raw logs and earlier results remain untracked
or unchanged; standalone proposal documents were not edited.

## Interpretation

This pilot is no longer universally solved by Luna at 32 credits: it exposes
target-inference errors, abstention and a simulation-versus-measurement allocation
trade-off. It does **not** establish a general benchmark or prove that adaptive
planning caused the CPU advantage. The six studies are three engineered pairs,
not six independent random systems; the last pair shares all six labels, and
both members were solved perfectly. Private targets belong to the two supplied
fits in this catalog, although the public interface makes no such guarantee.
That restricted construction and the CPU estimator's assumption are important
limitations when interpreting the comparison.
