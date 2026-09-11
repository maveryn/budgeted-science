# GPT-5.6 Luna on the 32-credit planning task

## Result: 2026-09-11

One GPT-5.6 Luna/high episode completed **32/32 scientific credits** and made a
valid submission, but **failed the 5% parameter-accuracy requirement**. Its
largest relative parameter error was **15.6824%**. This was an accuracy failure,
not a runner interruption or missing submission.

| Method | Largest relative parameter error | Pass | Low / high / new-measurement purchases |
|---|---:|---|---|
| GPT-5.6 Luna, high | 15.6824% | No | 8 / 3 / 0 |
| GPT-5.6 Sol, high (earlier matched run) | 3.0347% | Yes | 12 / 1 / 1 |
| Local-fitting baseline | 4.7000% | Yes | 12 / 1 / 1 |
| Randomized GP baseline | 29.6749% | No | 12 / 1 / 1 |
| Adaptive GP baseline | 17.5129% | No | 12 / 1 / 1 |

All rows concern the same target and noise realization, at 32 credits. The Sol
row is the preserved earlier episode, not a second Sol evaluation in this turn.
The three CPU baselines were rerun independently and their evaluations exactly
matched the earlier saved results. No scientific implementation or policy was
retuned.

Luna submitted `[1.0, 0.1, 1.2]`. Relative parameter errors were
`[8.61365%, 15.68237%, 12.69517%]`; every parameter exceeded 5%. Worst normalized
error was **3.13647383**, where success requires at most 1.

Luna bought eight low-fidelity simulations, called the GP fitter, then bought
three high-fidelity simulations. It called the fitter again, compared cached
candidates, and submitted a previously simulated parameter vector. It purchased
**no additional target observation**, relying only on the initial free evidence.
All tool calls succeeded. This differs from Sol's allocation, but one rollout
does not establish that allocation caused the error or that either model has a
particular general success rate.

## Matched protocol and pricing

The scientific prompt and tool-schema files are **byte-identical** to Sol's
32-credit run. The hidden target, noise seed, free observations, public bounds,
measurement noise, prices, fitting helper, 5% tolerance, and full-budget
submission requirement are unchanged. Luna started a fresh conversation and
received none of Sol's purchases, estimates, transcript, or evaluator results.

- Exact model: `gpt-5.6-luna`; reasoning: `high`.
- Scientific budget: 32; API ceiling: $3.
- Limits: 30 responses, 32,768 output tokens per response, 1,200 seconds.
- Streaming Responses API, standard service tier, `store=false`, sequential
  tool execution, reasoning summaries and opaque encrypted reasoning replay.
- No model substitution, retry, continuation, arbitrary Python execution, or
  extra paid episode.

Official documentation confirms
[Luna's supported settings](https://developers.openai.com/api/docs/models/gpt-5.6-luna).
The [standard short-context pricing table](https://developers.openai.com/api/docs/pricing)
gives $0.20/million uncached input, $0.02/million cached input, $0.25/million cache
writes, and $1.20/million output. Reservations conservatively use $0.25 for all
input and $1.20 for output, including the complete output-token allowance before
each call. The unchanged 256,000-input-token guard avoids long-context pricing.

The run took **82.032 seconds** and completed **15 responses**. Recorded usage:
94,202 input tokens, 5,769 output tokens, including 5,344 reasoning tokens. The
conservative API cost upper bound was **$0.03047330**, with no unsettled
reservations. This is not an invoice. For context, the earlier Sol run took
254.855 seconds with a $0.857335 cost upper bound; these are single-run timings
and conservative cost bounds, not controlled throughput measurements.

## Local artifacts and verification

- [Complete Luna transcript](../demos/planning/runs/resource_agent_v2/20260911T141328Z-live-c76209f003/transcript.md)
- [Luna and CPU-baseline report](../demos/planning/runs/resource_agent_v2/20260911T141328Z-live-c76209f003/report.md)
- [Complete raw run directory](../demos/planning/runs/resource_agent_v2/20260911T141328Z-live-c76209f003/)
- [Matched earlier Sol run](resource_planning_v2_32_credit_run.md)

Logs retain API-visible responses and returned reasoning summaries, not raw
internal reasoning. Encrypted replay items are opaque. Credentials and raw runs
remain untracked; private evaluator records were never supplied to the model.

**270 tests passed** (256 shared plus 14 planning-pilot), including five new
Luna tests covering selection, pricing, reservations, resume, complete offline
execution, and report regeneration. The offline CLI rehearsal completed 32
credits. All 265 pre-existing tests remain passing.

Post-run audits verified 53 source-file hashes, 2,354 contiguous events, all 15
exact request-history replays, all 11 purchased trajectories, submission scoring,
and the completed checkpoint. Luna's cost ledger was independently recalculated
from recorded token usage. Transcript, report, evaluation JSON, and event log
remained byte-identical after offline regeneration.

- Source-manifest hash: `f961082a95f453782e198e4d3bafc41d17ff67d56b165d610afdc222620184ea`
- Prompt hash: `7512cb102c2f556e795d794a96ff2ed60ac5e33ed405b8b9163f747a2da07109`
- Tool-schema hash: `e78d3daa1f2829965f2123ea6ca9eee17f253eb4cdc24a00bb52056ad301197f`
- Software: Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1, OpenAI SDK 2.54.0,
  httpx 0.28.1, budgeted-science 0.1.0.

Offline rehearsal from the repository root:

```powershell
.\.venv\Scripts\python.exe demos/planning/src/run_resource_agent.py --dry-run --model gpt-5.6-luna --harder --scientific-budget 32 --api-ceiling-usd 3.00 --require-full-budget
```

The executed live command used `--live` instead of `--dry-run`; running it again
requires fresh authorization. `--render RUN_DIR` regenerates saved reports
offline. Sol remains the default model. Explicit resume restores the saved
model and price assumptions and rejects changing models during an episode.
