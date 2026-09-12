# Luna/high evaluation of the frozen MMS toy

This adds a model adapter to the existing
[CPU MMS protocol](mms_verification_protocol.md), without changing its cases,
numerics, prices, tools or truth criteria. The user authorized six live episodes,
one per existing study, after offline verification. No other model is included.

## Frozen evaluation

- Model: `gpt-5.6-luna`; reasoning effort: `high`.
- Six independent episodes, in the saved catalog order, fresh conversations.
- Ten scientific credits per episode; all original reuse/pricing rules remain.
- Thirty model responses, thirty tool requests, 32,768 output tokens per response
  including reasoning. Five-minute episode deadline, matching the toy's existing
  execution limit.
- **$2 for the entire batch**, not $2 multiplied by six. Each episode receives
  at most the batch remainder. Outstanding/uncertain calls retain reservations.
- No automatic retry, resubmission, case replacement, model substitution or
  limit increase. A failed or incomplete attempt remains part of reporting.

The prompt provides the neutral report, physical coefficients/boundaries,
original numerical inputs, diagnostic definitions, price schedule and scoring
contract. It does not provide the study-aware CPU rule, a preferred diagnostic,
an action sequence, case category, exact study solution or baseline outcome.
The audited kernel's finite-grid order is the claim under test; independent
kernel computations do not measure that implementation's order.

Actions are `run_study`, `run_mms`, `record`, `budget`, and `submit`. Full original
and purchased fields are freely retrievable. Ordinary solve responses contain
compact numerical summaries with links by record ID. Diagnostic exact errors
are public; original-study reference errors stay evaluator-side. No Python,
shell, browser, code inspection, LLM judge or additional scientific helper is
introduced.

## Scoring and comparisons

The model submits separate ACCEPT/REJECT/ABSTAIN verdicts for the original
point-value claim and finite-grid order claim. Both-correct is reported alongside
the two component scores. Abstention is completed but not a correct binary
verdict. No savings bonus, spending penalty or full-budget requirement applies.
Explanations are retained without semantic grading.

The five saved 10-credit CPU comparisons are imported and verified, not rerun.
Source hashes, catalog and artifact checksums, episode events, purchases and
scores are checked before importing. CPU results are never put into model
context. Six development studies share three physical systems, including an
identical harmless control. This is an exploratory model demonstration, not
held-out benchmark performance. The complete CPU rule's success was deliberately
commissioned, not independently discovered in this evaluation.

## API and durable records

The existing Responses runner supplies streaming, `store=false`, standard
service tier, disabled parallel tool calls, full untruncated history replay,
requested reasoning summaries and opaque encrypted reasoning items. Logs contain
all returned API-visible material, **not raw internal reasoning**. Each request
is saved before sending, and streaming events are flushed as received.

[Official Luna documentation](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
confirms high reasoning, streaming and function calling.
[Official pricing](https://developers.openai.com/api/docs/pricing), rechecked
12 September 2026, is $0.20/M uncached input, $0.02/M cached input,
$0.25/M cache writes and $1.20/M output for standard short context. The runner
reserves $0.25/M input plus the entire output allowance before each generation,
using the API input-token counter. It refuses input over 256,000 tokens.
Scientific credits and API dollars have independent ledgers.

Only explicit live mode reads the existing `openaiapi.txt` privately. No key,
authorization header or client object is printed or serialized. Existing
credential redaction and uncertain-billing handling remain unchanged.

Each batch has a unique ignored directory under `demos/claim_verification/runs/`:
frozen sources/configuration, slot reservations, copied private catalog, imported
CPU comparisons, per-episode API requests/responses, stream events, actions,
numerical artifacts, inspection checkpoints, prompts, transcripts, evaluations,
and aggregate reports. Source hashes are checked between episodes and at batch
completion. Raw JSON/JSONL files are sealed with hashes; offline replay checks
saved scores/events and requires no tools or API access. The checkpoints are
for inspection; this adapter does not implement live crash-resume. No batch is
automatically restarted.

```powershell
python -m unittest discover -s tests -p test_mms_agent.py -v
python -m budgeted_science.agents.mms_catalog --dry-run
python -m budgeted_science.agents.mms_catalog --live
python -m budgeted_science.agents.mms_catalog --render <saved-batch-directory>
```

Dry-run uses scripted purchases and abstentions. Its displayed token/cost ledger
is synthetic; real API expenditure is zero. Tests generate their own CPU fixture
and do not require saved local runs, credentials or an installed OpenAI SDK.
