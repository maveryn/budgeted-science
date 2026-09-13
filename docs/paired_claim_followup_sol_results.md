# Matched follow-up toy: Sol/high results

## Outcome

All **six authorized GPT-5.6 Sol/high episodes completed**, one per frozen
development study, with independent histories and 32-credit scientific budgets.
Sol returned **29/36 correct, four wrong and three abstentions**, exactly Luna's
aggregate counts on these studies. Individual outcomes differed. There were no
retries, model substitutions, incomplete episodes or scientific changes.

Correct verdicts account for 80.6% of all claims; coverage is 33/36. Utility
under the announced +1 correct / -2 wrong / 0 abstain rule is **21**.

| Investigator | Correct / 36 | Wrong | Abstain | Utility | Mean credits |
|---|---:|---:|---:|---:|---:|
| Sol/high | 29 | 4 | 3 | 21 | 32.00 |
| Luna/high, saved matched episodes | 29 | 4 | 3 | 21 | 30.17 |
| Measurement-first adaptive CPU | 33 | 0 | 3 | 33 | 29.00 |
| Fixed x(4), fit refinement, uncertainty-aware verdicts | 30 | 0 | 6 | 30 | 29.00 |
| Fixed x(4), fit refinement, constant intervention rejection | 34 | 2 | 0 | 30 | 29.00 |
| Fixed high-fidelity intervention, no target measurement | 32 | 4 | 0 | 24 | 17.00 |
| Greedy adaptive CPU over the full action menu | 27 | 0 | 9 | 27 | 27.67 |

Luna and CPU records were imported, not rerun. CPU methods use a restricted
two-fit estimator and paid 9-credit initialization. Neither that estimator nor
initialization is imposed on the models. Fixed policies were examined on these
development cases. This is a practical comparison, not an isolated allocation
experiment or a held-out baseline selection exercise.

## Per-study outcomes and resources

Counts in the Luna column are correct / wrong / abstain.

| Study / case ID | Sol correct | Wrong | Abstain | Luna | Sol credits | Sol API upper bound |
|---|---:|---:|---:|---|---:|---:|
| 1 / fecf156f60a7 | 5 | 1 | 0 | 5 / 1 / 0 | 32 | $0.501515 |
| 2 / b387548dec7b | 3 | 0 | 3 | 4 / 1 / 1 | 32 | $0.939040 |
| 3 / 868e59454f9b | 6 | 0 | 0 | 4 / 0 / 2 | 32 | $0.568005 |
| 4 / 9599324ac351 | 4 | 2 | 0 | 4 / 2 / 0 | 32 | $0.655565 |
| 5 / 9778d9e366b9 | 6 | 0 | 0 | 6 / 0 / 0 | 32 | $0.777215 |
| 6 / baa95d258e0a | 5 | 1 | 0 | 6 / 0 / 0 | 32 | $0.834660 |

In **every study**, Sol purchased two high simulations, four low simulations
and one target scalar measurement: 2 x 8 + 4 x 1 + 1 x 12 = 32 credits.
Both high simulations evaluated the specified report and intervention parameters,
before the paid target measurement, which was always x(6.5). Low-parameter
choices and final verdicts varied, but the resource totals, high-simulation
roles and measurement location did not. No fixed acquisition sequence or
full-budget submission rule was imposed by the runner.

Total spending was **192 scientific credits**, 24 low simulations, 12 high
simulations and six measurements. Credits price synthetic scientific resources;
they are not dollars or measured runtime.

The 61 model responses used **619,472 input tokens and 58,932 output tokens**,
including reasoning. The conservative API cost upper bound was **$4.276000**;
the usage-based standard-price lower estimate was **$1.8289448**. These are
accounting estimates, not an invoice. All usage was received and reservations
settled. The user-approved ceiling was $3 per episode, $18 total; no allowance
was increased or transferred. Episode runtimes ranged from 121 to 252 seconds.
Luna's saved total upper bound was $0.18629395 under its $1-per-episode cap.

## What the traces show

| Claim referent | Correct | Wrong | Abstain |
|---|---:|---:|---:|
| Specified numerical model | 18 | 0 | 0 |
| Unknown fixed target | 11 | 4 | 3 |

Sol's errors were two false rejections and two false acceptances:

- **Study 1, C1 (target integral):** Sol rejected the true claim that the
  integral is at least 126. Its noise-adjusted estimate was about 124.94;
  the private reference is 126.2461068. Luna rejected the same claim.
- **Study 4, C3 and C5 (target integral and late recovery):** Sol accepted
  both claims using locally adjusted low-fidelity candidates. The reference
  integral is 138.94835, below 142; recovery is about -0.07495, below 0.05.
  Luna made the same two errors, despite choosing a different measurement.
- **Study 6, C2 (late target recovery):** Sol rejected the claim that recovery
  is at least -0.4, relying on low-candidate ratios near -0.4024 and -0.4608.
  The private reference is about -0.33, so the claim is true. Luna got it right.

All three Sol abstentions occurred in **study 2**, on the unknown-target
claims. Sol resolved its three specified-model claims but declined target
verdicts where its evidence and approximate candidates remained inconclusive.
Luna instead gave four correct verdicts, one wrong and one abstention there.

In **study 3**, Sol got 6/6 after retaining funds for a target measurement.
Luna bought three high simulations and one low simulation, leaving seven
credits, insufficient for a 12-credit measurement, and abstained on two claims.
This is an informative trace contrast, not proof that allocation alone caused
the outcome difference: models, inference and numerical choices also differ.

These descriptions are manual inspections of saved explanations and tool
records, not additional semantic scores or evidence of calibrated confidence.

## Records, verification and limitations

- [Complete comparison and all Sol/Luna transcript links](../demos/paired_claim_audit/runs/20260913T055416Z-followup-sol-prepared-893986f50d/campaigns/20260913T060154Z-live-ca5baf1a19/report.md)
- [Frozen preparation](../demos/paired_claim_audit/runs/20260913T055416Z-followup-sol-prepared-893986f50d/manifest.json)
- [Full Sol results and private evaluations](../demos/paired_claim_audit/runs/20260913T055416Z-followup-sol-prepared-893986f50d/campaigns/20260913T060154Z-live-ca5baf1a19/results.json)
- [Settings, safeguards and offline commands](paired_claim_followup_sol_protocol.md)

The scientific version is `paired-claim-followup-v2`. Frozen source-manifest
hash: `7f2ad8aea56e83db226e864f16d5c88eccd8a82878e4a9770700f378accf7176`.
Catalog hash: `79543b99a111c52c25aff7d851b5a6e99b6cb3c9e660387fc4dcfd47908c6b3d`.

Before execution, 150 targeted tests ran successfully with one optional skip,
and a six-episode scripted rehearsal used zero API calls. After execution, all
six event streams, 61 generation responses, 36 purchased simulation artifacts,
settled ledgers and source hashes were verified. Offline regeneration reproduced
episode transcripts/reports and the aggregate report exactly. Imported Luna
results remained unchanged. No full historical-suite run is claimed.

All available API-visible requests, streaming events, responses, reasoning
summaries, opaque encrypted reasoning items, exact tool results and numerical
artifacts remain local and ignored. Raw internal reasoning is not available.
Credentials and raw runs are not committed; proposals and earlier code/results
are unchanged.

These six studies are **three engineered development pairs**, not six random
independent systems; the last pair shares all six truth labels. Private targets
belong to the supplied two-fit set, while public instructions do not guarantee
that set is exhaustive. The CPU estimator assumes this restriction, limiting
claims about the fairness or generality of its advantage. This run confirms
that target claims are not universally solved by either model at 32 credits;
it does not establish a general model ranking or a causal benefit of adaptation.
