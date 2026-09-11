# GPT-5.6 Sol on the harder resource-planning toy

## Result: 2026-09-11

Exactly one live episode completed without retry, interruption, or continuation.
GPT-5.6 Sol with high reasoning spent **40/40 scientific credits** and submitted
all three parameters within the **5%** tolerance. Its largest relative error was
**0.5461%**. The stronger local-fitting baseline also passed, at **0.8771%**.

| Method | Pass | Largest relative parameter error | Worst normalized error | Low / high / measurement purchases | Seconds |
|---|---|---:|---:|---|---:|
| GPT-5.6 Sol, high | Yes | 0.5461% | 0.10921231 | 12 / 2 / 1 | 207.293 |
| Local-fitting baseline | Yes | 0.8771% | 0.17542763 | 20 / 1 / 1 | 0.210 |
| Randomized GP baseline | No | 20.1288% | 4.02576304 | 12 / 2 / 1 | 0.186 |
| Adaptive GP baseline | No | 19.5484% | 3.90968491 | 12 / 2 / 1 | 3.958 |

All methods spent 40 credits. Times are descriptive, not matched compute budgets:
GPT's time includes API latency; classical methods run locally on CPU.
Success is `max_i |estimate_i - target_i| / (0.05 |target_i|) <= 1`.

GPT submitted `[1.094, 0.1183, 1.382]`; its three relative errors were
`[0.02333%, 0.25224%, 0.54606%]`. Evaluation used that actual submission, not a
replacement estimate from the fitting helper.

This is one preselected instance. Both GPT and the stronger classical method
solve it comfortably. It does not establish general model superiority, the
benefit of adaptive resource allocation, or that every v2 instance is easy.
V1 used a different target and noiseless observations, so this is not a paired
before/after difficulty experiment. The frozen multi-instance classical pilot
and its findings remain unchanged.

## Frozen protocol

- Environment: opt-in `harder_config()`; ranges `[0.6,1.4]`, `[0.04,0.12]`,
  `[0.8,2.0]`; parameter tolerance 5%; 40 shared credits.
- Prices: low simulation 1, high simulation 8, new target scalar 12.
- Target selection: first frozen v2 evaluation target (seed 6000), first noise
  replicate (0; private observation seed 60000). Selected by original ordering,
  not by baseline outcome. Parameters and seeds were absent from agent inputs.
- Noisy free time-1 readings and paid observations: independent zero-mean
  Gaussian sensor noise, standard deviation 0.10 for x and 0.05 for y, disclosed
  as 1% of the initial population scales. Initial conditions remain exact.
  Repeated retrieval returns the same reading, not an independent replicate.
- Model: exactly `gpt-5.6-sol`, `high` reasoning, streaming Responses API,
  standard service tier, `store=false`, reasoning summaries and encrypted replay.
- Limits: $3 API ceiling, 30 responses, 32,768 maximum output tokens per
  response, 1,200 seconds of active agent time. No automatic retry or substitution.
- The initial prompt retained the user's full-budget requirement: submission
  was allowed only after spending all 40 credits. There is no savings bonus or
  confidence score. This run does not evaluate early stopping.
- Eight tools: `simulate_low`, `simulate_high`, `measure_target`, `get_status`,
  `evidence`, `compare_cached_candidates`, `fit_purchased`, `submit`.
  The fitting helper uses the unchanged GP backend, correct noisy likelihood,
  2,048 particles, and fitting seed 0. It purchases no scientific information
  and provides no policy recommendation. No arbitrary Python execution.
- Independent classical runs used the identical hidden target and noise stream,
  policy seed 0, and separate 40-credit ledgers. All three estimates and scores
  exactly matched their saved frozen-pilot case; policies were not retuned.

The agent acquired one additional x measurement at time 3.5, performed twelve
low-fidelity and two high-fidelity simulations, called the GP fitter four times,
and compared cached candidates once before submitting. All tool calls succeeded.

## API accounting and logs

There were **21 completed responses**, with 164,744 input tokens and 7,437 output
tokens, including 6,858 reasoning tokens. The conservative API cost upper bound
was **$0.972460**, with **zero unsettled reservations**, below the $3 ceiling.
This is not an invoice. Reservations use $5/million input and $20/million output
tokens and reserve the entire allowed output before a request. See the
[official model documentation](https://developers.openai.com/api/docs/models/gpt-5.6-sol).

Complete local records, ignored by Git:

- [Readable transcript](../demos/planning/runs/resource_agent_v2/20260911T131840Z-live-2ecdddb9f7/transcript.md)
- [Four-way comparison report](../demos/planning/runs/resource_agent_v2/20260911T131840Z-live-2ecdddb9f7/report.md)
- [Raw run directory](../demos/planning/runs/resource_agent_v2/20260911T131840Z-live-2ecdddb9f7/)
- [Offline full-budget rehearsal](../demos/planning/runs/resource_agent_v2/20260911T131756Z-dry-run-141908a64a/report.md)

Raw logs contain all API-visible output, including returned reasoning summaries
and opaque encrypted replay data, not readable raw internal reasoning. Private
evaluator artifacts remain separate from model-facing requests. Review logs
before sharing. The credential file was loaded only by the live runner and was
not displayed, staged, or committed.

## Verification and reproduction

**260 tests passed**: 246 shared tests and 14 planning-pilot tests, including nine
new v2 tests. Coverage includes noisy fitting against the baseline backend,
identical paired observations, noisy checkpoint restoration, full-credit gating,
history replay, interruption reservations, scoring, and offline regeneration.
All 251 pre-existing tests remain passing.

Post-run verification checked all **52 source hashes**, **2,434 chronological
events**, **21 exact request/history replays**, and **14 purchased trajectories**.
The final submitted checkpoint, observation records, ledger, and parameter score
agree with the evaluation report. Transcript, report, evaluation JSON, and raw
event log were byte-identical after offline regeneration. Scientific environment
and baseline-policy code were unchanged from the frozen v2 pilot.

- Source-manifest hash: `25d9a95b88c1fea5ca64c3f26bb5c56a061a35996153ee083df2daa849e1941f`
- Prompt hash: `14ece1a1435af3c4555ef81c2ff794ccab14c78ec9f5e5d0861e9cbe29af4799`
- Tool-schema hash: `e78d3daa1f2829965f2123ea6ca9eee17f253eb4cdc24a00bb52056ad301197f`
- Versions: Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1, OpenAI SDK 2.54.0,
  httpx 0.28.1, budgeted-science 0.1.0.

From the repository root, offline:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m unittest discover -s demos/planning/tests
.\.venv\Scripts\python.exe demos/planning/src/run_resource_agent.py --dry-run --harder --api-ceiling-usd 3.00 --require-full-budget
.\.venv\Scripts\python.exe demos/planning/src/run_resource_agent.py --render demos/planning/runs/resource_agent_v2/20260911T131840Z-live-2ecdddb9f7
```

The executed paid command below starts a NEW attempt if run again and requires
fresh authorization; it is not a report-regeneration command:

```powershell
.\.venv\Scripts\python.exe demos/planning/src/run_resource_agent.py --live --harder --api-ceiling-usd 3.00 --require-full-budget
```

V1 remains the CLI default; `--harder` explicitly selects v2. Interrupted v2
runs use the existing explicit `--resume RUN_DIR` mechanism, restoring their
configuration, private noise stream, purchases, history, and cumulative API
ledger. Do not add `--harder` on resume. Submitted episodes cannot be resumed.
No resume or extra paid episode was needed for this evaluation.
