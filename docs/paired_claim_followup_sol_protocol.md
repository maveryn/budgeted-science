# Matched Sol/high evaluation: ready for live execution

The separate Sol adapter preserves the existing Luna implementation, six frozen
v2 studies, seven tool schemas, scientific accounting and evaluator. It imports
Luna's completed records and CPU comparisons without rerunning or overwriting
them. No new scientific cases or proposal edits are included.

## Configuration

- Exact model `gpt-5.6-sol`, high reasoning; one episode for each of the six studies.
- 32 scientific credits per episode, initially unspent; low/high simulations
  cost 1/8 and target scalar measurements cost 12.
- Utility +1 correct, -2 wrong, 0 abstain; raw counts and expenditure retained.
- 30 model responses, 60 tool requests, 32,768 output tokens per response,
  20-minute episode deadline. No forced initialization or full-spend requirement.
- API cap selected at preparation: $1 per episode ($6 total) or, with explicit
  user approval, $3 per episode ($18 total). No transfer of unused allowances.

The public scientific prompts and tool schemas match Luna exactly. The only
possible prompt difference is the disclosed API-dollar ceiling. Target identities,
seeds, references, labels, Luna outcomes and CPU outcomes remain harness-side.
Each episode has an independent conversation, purchase history and API ledger.

Official documentation checked on 2026-09-13 confirms high reasoning, streaming
and function calling. Sol standard input is $4, cached input $0.40, cache writes
$5, and output $20 per million tokens. The existing spending ledger reserves
$5 per million input tokens and $20 per million output tokens, including the
full output allowance. Thus 1,000 input tokens plus the 32,768-token allowance
requires a $0.66036 reservation, even if eventual usage is much lower. This is
why a $1 ceiling may interrupt an otherwise affordable multi-turn investigation.
Sources: [model](https://developers.openai.com/api/docs/models/gpt-5.6-sol),
[pricing](https://developers.openai.com/api/docs/pricing#standard-pricing-data).

## Commands

```powershell
.venv\Scripts\python.exe -m budgeted_science.agents.followup_claim_sol prepare --api-ceiling 3.00
.venv\Scripts\python.exe -m budgeted_science.agents.followup_claim_sol dry-run <prepared-directory>
# Requires explicit authorization for this spending ceiling:
.venv\Scripts\python.exe -m budgeted_science.agents.followup_claim_sol live <prepared-directory>
.venv\Scripts\python.exe -m budgeted_science.agents.followup_claim_sol render <campaign-directory>
.venv\Scripts\python.exe -m budgeted_science.agents.followup_claim_sol render-episode <episode-directory>
```

Use `--api-ceiling 1.00` to prepare the lower-cap alternative. A prepared campaign
cannot have its cap changed at launch. `prepare`, `dry-run`, tests and rendering
do not open credentials or make API calls. Live mode privately loads the existing
ignored credential file. Exclusive attempt markers prevent launching the same
prepared campaign twice; each slot is durably marked before its attempt. Expected
episode limits are retained as outcomes while untouched slots proceed; transport,
authentication or accounting failures halt the campaign for inspection. There
are no automatic retries, substitutions, ceiling increases or crash-resume.

All API-visible requests, streaming events, responses, returned reasoning
summaries, opaque encrypted reasoning items, exact tool results, numerical
artifacts and private evaluations are preserved locally. Raw internal reasoning
is unavailable. Regeneration uses only saved logs and snapshots. Raw records
and credentials stay untracked. The matched report links the unchanged Luna
transcripts alongside Sol outcomes and imported CPU results.

## Offline verification and prepared artifacts

**150 targeted tests ran successfully, with one optional skip**, including seven
new Sol-adapter tests. They cover matched prompts and schemas, independent initial
budgets, exact model and pricing reservations, snapshot tampering, duplicate-launch
protection, interrupted-stream preservation and repeatable offline rendering.
No full historical-repository test run is claimed.

The six-study rehearsal completed with scripted all-abstain submissions. These
are transport fixtures, not Sol performance results; API expenditure was zero.

- Prepared proposed $3-cap campaign:
  `demos/paired_claim_audit/runs/20260913T055416Z-followup-sol-prepared-893986f50d`
- Offline rehearsal:
  `campaigns/20260913T055439Z-dry-run-1f7a8fae7e` under that prepared directory.
- Imported Luna campaign:
  `demos/paired_claim_audit/runs/20260913T051751Z-followup-luna-prepared-db46c28d52/campaigns/20260913T051840Z-live-e24616a723`

At this checkpoint **no paid Sol episode has been launched**. The proposed
$3-per-episode cap is pending user approval. The scientific settings are not
pending redesign. Once authorized, use the frozen preparation above rather
than generating another copy or rerunning Luna.

The six engineered development studies and the CPU two-fit assumption retain
the limitations documented in the [Luna results](paired_claim_followup_luna_results.md).
Any future comparison must distinguish scientific performance from API-limit
interruptions and must not present six paired studies as independent random systems.
