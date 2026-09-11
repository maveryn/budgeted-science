# First Terra claim-verification episode

Date: September 11, 2026. One completed live episode; no retry or resume was
needed. The exact model was `gpt-5.6-terra`, with high reasoning.

## Outcome

| Method | Verdict | Correct verdict | Audit credits |
|---|---|---|---:|
| GPT-5.6 Terra, high | ACCEPT | Yes | 5 / 5 |
| Fixed two-check numerical verifier | ACCEPT | Yes | 5 / 5 |

The model tested the first study in the existing development-catalog order,
`study-13cc000ca7a7e1`. It was not chosen based on model performance. This is a
sound numerical study, not a consequential-defect test. The claim concerns the
maximum of species A on [0,8], with a 5% relative numerical-accuracy tolerance.

The printed original claim is **30.00513192**; the independently checked private
reference is **30.005229138136862**. The original claim's relative error is
**0.000324004%**, within tolerance. The evaluator scored ACCEPT on that original
claim, not on a replacement computed by the agent. Explanation correctness and
justified confidence were not graded.

## Observed workflow

The prompt supplied the report, artifact inventory, tool contracts and budgets,
without prescribing a checking sequence. Terra made seven tool requests:

1. Read the solver log, then the analysis artifact (two free requests).
2. Recompute the peak from the original stored samples (free).
3. Refine sampling on the original run (2 credits).
4. Refine integration on the sampling-refined run (3 credits).
5. Compare the three purchased/original runs (free).
6. Submit ACCEPT with evidence IDs and a numeric justification (free).

| Available run | Stored-sample peak |
|---|---:|
| Original | 30.005131922218126 |
| Sampling-refined | 30.00522354328215 |
| Sampling plus integration refinement | 30.005223541948737 |

The baseline used integration then sampling, with an independent five-credit
ledger. Both orders perform the combined numerical check; the model was not
given the baseline's actions or results. Two recognized explicit run-ID peak
citations matched their purchased records. That mechanical check does not grade
the rest of the explanation or prove evidence sufficiency.

## Settings, usage and records

- Scientific budget: 5; integration price 3 and sampling price 2. No full-budget
  requirement, spending penalty or early-stopping bonus.
- API ceiling: USD 3 cumulative; 30 responses and 30 tool requests maximum;
  32,768 output tokens per response; 20-minute active deadline.
- Streaming Responses API, standard service tier, high reasoning, store=false,
  sequential tool execution and requested reasoning summaries.
- Completed in **7 responses and 19.284 seconds** of recorded agent time,
  excluding the independent CPU comparison.
- Reported usage: **14,394 input tokens, 702 output tokens**, including **214
  reasoning output tokens**. Replayed/cached inputs remain part of input usage.
- Recorded cost bounds: **USD 0.0167604 to USD 0.0444090**, not an invoice.
  No unsettled request reservations remained. The upper bound conservatively
  prices all inputs at the cache-write rate. The ceiling was never increased.

All API-visible output is saved, including returned reasoning summaries and
opaque encrypted reasoning items. Raw internal reasoning is not exposed. The
credential was loaded only inside live execution; credentials and raw runs are
not tracked by Git.

Local evidence:

- [Complete run directory](../demos/claim_verification/runs/20260911T231112Z-live-82c4873b27/)
- [Readable transcript](../demos/claim_verification/runs/20260911T231112Z-live-82c4873b27/transcript.md)
- [Comparison and private evaluation](../demos/claim_verification/runs/20260911T231112Z-live-82c4873b27/report.md)
- [Frozen manifest and source hashes](../demos/claim_verification/runs/20260911T231112Z-live-82c4873b27/manifest.json)
- [Preflight inspection](../demos/claim_verification/runs/20260911T230918Z-verification-inspection-d636f0b85e/)
- [Scripted dry run, no paid calls](../demos/claim_verification/runs/20260911T230920Z-dry-run-464051eece/)

These raw directories are local and ignored. The curated report remains useful
without them, but exact transcripts are not included in a fresh checkout.

## Verification and reproduction

All **372 tests passed before live execution**: 358 root tests plus 14 planning
pilot tests. Fourteen new tests cover the adapter, public/private separation,
charging, cached retrieval, interruptions, unchanged-budget resume, independent
comparison, missing submission, cost limits and offline regeneration. Existing
tests continue to cover API history, credential redaction and spending ledgers.

The post-run audit confirmed all seven complete request/response pairs, exact
model/reasoning/limit settings, no evaluator fields in generation requests,
unchanged source and catalog hashes, and equality of the inspected and live
prompts/schemas. Offline regeneration reproduced the report, transcript and
evaluation byte-for-byte without numerical execution or credential access.

Software: Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1, OpenAI SDK 2.54.0,
HTTPX 0.28.1, budgeted-science 0.1.0. The run used the newly added adapter atop
repository checkpoint `afdc977`; the manifest pins the exact uncommitted source
bytes present at launch. No scientific implementation changed after the run.

| Recorded identity | SHA-256 / canonical digest |
|---|---|
| Source-hash mapping | `dbc4d115aa93d3900840d2ca5f3aca13cc332eb31078594dfc86a763bc551eb5` |
| Prompt | `8da2885572207c8384dc1031d3caae2f0171df7bb7d87d86c787563ee580c276` |
| Tool schemas | `53f9b3341e56cea5fd1faef3445b00ac804ee48842268b3bad2c7b1cd14ee0b9` |
| Development catalog | `a761b84be95282af425dee18949d718f17866dd094224f9826f82b9b0d0c7d19` |

Regenerate the saved result offline from the repository root:

~~~powershell
.\.venv\Scripts\python.exe -B -m budgeted_science.agents.verification_cli --render demos/claim_verification/runs/20260911T231112Z-live-82c4873b27
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -B -m unittest discover -s demos/planning/tests -q
~~~

See the [runner protocol](claim_verification_agent_protocol.md) for inspection,
dry-run, newly authorized live runs and explicit same-episode resume. Completed
submissions cannot be resumed into additional trials.

## What this establishes

This smoke test demonstrates an end-to-end model-controlled audit with paid
checks, a submitted verdict, objective scoring and complete recoverable records.
It does **not** estimate accuracy across the 30-case catalog, test rejection of
bad claims, or show an advantage over the fixed verifier. Both checks fit the
budget; their selection does not demonstrate difficult resource allocation.
The 30 studies also share only six development systems. Further evaluations
must report individual cases and these dependencies, not treat one successful
sound-study audit as general scientific verification ability.
