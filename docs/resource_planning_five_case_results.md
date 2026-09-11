# Five-case matched evaluation at 32 scientific credits

## Result: 2026-09-11

Completed the eight authorized new model episodes and 17 CPU episodes, retaining
five imported results unchanged. All **30 method-case results** have valid
submissions and spent exactly 32 credits. There were no incomplete episodes,
automatic retries, resumptions, model substitutions, or increased limits.

| Method | Successes, all five | Median largest parameter error | Successes, new four | Median largest error, new four |
|---|---:|---:|---:|---:|
| GPT-5.6 Sol, high | **3/5** | **3.03%** | **2/4** | **6.55%** |
| GPT-5.6 Luna, high | 0/5 | 17.66% | 0/4 | 22.90% |
| Local fitting | 1/5 | 6.00% | 0/4 | 8.30% |
| Random acquisition + local fit | 0/5 | 18.47% | 0/4 | 17.58% |
| Random acquisition + GP (supplementary) | 0/5 | 29.67% | 0/4 | 38.22% |
| Adaptive GP (supplementary) | 0/5 | 17.51% | 0/4 | 24.68% |

Success requires every parameter to be within 5% of its true value. Error columns
are the median, across cases, of each case's largest relative parameter error.
The two median columns use five and four valid submissions respectively.
Incomplete attempts would count as nonsuccesses but be excluded from numerical
error summaries; there were none here.

## Individual paired results

Largest relative parameter error, in percent; values at most 5 pass.

| Target seed | Sol | Luna | Local fit | Random + local | Random + GP | Adaptive GP |
|---|---:|---:|---:|---:|---:|---:|
| 6000, exploratory/imported | 3.0347 | 15.6824 | 4.7000 | 45.3075 | 29.6749 | 17.5129 |
| 6020, new | 2.9106 | 17.6567 | 5.7985 | 8.9629 | 21.5505 | 15.2339 |
| 6021, new | 10.2116 | 55.0941 | 81.1779 | 34.8755 | 49.6138 | 34.1206 |
| 6022, new | 10.1835 | 28.1468 | 10.5978 | 16.6884 | 26.8169 | 11.7966 |
| 6023, new | 0.3037 | 12.2447 | 5.9961 | 18.4709 | 66.0483 | 52.7647 |

The new random-local result on seed 6000 was computed in this milestone; only
the two model results and three previously existing CPU results were imported.
The original case had already influenced budget exploration and is not described
as an untouched test case. The four new targets were fixed before evaluation,
without screening or replacement. The older 40-credit pilot is not pooled here.

## Frozen protocol and implementation

The predator-prey v2 environment, public bounds, noise levels, numerical
solvers, 16-time menu, and 1/8/12 low/high/measurement prices are unchanged.
Parameters use the existing uniform seeded generator; each case uses noise
replicate 0, with private noise seed `10 * target_seed`. Each method has independent
purchases and state but identical sensor readings at matching query locations.
The agent never receives target parameters, seeds, reference artifacts, equations,
or other methods' results.

Sol and Luna received identical scientific prompts within each case. Across
cases only the initial observed values changed. Each used high reasoning,
32 scientific credits, a $3 API ceiling, 30 responses, 32,768 output tokens per
response, and a 20-minute deadline. The full-budget requirement remains disclosed;
this experiment does not test efficient early stopping. New cases ran in seed
order, alternating which model ran first. Classical methods retained seed 0 and
their separate five-minute CPU limit.

The new `random_local` policy reuses the existing lower-budget random-GP
acquisitions: 12 scrambled-Sobol low trajectories, one high trajectory at the
first low location, and one seeded random unpurchased target reading. It fixes
the complete plan before reading target evidence. It then uses the existing
`LocalFit` correction, affine approximations, bounds, regularization and multistart
procedure to submit the lowest-residual proposal, without another physical solve.
No existing baseline or agent fitting helper was retuned.

The campaign freezes source/dependency hashes, imports, cases, settings and
execution order; validates comparison snapshots; and logs slot starts durably
before launching work. An OS-held writer lock prevents concurrent dispatch.
Continuation skips completed slots and can reconcile finalized child records,
but never silently repeats an attempted episode. Uncertain partial launches
retain the full slot reservation until inspection. Existing explicit episode
resume preserves its cumulative limits and sample identity. Imported logs remain
byte-for-byte unchanged.

## Allocations, time, and API accounting

Counts below are low simulations / high simulations / new target measurements.
All four CPU policies bought **12 / 1 / 1** in every case, although their locations
and estimation methods differed.

| Target | Sol purchases | Luna purchases |
|---|---|---|
| 6000 | 12 / 1 / 1 | 8 / 3 / 0 |
| 6020 | 4 / 2 / 1 | 16 / 2 / 0 |
| 6021 | 12 / 1 / 1 | 8 / 3 / 0 |
| 6022 | 4 / 2 / 1 | 8 / 3 / 0 |
| 6023 | 4 / 2 / 1 | 8 / 3 / 0 |

Luna purchased no additional target measurement in any case; Sol purchased one
in each. This is an observed behavioral difference, not evidence that this choice
alone caused their accuracy difference. Scientific spending and API dollars are
separate ledgers; free analysis is allowed under the unchanged task rules.

| New episodes only | Responses | Input tokens | Output tokens (includes reasoning) | Reasoning tokens | Median episode time | API cost upper bound |
|---|---:|---:|---:|---:|---:|---:|
| Sol, four runs | 57 | 384,172 | 35,831 | 34,326 | 238.08 s | $2.637480 |
| Luna, four runs | 66 | 488,405 | 31,690 | 29,786 | 115.84 s | $0.16012925 |

Total new API cost upper bound: **$2.79760925**, against a maximum of $24
($3 per episode, without transferring unused allowances). No unsettled request
reservations remain. Imported historical model costs, **$0.88780830**, are separate.
These conservative bounds are not invoices. Accounting follows the verified
[official pricing](https://developers.openai.com/api/docs/pricing), reserving
cache-write input rates and the full output allowance before each generation.
Runtime includes API latency and is descriptive, not a matched compute comparison.

## Verification, records, and reproduction

**288 tests passed:** 274 shared tests, including 18 new campaign tests, plus
14 preserved planning-pilot tests. Coverage includes import validation, seeded
instances, paired noise, random-policy independence, existing-fitter agreement,
no unpaid fitting calls, failed-purchase charges, interruption recovery, duplicate
prevention, missing usage, cumulative limits, scoring, and offline regeneration.
The complete scripted rehearsal used development seeds 5000-5003, not the new
evaluation targets, and made no API calls.

The independent final audit checked all 30 results, 57 frozen source files,
156 exact request-history replays (including the imported model runs), 366
successful simulation events, and 39 distinct paired sensor locations across
cases. It verified scoring, all 32-credit ledgers, API-cost arithmetic,
unchanged imports, identical paired prompts, and byte-identical regeneration of
new episode reports/transcripts and the campaign summary. Model logs retain all
API-visible material and returned reasoning summaries, not raw internal reasoning.

- [Complete campaign report and links to every episode](../demos/planning/runs/resource_five_case/20260911T144803Z-prepared-24ca583c0a/report.md)
- [Machine-readable results and all private evaluations](../demos/planning/runs/resource_five_case/20260911T144803Z-prepared-24ca583c0a/summary.json)
- [Frozen manifest and private case identities](../demos/planning/runs/resource_five_case/20260911T144803Z-prepared-24ca583c0a/manifest.json)
- [Append-only campaign journal](../demos/planning/runs/resource_five_case/20260911T144803Z-prepared-24ca583c0a/events.jsonl)
- [Earlier Sol case](resource_planning_v2_32_credit_run.md) and [earlier Luna case](resource_planning_v2_luna_run.md)

Source-manifest digest:
`206eecaf0f399e6458f039b984c21414dde450f6f4fbfbe7d2b376e1b6377116`.
Software: Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1, OpenAI SDK 2.54.0,
httpx 0.28.1, budgeted-science 0.1.0. Raw records and credentials remain local
and untracked; review private artifacts before sharing.

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m unittest discover -s demos/planning/tests
.\.venv\Scripts\python.exe -m budgeted_science.agents.campaign dry-run
.\.venv\Scripts\python.exe -m budgeted_science.agents.campaign render demos/planning/runs/resource_five_case/20260911T144803Z-prepared-24ca583c0a
```

The executed live workflow was `campaign prepare`, then `campaign live` with
the prepared directory linked above. Reproducing a new paid campaign requires
fresh authorization; the completed campaign must not be restarted. See the
[runner instructions](../demos/planning/README.md#five-case-matched-campaign).

## Limits of interpretation

This is a five-system pilot with one model rollout per case, not an estimate of
within-case rollout consistency or a reliable general success rate. Sol's 3/5
includes the explored anchor; on the four new cases it passed 2/4. These data do
not establish superiority over stronger classical inference algorithms.

The random-local and random-GP controls have identical acquisitions, so their
contrast exposes estimator dependence; replacing GP fitting did not make the
random control pass. Comparisons with local fitting or agents also differ in
query locations and analysis, and do not isolate budget allocation causally.
The task retains fixed prices and no simulator-target structural mismatch; it
does not evaluate unexpected execution costs, justified confidence, or efficient
stopping. No task settings were adjusted after seeing these results.
