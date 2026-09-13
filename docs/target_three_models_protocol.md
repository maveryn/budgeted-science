# Three target claims: matched Sol/Terra extension

Add six independent episodes each for `gpt-5.6-sol` and `gpt-5.6-terra`, both
at **high** reasoning, to the [three-target-claim experiment](target_three_claims_protocol.md).
Import the six Luna attempts and CPU comparisons unchanged, including Luna's
incomplete attempt. Do not regenerate studies, rerun the CPU baseline, change
scientific tools, or replace previous results.

## Frozen comparison

Each episode has three shuffled claims about the unknown fixed predator-prey
target: joint parameter accuracy, integrated prey abundance, and late recovery.
Original reports, observations, noise, thresholds, private labels and tool
responses remain unchanged. Each model starts with **32 scientific credits**;
new low/high simulations cost **1/8**, and a scalar target measurement costs
**12**. Purchased evidence can support multiple claims.

Scoring remains +1 correct, -2 wrong, 0 abstain; missing submissions are separate.
There is no spending penalty or full-budget requirement. The six reused worlds
are three engineered development pairs, not independent random evaluation systems.

Retain case order. Sol runs first on cases 1, 3 and 5; Terra first on cases 2, 4
and 6. All 12 episodes are sequential with independent histories and ledgers.
Scientific prompts and schemas are identical between models. Relative to Luna,
only the disclosed API ceiling changes if the approved cap differs.

## Limits and approval

The prepared configuration proposes **$3 per episode**, **$18 per model**, and
**$36 maximum new API expenditure**. At this checkpoint the increase is awaiting
approval; no paid Sol/Terra episode has started. Preparation/rehearsal does not
authorize spending. If $1 is selected instead, create a new preparation with
`--api-ceiling 1.00` ($12 total); never edit a frozen manifest or transfer unused
allowances between episodes.

Other limits: 30 responses, 32,768 output tokens per response, 60 tool requests,
20-minute episode deadline. Preserve standard-tier streaming Responses API,
`store=false`, high reasoning, returned summaries and opaque encrypted replay.
Save all API-visible material; raw internal reasoning is not exposed.
Credentials are read only in explicit live mode and remain untracked.

Capabilities/pricing were checked on 2026-09-13 against official
[Sol documentation](https://developers.openai.com/api/docs/models/gpt-5.6-sol),
[Terra documentation](https://developers.openai.com/api/docs/models/gpt-5.6-terra)
and [standard pricing](https://developers.openai.com/api/docs/pricing#standard-pricing-data).
Existing conservative reservations use $5/M input and $20/M output for Sol,
$2.50/M input and $12/M output for Terra, including the full output allowance.
Refuse input above 256,000 tokens. These are spending bounds, not invoices.
Uncertain requests retain reservations and halt the campaign.

Exclusive campaign/slot attempt markers prevent automatic duplicate paid calls.
Expected incomplete outcomes remain recorded while untouched slots continue;
unexpected transport/accounting failures halt execution. No automatic retries,
model substitutions, live crash-resume, or cap increases.

## Verification and records

The targeted regression suite passed **149 tests** with no skips. A 12-slot
scripted rehearsal completed with exact paired payloads, frozen prompts/settings,
encrypted history replay, imported incomplete outcomes and offline regeneration.
Scripted abstentions and synthetic usage values are not model results; rehearsal
API expenditure was zero.

Frozen preparation, relative to the repository:
`demos/paired_claim_audit/runs/20260913T093320Z-target-three-models-prepared-e30c1fbe8c`.

- Original catalog hash: `086f913625f20a5c49eac56ad8cdafeec19fa2ef5468fef2d9d8b24fca7f1d8b`.
- Extension source hash: `55e96a285fd2f15316df571ec1a7234d82aedaca52f76cd7852011b54211ef65`.
- Rehearsal: `campaigns/20260913T093350Z-dry-run-f5ac22327c`.

Configuration, source/software provenance, payload/prompt/schema hashes,
imported-result hashes, attempt records, numerical artifacts, transcripts and
private evaluations remain in ignored unique directories.

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_target_three_models.py -v
.venv\Scripts\python.exe -m budgeted_science.agents.target_three_models prepare --api-ceiling 3.00
.venv\Scripts\python.exe -m budgeted_science.agents.target_three_models dry-run <prepared-directory>
# Only after approving the frozen cap; never repeat an attempted campaign.
.venv\Scripts\python.exe -m budgeted_science.agents.target_three_models live <prepared-directory>
.venv\Scripts\python.exe -m budgeted_science.agents.target_three_models render <campaign-directory>
.venv\Scripts\python.exe -m budgeted_science.agents.target_three_models render-episode <episode-directory>
```

Rendering reads saved records only, without API calls or scientific tools.
Existing science code, proposals, credentials and raw results are excluded from
this extension's checkpoint.
