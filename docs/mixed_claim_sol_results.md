# Mixed-claim audit: Sol/high attempt at 32 credits

Executed September 12, 2026 (September 13 UTC). Exactly one live Sol/high
episode was attempted on the same frozen six-claim study as the
[completed Luna run](mixed_claim_audit_results.md). The study, claim order,
scientific prompt, tools, target, observations, 32-credit budget and 1/8/12
prices were verified identical. No numerical-science code or claim changed.

## Outcome: incomplete, no verdict submission

Sol used **31 of 32 scientific credits** before the API reservation guard
stopped the episode. It did not call `submit`. There is therefore **no verdict
accuracy result** for Sol, not six incorrect verdicts or six abstentions.
Its raw evaluation records zero correct/wrong/abstained and six incomplete
claims because no verdicts were supplied. No fallback answer was fabricated.

| Investigator | Outcome | Correct | Wrong | Abstained | Scientific credits |
|---|---|---:|---:|---:|---:|
| Fixed shared-evidence CPU baseline | Completed | 4/6 | 0 | 2 | 32/32 |
| Luna/high (earlier saved episode) | Completed | 5/6 | 1 | 0 | 27/32 |
| Sol/high | API ceiling before submission | Not scored | Not scored | Not scored | 31/32 |

The new preparation independently repeated the same CPU baseline. Its
verdicts, purchases and charges matched the saved Luna comparison; these
are duplicate checks of one deterministic control, not independent samples.
The CPU-only 52-credit diagnostic remains separate from this comparison.

## Why it stopped despite spending less than $1

- Cumulative measured-usage **conservative API cost upper bound: $0.346635**.
- Remaining API allowance: **$0.653365**; no uncertain charges or reservations.
- Next input count: **12,122 tokens**, reserving $0.060610 at $5/M input.
- Maximum next output: **32,768 tokens**, reserving $0.655360 at $20/M output.
- Required next-request reservation: **$0.715970**.
- Cumulative upper bound if that request were allowed: **$1.062605**, exceeding
  the unchanged **$1 ceiling**.

The eighth generation request was **not sent**. Input-token counting was
completed, but generation failed the pre-send reservation check. This is the
specified spending safeguard, not a model refusal, numerical failure, network
failure, or evidence that the claims are scientifically unsolvable. These
conservative costs are not invoices; the full $1 was not consumed.

No automatic restart, resume, cap increase or output-limit reduction was
performed. All partial evidence and API-visible logs are retained. The
current mixed-claim runner has inspection checkpoints, not live crash-resume
support. Continuing the same episode would require implementing resume and
explicit approval for revised cumulative API limits; a fresh run would be a
different sample, not a continuation.

## Scientific purchases

Sol first retrieved the supplied evidence for free, then purchased:

| Action | Parameters or measurement | Cost | Credits remaining |
|---|---|---:|---:|
| High simulation | Baseline (1, 0.08, 1.4) | 8 | 24 |
| High simulation | Intervention (1, 0.088, 1.4) | 8 | 16 |
| Target measurement | Prey x(4.5) | 12 | 4 |
| Low simulation | (0.8, 0.08, 1.06) | 1 | 3 |
| Low simulation | (0.9, 0.09, 1.2) | 1 | 2 |
| Low simulation | (1.0, 0.1, 1.2) | 1 | 1 |

This differs from Luna's simulation-only allocation and the classical
baseline's high-baseline-plus-two-measurements allocation. Without a final
submission, do not infer how Sol would have classified the claims or rank
its scientific accuracy against the completed investigators.

## Runtime and verification

- **7 responses / 7 tool requests**, 62.183 seconds.
- **57,831 input tokens**, **2,874 output tokens** including reasoning.
- Exact model **gpt-5.6-sol**, **high reasoning**, streaming Responses API,
  standard service tier, store=false, encrypted reasoning replay and sequential
  function execution. Limits remain 30 responses, 60 tool requests, 32,768
  output tokens/response, 20 minutes and $1 API cost ceiling.
- **66 targeted tests passed**: 24 mixed-claim/model-selection tests and 42
  reused API safety/logging tests. The full legacy suite was not rerun for this
  model-selection extension.

The initial offline fake counted every JSON byte as a token and prematurely
hit Sol's ceiling. Its completion rehearsal now uses explicitly synthetic
fixed usage; an additional test retains the inflated-input ceiling outcome.
This changed **only the offline fixture**. Live input counts still come from
the API endpoint, with unchanged reservations and prices. An unused earlier
preparation was retained; only one real Sol episode was launched.

All seven generation request bodies were checked for exact settings. The
chronological log is complete through the API-ceiling termination. There is
no eighth generation body. Offline regeneration reproduced transcript,
report and evaluation byte-for-byte without changing raw events or running
solvers/API calls. Luna's completed episode and curated report were preserved.

Sol's supported settings and prices were checked against
[official model documentation](https://developers.openai.com/api/docs/models/gpt-5.6-sol)
and [official pricing](https://developers.openai.com/api/docs/pricing).
Reservations use the cache-write-inclusive $5/M input bound and $20/M output.

Frozen source-manifest SHA-256:
`eeb2508811811e11de1b3b72226087c498aa45bd6b496270167486454adeb2ba`.
Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1, OpenAI SDK 2.54.0, HTTPX 0.28.1,
budgeted-science 0.1.0. Per-file hashes and configuration are in the manifest.

## Local artifacts and reproduction

- [Sol transcript](../demos/mixed_claim_audit/runs/20260913T024618Z-live-7c755f7e8c/transcript.md)
- [Generated report](../demos/mixed_claim_audit/runs/20260913T024618Z-live-7c755f7e8c/report.md)
- [Complete event log](../demos/mixed_claim_audit/runs/20260913T024618Z-live-7c755f7e8c/events.jsonl)
- [Frozen preparation](../demos/mixed_claim_audit/runs/20260913T024523Z-mixed-prepared-f163f0073d/manifest.json)
- [Independent CPU transcript](../demos/mixed_claim_audit/runs/20260913T024523Z-mixed-prepared-f163f0073d/cpu/20260913T024524Z-fixed-cpu-8d29f5e7b0/transcript.md)
- [Commands and launch safeguards](../demos/mixed_claim_audit/README.md#matched-sol-follow-up)

Raw logs and credentials remain local and untracked. No proposal documents
were edited and no changes were pushed.
