# MMS verification: Luna/high results

Executed on 12 September 2026: **six live GPT-5.6 Luna episodes, all completed,
both verdicts correct on 6/6 studies**. The cases, numerical services, prices
and ten-credit limits were unchanged from the CPU pilot. No retries, replaced
cases, additional model runs or limit increases were used.

This is a working model demonstration, **not yet a challenging benchmark**.
The simple study-aware CPU rule also gets 6/6, using fewer scientific credits.

## Task and protocol

The [scientific protocol](mms_verification_protocol.md) uses a steady 2-D
advection-diffusion problem. Each study has two separately scored claims:

1. The originally reported point value is accurate within 2%.
2. The audited implementation passes its relevant manufactured-solution (MMS)
   diagnostic: both successive RMS convergence orders on grids 8/16/32 lie in
   the inclusive interval `[1.7,2.3]`.

The second criterion concerns these finite grids, not certified asymptotic
convergence. An implementation-order failure need not invalidate the original
value, and a passing implementation need not make a coarse study accurate.

Luna received the neutral report, physical configuration, original numerical
inputs, diagnostic definitions, tools and scoring contract. It did not receive
private reference answers, fault categories, baseline outcomes or a prescribed
audit sequence. Available actions were `run_study`, `run_mms`, `record`, `budget`
and `submit`. Purchased fields were freely retrievable. No arbitrary code
execution or additional numerical helper was introduced.

The [agent protocol](mms_luna_protocol.md) records high reasoning, 32,768 output
tokens per response, 30 responses/tool requests, a five-minute episode deadline
and a **$2 whole-batch API ceiling**. Conversations and scientific purchases
were independent across studies. Submission did not require spending the full
budget. Explanations were retained but not semantically graded.

## Six measured outcomes

Every row below had both verdicts correct. Categories are evaluator-side labels,
not descriptions shown to Luna. There were no abstentions, incomplete episodes,
false acceptances or false rejections.

| Development study | Value verdict | Order verdict | Scientific credits | Responses |
|---|---|---|---:|---:|
| Sound diffusion | ACCEPT | ACCEPT | 9.8166 | 7 |
| Correct mixed-BC code, coarse study | REJECT | ACCEPT | 9.8166 | 7 |
| Upwind advection, coarse study | REJECT | REJECT | 7.3287 | 8 |
| First-order Neumann boundary treatment | REJECT | REJECT | 9.8166 | 8 |
| Upwind advection, finer study | ACCEPT | REJECT | 9.8166 | 7 |
| Inactive upwind change in diffusion | ACCEPT | ACCEPT | 9.8166 | 7 |

Mean expenditure was **9.4020/10 scientific credits**; total was 56.4118 across
the six independent budgets. In particular, Luna correctly separated the
coarse-study value failure from the finer upwind case's order failure. These
verdicts are objectively scored; this does not establish that its explanation
or confidence was fully justified.

## Matched saved CPU comparisons

The existing ten-credit CPU results were verified and imported, not rerun
during the model batch. See the [CPU report](mms_verification_results.md) for
their definitions and original commissioning procedure.

| Method | Value correct | Order correct | Both correct | Mean credits |
|---|---:|---:|---:|---:|
| GPT-5.6 Luna, high | 6/6 | 6/6 | 6/6 | 9.4020 |
| Study-aware rule + independent study | 6/6 | 6/6 | 6/6 | 8.8166 |
| Study-aware rule with early order rejection | 6/6 | 6/6 | 6/6 | 6.9325 |
| Fixed diffusion diagnostic + independent study | 6/6 | 2/6 | 2/6 | 8.8166 |
| All diagnostics, fixed sequence | 0/6 | 5/6 | 0/6 | 7.6090 |
| Audited study refinement only | 6/6 | 0/6 | 0/6 | 4.1015 |

Lower CPU counts reflect abstentions, not wrong binary answers. Refinement-only
is a partial-task control that never attempts the order claim. The fixed full
suite cannot finish its sequence at ten credits; its earlier twenty-credit
comparison gets both answers correct on all six. None of these contrasts
establishes a need for sophisticated adaptive planning.

## API expenditure and durable records

The batch used 44 responses, 412,295 input tokens across repeated conversation
histories, and 27,414 output tokens including reasoning. The recorded standard
cached/uncached calculation gives a **$0.05320144 lower estimate**; conservative
accounting gives a **$0.13597055 upper bound**. These are accounting estimates,
not an invoice. There were no uncertain usage records or outstanding
reservations; the remaining batch allowance was $1.86402945. Per-episode elapsed
times were approximately 35-99 seconds, including API waiting and logging.

Local records (ignored by Git):

- [Aggregate report with all six transcript links](../demos/claim_verification/runs/20260912T192812Z-mms-luna-live-35f682c9b7/report.md).
- [Complete live batch directory](../demos/claim_verification/runs/20260912T192812Z-mms-luna-live-35f682c9b7/).
- [Frozen manifest and source hashes](../demos/claim_verification/runs/20260912T192812Z-mms-luna-live-35f682c9b7/manifest.json).
- [Machine-readable results and API usage](../demos/claim_verification/runs/20260912T192812Z-mms-luna-live-35f682c9b7/summary.json).
- [Retained scripted offline rehearsal](../demos/claim_verification/runs/20260912T192701Z-mms-luna-dry-run-6c173b4513/report.md).

Each episode retains the frozen prompt/schemas, outgoing requests, streaming
events, complete returned response items, reasoning summaries, opaque encrypted
reasoning items, chronological tool logs, numerical arrays, submissions and
private scoring. This is all available API-visible material, not raw internal
reasoning. The rehearsal used fake responses and spent no API money.

From the repository root, regenerate the saved report without contacting the
API or executing scientific tools:

```powershell
python -m budgeted_science.agents.mms_catalog --render demos/claim_verification/runs/20260912T192812Z-mms-luna-live-35f682c9b7
```

JSON/JSONL integrity hashes and saved scores/events are verified on replay.
The live source freeze matched through completion. After all six episodes,
a defensive one-line guard was added to the shared response parser for SDK
items with `content: null`, together with an offline regression test. This
condition did not occur in the live batch. The stored live source hashes
therefore identify the pre-guard runner, not a retroactively updated version;
no science changed and no samples were rerun.

## Verification and limitations

- The full 674-test shared regression suite and 14 planning-pilot tests passed.
- After the parser guard, all 13 MMS-agent tests and 42 shared API/runner tests
  passed again. Tests cover hidden-data separation, schemas, charge/reuse rules,
  deduplication, failure logging, history replay, reservations and offline replay.
- Only six development studies on three physical systems were evaluated, with
  an identical harmless control and one model episode per study. There is no
  held-out or repeated-sampling performance claim.
- The complete CPU rule's success was an explicit commissioning requirement,
  not an independently obtained generalization result. Public configuration
  makes selection of the relevant diagnostic straightforward.
- Both diagnostic families and refinement actions are prebuilt tools. This is
  not evidence of independent verifier construction, open-ended report auditing,
  physical validation, or reliable uncertainty assessment.
- Scientific prices are a declared grid-size proxy, not measured runtime or
  monetary cost. No efficient-stopping objective was evaluated.

The result supports a concise, executable toy illustration in the proposal.
It does not demonstrate an advantage over classical verification or a difficult
resource-constrained scientific investigation.
