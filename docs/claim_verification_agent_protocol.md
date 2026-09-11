# First verification-agent episode

The first requested model is `gpt-5.6-terra` with high reasoning. This is one
episode on the first case in the original development catalog, not a 30-case
model evaluation. No case is selected for a favorable model result.

## Frozen settings

- Five audit credits; integration refinement costs 3, sampling refinement 2.
- Submission may occur at any spend; no full-budget requirement or savings bonus.
- Cumulative API ceiling: USD 3; 30 model responses; 30 tool requests.
- Maximum 32,768 output tokens per response, including reasoning.
- Twenty-minute active agent deadline, excluding the independent CPU comparison.
- Responses API, standard service tier, streaming, high reasoning, store=false.
- Sequential function calls; no shell/Python, browser, or reference-query tool.

The model receives the original report, public artifact inventory, goal,
verdict meanings, costs, limits and tool contracts. It is not given parameters,
reference results, generation categories, labels or baseline outcomes. The
prompt does not prescribe the fixed baseline's action sequence.

The fixed two-check comparison runs independently with its own five-credit
ledger. The evaluator scores the model's actual original-claim verdict.
Abstention is completed but not correct; incomplete attempts remain incomplete.
Evidence IDs and recognized numeric citations are checked mechanically, not by
an LLM judge. No explanation-correctness or justified-confidence score is claimed.

## Commands

From the repository root:

~~~powershell
.\.venv\Scripts\python.exe -m budgeted_science.agents.verification_cli --inspect --model gpt-5.6-terra
.\.venv\Scripts\python.exe -m budgeted_science.agents.verification_cli --dry-run --model gpt-5.6-terra
.\.venv\Scripts\python.exe -m budgeted_science.agents.verification_cli --live --model gpt-5.6-terra
.\.venv\Scripts\python.exe -m budgeted_science.agents.verification_cli --render PATH_TO_RUN
.\.venv\Scripts\python.exe -m budgeted_science.agents.verification_cli --live --resume PATH_TO_RUN
~~~

The demo wrapper `demos/claim_verification/src/run_agent.py` accepts the same
arguments. Paid execution requires explicit user authorization and `--live`.
Only live execution reads the existing credential file. Inspect/dry-run/render
do not need credentials or contact the model.

## Preservation, accounting and resume

Every attempt creates a unique ignored run directory. Freeze prompts and tool
schemas before generation. Retain raw requests, stream events, full responses,
tool outputs, purchased numerical artifacts, checkpoint state, private scoring
and readable transcripts. Returned reasoning summaries and opaque encrypted
reasoning items are retained; raw internal thoughts are not exposed.

Reserve the maximum request cost before sending it. Terra standard short-context
rates were checked on September 11, 2026: input USD 2/million, cache writes 2.5,
output 12. Use the conservative 2.5/12 reservation and reject input above 256,000
tokens. Missing usage or an uncertain network failure retains its reservation.
No automatic generation retry, limit increase or model substitution is allowed.
[Official pricing](https://developers.openai.com/api/docs/pricing)

Explicit resume restores the same instance, purchased runs, artifacts, remaining
credits, call-ID deduplication state, conversation, cumulative API usage,
uncertain reservations, response count and active-time limit. It is the same
sample, not a new trial. It cannot reset the budget or repurchase old checks.
An exclusive parent marker prevents duplicate continuations.

Only durably finalized, unsubmitted attempts with consistent checkpoints can
resume. Changed source/schema/pricing, torn logs, uncheckpointed tool execution,
pending completed-response calls, active attempts and already-submitted episodes
are rejected for manual review. This is not arbitrary crash recovery.

Terra supports high reasoning, streaming and function calling.
[Official model documentation](https://developers.openai.com/api/docs/models/gpt-5.6-terra)
