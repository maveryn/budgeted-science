# Three target claims: Sol, Terra, Luna and CPU results

A subsequent [explicit Luna retry](target_three_luna_retry_results.md) filled
the missing study with 2/3 correct. Its retry-inclusive result is 10/18 correct,
6 wrong and 2 abstentions. The first-attempt comparison below remains unchanged.

## Matched setup

On 2026-09-13, six independent **Sol/high** and six **Terra/high** episodes
completed on the same six frozen predator-prey studies previously used for
[Luna and the continuous local-fitting CPU baseline](target_three_claims_results.md).
Each study contains three shuffled claims about the unknown fixed target:

1. All reported parameter estimates are within 5% of their true values.
2. Target trapezoidal prey abundance meets its stated threshold.
3. Target late recovery, x(8)/x(6)-1, meets its stated threshold.

The budget is **32 scientific credits per study**; low simulation, high
simulation and scalar target measurement cost **1, 8 and 12**, respectively.
Public reports, early noisy observations, target/noise instances, numerical
models, parameter bounds, thresholds and scientific tools are unchanged.
No Python or fitting helper is available to the models. All histories and
purchase ledgers are independent. The original CPU and Luna records were
imported and verified, not rerun. The [scientific protocol](target_three_claims_protocol.md)
and [matched-model protocol](target_three_models_protocol.md) give full details.

Sol and Terra used the exact requested model IDs, high reasoning, $3 per-episode
API caps, 30 responses, 32,768 output tokens per response, 60 tool requests and
20-minute episode deadlines. The approved maximum was $36 across 12 episodes.
Case order was fixed, alternating the model that ran first. No retries,
substitutions, resumes, budget increases or scientific changes occurred.

## Overall results

| Investigator | Correct / 18 | Wrong | Abstain | Unsubmitted | Utility | Completed studies |
|---|---:|---:|---:|---:|---:|---:|
| Terra/high | 16 | 2 | 0 | 0 | 12 | 6/6 |
| Sol/high | 14 | 4 | 0 | 0 | 6 | 6/6 |
| Continuous local-fitting CPU | 12 | 6 | 0 | 0 | 0 | 6/6 |
| Luna/high, original run | 8 | 5 | 2 | 3 | -2 | 5/6 |

Utility is +1 correct, -2 wrong, 0 abstain. Missing submissions are neither
wrong verdicts nor abstentions; they contribute no correct verdicts to the
18-claim total. All new runs submitted; there were no runner failures or
API/time/response-limit terminations. Correctness does not certify the
accompanying explanation or confidence.

On the **same five studies with valid submissions from every model**, Sol and
Terra each scored **13/15 correct and two wrong**; CPU scored 11/15 with four
wrong; Luna scored 8/15 with five wrong and two abstentions. Luna's study-4
empty final message remains an incomplete original attempt, not a replacement
sample. The new $3 API cap differs from Luna's $1 cap; no run in this comparison
was reported as API-cap-limited, including that earlier incomplete episode.

### Individual studies

Entries below are correct claims out of three. Sol and Terra made no abstentions.

| Study / case ID | Sol | Terra | CPU | Luna |
|---|---:|---:|---:|---|
| 1 / 007f3916057d | 3 | 3 | 2 | 1 correct, 2 abstain |
| 2 / 046a179e0513 | 1 | 3 | 1 | 2 correct, 1 wrong |
| 3 / 9e34a4196499 | 3 | 3 | 3 | 1 correct, 2 wrong |
| 4 / 255c174d83fd | 1 | 3 | 1 | No submission |
| 5 / c1755e3c74d5 | 3 | 2 | 3 | 2 correct, 1 wrong |
| 6 / 7f7aab8b1763 | 3 | 2 | 2 | 2 correct, 1 wrong |

### Claim types

| Claim type | Sol correct / 6 | Terra correct / 6 | CPU correct / 6 | Luna correct / 6 |
|---|---:|---:|---:|---:|
| Joint parameter accuracy | 6 | 6 | 6 | 2 |
| Target abundance | 4 | 5 | 2 | 2 |
| Late recovery | 4 | 5 | 4 | 4 |

For Luna, parameter accuracy and abundance each also have two wrong, one abstain
and one missing verdict; recovery has one wrong and one missing. For the other
methods every non-correct verdict in this table is wrong. A correct parameter
claim classification does not require recovering every true parameter to 5%:
rejecting an inaccurate report can be correct without an accurate full fit.

## Resources and recorded errors

L/H/M denotes newly purchased low trajectories, high trajectories and target
scalar measurements. Free original calculations and retrievals are excluded.

| Study | Sol L/H/M | Sol measurements | Terra L/H/M | Terra measurements |
|---|---|---|---|---|
| 1 | 0/1/2 | x(6.5), x(8) | 0/1/2 | x(6), x(8) |
| 2 | 4/2/1 | x(8) | 0/1/2 | x(6.5), x(8) |
| 3 | 0/1/2 | x(3.5), x(8) | 0/1/2 | x(6.5), x(8) |
| 4 | 4/2/1 | x(8) | 0/1/2 | x(6.5), x(8) |
| 5 | 0/1/2 | x(6.5), x(8) | 0/1/2 | x(4), y(4) |
| 6 | 0/1/2 | x(6.5), x(8) | 7/0/2 | x(4), y(4) |

Sol spent **32 credits in every study: 192 total**, buying 8 low trajectories,
8 high trajectories and 10 measurements. Terra spent **32 in studies 1-5 and
31 in study 6: 191 total**, buying 7 low trajectories, 5 high trajectories and
12 measurements. Leaving a credit unspent is permitted; there is no spending
penalty, full-budget requirement or savings bonus. CPU and original Luna each
spent 192 credits. CPU purchases were 12 low, one high and one measurement per
study, using its unchanged continuous local-fitting method.

- **Sol, studies 2 and 4:** all four errors were false acceptances of abundance
  and recovery claims. It bought one target reading, x(8), and spent the other
  20 credits on candidate simulations. Its explanations extrapolated from a
  locally explored parameter branch toward that reading, then used the branch
  to infer the unmeasured quantities. Those inferences were wrong under the
  reference evaluation. The parameter-accuracy rejection was correct in both.
- **Terra, study 5:** it accepted target abundance >=130; the reference is
  approximately **129.28**. It bought x(4),y(4) and judged the target's shift
  from the reported-model trajectory sufficient to cross the threshold.
- **Terra, study 6:** it rejected recovery >=-0.4; the reference is approximately
  **-0.32687**, so the claim is true. It again measured x(4),y(4), then bought
  seven low trajectories. Its parameter and abundance verdicts were correct.

These are descriptions of recorded actions and submissions, not semantic
grades. Sol's four two-measurement studies were all correct, whereas its two
one-measurement studies produced the errors. This is an **observational pattern**,
not a controlled causal comparison: studies, acquisition times, numerical
inference and decisions also differed. Terra's two-measurement mistakes show
that buying two readings is not itself a guarantee of correctness.

## API accounting and runtime

| Model | Responses | Input tokens | Output tokens, including reasoning | Reasoning tokens | Usage-cost lower estimate | Conservative upper bound |
|---|---:|---:|---:|---:|---:|---:|
| Sol | 40 | 346,239 | 76,510 | 72,386 | $1.8842528 | $3.261395 |
| Terra | 35 | 286,620 | 48,821 | 45,400 | $0.7465086 | $1.3024020 |
| New runs total | 75 | 632,859 | 125,331 | 117,786 | $2.6307614 | **$4.563797** |

All reservations settled; none remain uncertain. Every episode was within $3,
and the campaign was within $36. These usage-based bounds are **not invoices**.
The upper bound uses conservative input/cache-write rates with no cache discount;
the lower estimate accounts for cached-input discounts but excludes any cache-write
premium. The [protocol](target_three_models_protocol.md) records verified pricing.

Sol episode runtimes ranged from **160.6 to 420.2 seconds** (1,546.8 total);
Terra ranged from **50.2 to 157.0 seconds** (607.9 total). These include API and
tool execution time. They are not scientific-credit prices or controlled latency
benchmarks. All API-visible messages, returned reasoning summaries and opaque
encrypted items are retained; raw internal reasoning is not exposed.

## Verification, records and limitations

Before launch, **149 targeted tests** and the 12-episode scripted rehearsal
passed. After execution, the offline audit verified all 12 unique slots, exact
requested models/settings, unchanged frozen science and prior artifacts,
complete request/response usage, charge arithmetic, score arithmetic and
byte-identical report/transcript regeneration. No additional API or solver
calls were used for this audit.

- [Complete report with all model and CPU transcript links](../demos/paired_claim_audit/runs/20260913T093320Z-target-three-models-prepared-e30c1fbe8c/campaigns/20260913T094518Z-live-0262ddc444/report.md)
- [Machine-readable record audit and per-study allocations](../demos/paired_claim_audit/runs/20260913T093320Z-target-three-models-prepared-e30c1fbe8c/campaigns/20260913T094518Z-live-0262ddc444/record_audit.json)
- [Frozen configuration and imported-artifact hashes](../demos/paired_claim_audit/runs/20260913T093320Z-target-three-models-prepared-e30c1fbe8c/manifest.json)
- [Original Luna/CPU results](target_three_claims_results.md)

Prepared directory:
`demos/paired_claim_audit/runs/20260913T093320Z-target-three-models-prepared-e30c1fbe8c`.
Live campaign: `campaigns/20260913T094518Z-live-0262ddc444` beneath it.
Implementation checkpoint: `2154c95`.
Frozen source hash: `55e96a285fd2f15316df571ec1a7234d82aedaca52f76cd7852011b54211ef65`.
Original catalog hash: `086f913625f20a5c49eac56ad8cdafeec19fa2ef5468fef2d9d8b24fca7f1d8b`.
Software: Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1, OpenAI SDK 2.54.0,
httpx 0.28.1, budgeted-science 0.1.0.

```powershell
# Offline only; use the saved live-campaign directory above.
.venv\Scripts\python.exe -m budgeted_science.agents.target_three_models render <campaign-directory>
.venv\Scripts\python.exe -m budgeted_science.agents.target_three_models render-episode <episode-directory>
.venv\Scripts\python.exe <campaign-directory>/verify_and_summarize.py
```

**Conclusion:** the restricted toy runs end-to-end and produces objectively
scored scientific errors without runner failures in these new attempts. Terra
performed best on this small set, but still missed two claims; Sol missed four.
The six worlds form three engineered development pairs, with one episode per
model per world. This is not evidence of a general model ranking, optimal budget
allocation, justified confidence, physical validation, or held-out benchmark
difficulty. Correct verdicts can be reached through imperfect arguments. All
earlier experiments remain preserved; raw logs and credentials stay untracked.
