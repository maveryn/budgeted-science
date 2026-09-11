# GPT-5.6 Terra: matched five-case planning evaluation

## Results — 2026-09-11

Completed exactly five fresh `gpt-5.6-terra` episodes with **high reasoning**.
Terra passed **2/5** cases; all five submitted valid estimates after spending
exactly **32 scientific credits**. There were no incomplete outcomes, retries,
resumptions, model substitutions, or increases to the approved limits.

The earlier 30 Sol/Luna/classical results were imported unchanged. No CPU
baseline was rerun for this extension. Success requires all three parameter
estimates to be within 5% of their true values.

| Method | Passes, all five | Median largest parameter error | Passes, four non-anchor cases | Median error, non-anchor cases |
|---|---:|---:|---:|---:|
| GPT-5.6 Sol, high | 3/5 | 3.03% | 2/4 | 6.55% |
| GPT-5.6 Terra, high | 2/5 | 20.92% | 2/4 | 12.70% |
| GPT-5.6 Luna, high | 0/5 | 17.66% | 0/4 | 22.90% |
| Local fitting | 1/5 | 6.00% | 0/4 | 8.30% |
| Random acquisition + local fit | 0/5 | 18.47% | 0/4 | 17.58% |
| Random acquisition + GP (supplementary) | 0/5 | 29.67% | 0/4 | 38.22% |
| Adaptive GP (supplementary) | 0/5 | 17.51% | 0/4 | 24.68% |

Each error column takes the median across cases of the largest relative error
among the three parameters. Pass counts and median error summarize different
aspects: Terra passed more cases than Luna but had a larger all-five median error.
All methods have five valid submissions; numerical-error summaries exclude
incomplete attempts, while success denominators would include them.

## Case-level comparison

Largest relative parameter error, in percent; values at most 5 pass.

| Target seed | Sol | Terra | Luna | Local fitting | Random + local |
|---|---:|---:|---:|---:|---:|
| 6000, exploratory anchor | 3.0347 | 27.4825 | 15.6824 | 4.7000 | 45.3075 |
| 6020 | 2.9106 | 20.9225 | 17.6567 | 5.7985 | 8.9629 |
| 6021 | 10.2116 | 42.6595 | 55.0941 | 81.1779 | 34.8755 |
| 6022 | 10.1835 | 1.5933 | 28.1468 | 10.5978 | 16.6884 |
| 6023 | 0.3037 | 4.4831 | 12.2447 | 5.9961 | 18.4709 |

Terra passed 6022 and 6023. Sol passed 6000, 6020, and 6023. On the four
non-anchor cases, both passed 2/4, but not the same two cases. These are five
systems with one rollout per model per system, not an estimate of repeated-run
consistency or evidence of general model superiority. Terra was added after the
earlier results were known; no claim of a newly held-out test set is made.

## Unchanged scientific protocol

The v2 predator-prey dynamics, bounds, noise, solvers, 16-time menu, fitting
helper, and 1/8/12 low/high/measurement prices remain unchanged. The five private
target seeds are 6000 and 6020–6023, with noise replicate 0. Each Terra episode
starts fresh, with independent purchases, all 32 credits, and matched sensor
readings. The paired Sol scientific prompt and tool schemas are checked for
exact equality before generation. Seeds, target parameters, reference data,
equations, and other methods' outcomes are not given to the agent.

The full-budget requirement remains disclosed and enforced. This experiment
does not test efficient early stopping, reliable confidence, unexpected
execution costs, or structural simulator-target mismatch. Scientific credits
and API dollars have separate ledgers. No Python execution tool was added.

Each episode retains a $3 API ceiling, 30-response limit, 32,768 output tokens
per response (including reasoning), and a 20-minute deadline. The five slots
allow at most $15 new API spending. Model support and prices were checked against
the official [Terra model documentation](https://developers.openai.com/api/docs/models/gpt-5.6-terra)
and [API pricing](https://developers.openai.com/api/docs/pricing).
Conservative reservations use $2.50/million input tokens, including the
cache-write upper bound, and $12/million output tokens. No request above 256,000
input tokens is allowed. Unknown usage would retain its reservation.

## Terra allocations and API usage

| Case | Low simulations | High simulations | New measurements | Responses | Seconds | API cost upper bound |
|---|---:|---:|---:|---:|---:|---:|
| 6000 | 4 | 2 | 1 | 10 | 105.34 | $0.1879645 |
| 6020 | 12 | 1 | 1 | 17 | 162.23 | $0.3984495 |
| 6021 | 12 | 1 | 1 | 18 | 121.92 | $0.4289195 |
| 6022 | 8 | 0 | 2 | 13 | 151.01 | $0.2898805 |
| 6023 | 12 | 1 | 1 | 18 | 96.82 | $0.3808230 |

Terra bought two target measurements and no high-fidelity simulation in the
successful 6022 case. In every other case it bought one target measurement.
These are observed choices, not proof that the allocation caused an outcome;
query locations and the final estimation procedure also matter.

Totals: **76 responses**, 510,442 input tokens, and 34,161 output tokens,
including 31,990 reasoning tokens. Total episode time was 637.33 seconds;
median episode time was 121.92 seconds. Runtime includes API latency and is
descriptive, not a matched compute comparison with the CPU baselines.

The total new API cost upper bound is **$1.6860370**, with no unsettled
reservations. This conservative bound is not an invoice. Historical Sol/Luna
costs are excluded, and their original records were not modified.

## Verification and reproducibility

**294 tests passed:** 280 shared tests, including six new Terra tests, plus
14 preserved planning-pilot tests. Coverage includes model selection, pricing,
unknown-usage reservations, resume identity, prompt matching, zero new baseline
execution, full-budget fake runs, provenance guards, continuation without
duplicate episodes, and offline report regeneration.

A separate five-slot offline rehearsal used scripted responses on these already
evaluated cases and made no API calls. The final audit verified all 35 result
identities, unchanged prior artifacts, 59 frozen source files, all 76 exact
request-history replays, scoring, scientific charges, model/reasoning settings,
and reconstructed token reservations and settlements. All 53 Terra simulations
are logged. Regenerating the five transcripts/reports and aggregate report from
saved records produced byte-identical output without tools or API execution.

Source-manifest digest:
`514965dea40ec744d12ef3464bbedf65eb8cf7d01eedb5dbedafe361a6c3a8d6`.

Software: Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1, OpenAI SDK 2.54.0,
httpx 0.28.1, budgeted-science 0.1.0. The manifest freezes complete source and
prior-artifact hashes. Local import-integrity integration tests require the
preserved campaign artifacts; those private artifacts are not in Git.

- [Combined report and links to all five Terra transcripts](../demos/planning/runs/resource_terra_five_case/20260911T200237Z-prepared-cabe9f2088/report.md)
- [Machine-readable 35-result comparison](../demos/planning/runs/resource_terra_five_case/20260911T200237Z-prepared-cabe9f2088/summary.json)
- [Frozen manifest and private case metadata](../demos/planning/runs/resource_terra_five_case/20260911T200237Z-prepared-cabe9f2088/manifest.json)
- [Offline audit](../demos/planning/runs/resource_terra_five_case/20260911T200237Z-prepared-cabe9f2088/audit.json)
- [Original Sol/Luna/classical report](resource_planning_five_case_results.md)
- [Terra runner commands](../demos/planning/README.md#terra-extension-of-the-completed-five-case-campaign)

All API-visible requests, responses, streaming events, tool outputs, numerical
artifacts, and returned reasoning summaries are saved locally. Encrypted
reasoning replay items remain opaque; raw internal reasoning is not available.
Logs and credentials remain ignored and untracked. Review private records
before sharing.

Offline report regeneration, from the repository root:

```powershell
.\.venv\Scripts\python.exe -m budgeted_science.agents.terra_campaign render demos/planning/runs/resource_terra_five_case/20260911T200237Z-prepared-cabe9f2088
```

The live workflow was `terra_campaign prepare`, then `terra_campaign live`
with this frozen directory. `continue` skips completed slots and never
automatically repeats an attempted episode. New paid runs need fresh approval.
