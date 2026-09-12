# Luna/high on the frozen transport catalog

Evaluate the twelve existing development claims in saved order, once each.
Do not regenerate cases, rerun CPU baselines, screen results, or automatically
retry an attempted episode. The scientific implementation from the CPU pilot
remains unchanged; a separate adapter exposes its ordinary tools to the existing
logged Responses runner.

| Setting | Value |
|---|---|
| Exact model | gpt-5.6-luna |
| Reasoning | high |
| Scientific budget | 4 work-proxy credits per independent episode |
| Claim tolerance | 3% relative numerical error |
| API limit | $2 for the entire sequential batch, not per case |
| Model limits | 30 responses, 32,768 output tokens per response including reasoning |
| Other limits | 30 tool requests and 20 minutes per episode |

The source catalog is
`20260912T054409Z-transport-cpu-b5aefbda0e`. Its twelve claims share three
physical systems and nine original numerical studies. The saved CPU comparisons
are imported and checked against the literal claim evaluations; all source,
catalog and comparison-file hashes are recorded. These are development cases,
not a new held-out benchmark.

## Public task

Luna receives the original report, physical coefficients, equation, initial and
boundary conditions, sensor/threshold, numerical settings, scoring rule, costs
and resource limits. Reference values, truth labels, selection rules and CPU
outcomes are excluded. Physical coefficients were already public in the CPU
task; the PDE admits cheap analytic analysis, which is disclosed. Arbitrary
code execution and external tools are unavailable.

Tools: `describe`, `quote`, `run_verification`, `inspect_existing_run`,
`recompute_qoi`, `compare_runs`, `budget`, and `submit`. Function schemas are
strictly validated before execution. Luna chooses its own workflow; neither
the balanced CPU configuration nor a refinement sequence is prescribed.

The first valid ACCEPT/REJECT/ABSTAIN ends the episode. Original-claim accuracy
is scored against the saved private reference. Explanations are saved without
semantic grading; abstention and incomplete attempts are not correct binary
verdicts. There is no full-budget requirement, spending penalty or saving bonus.

## Logs and API safeguards

Reuse streaming Responses, standard service tier, `store=false`, high reasoning
with requested summaries, opaque encrypted-reasoning replay, sequential calls,
disabled automatic retries, complete history and no context truncation. Preserve
every available API request, stream event, complete response, usage record,
tool request/result, numerical artifact, submission and evaluation. Raw internal
reasoning is not available. Prompts and schemas are frozen before paid requests.

Official [Luna documentation](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
was checked on 2026-09-12: $0.20/M input, $0.02/M cached input, $1.20/M output,
and 1.25x input pricing for cache writes. The existing conservative ledger
reserves $0.25/M input and $1.20/M maximum output after obtaining an API input
token count. It rejects input above 256,000 tokens. These are accounting bounds,
not invoices. The OpenAI Docs guidance was used to verify settings and pricing.

A slot durably reserves the remaining whole-batch allowance before launching.
Only unused allowance from a finalized episode is released for the next case;
unknown usage remains committed. A failed unfinalized launch retains its full
reservation. Episodes and conversation histories are independent. The API
allowance can shrink between cases, but the scientific budget remains four.

Invalid/unaffordable scientific requests are recoverable; exhausted credits
still permit free retrieval and submission. Duplicate call IDs cannot repeat
purchases. Model/API/request/deadline limits create explicit incomplete outcomes.
Ordinary completed errors remain in the denominator; authentication, provenance
or accounting problems halt the batch. No substitution, cap increase, or retry.

The existing credential file is read privately only in live mode. Authorization
headers and keys are not logged. Raw runs stay local and Git-ignored. Inspection
checkpoints are saved, but no standalone resume is provided: it must not bypass
the shared batch ledger. Offline rendering executes neither solvers nor APIs.

## Commands

```powershell
# No credentials or paid calls; predetermined ACCEPT fixtures, not performance.
.\.venv\Scripts\python.exe -B -m budgeted_science.agents.transport_catalog --dry-run

# Run only with explicit user authorization; always creates a NEW batch.
.\.venv\Scripts\python.exe -B -m budgeted_science.agents.transport_catalog --live

# Regenerate a campaign or episode from its saved records only.
.\.venv\Scripts\python.exe -B -m budgeted_science.agents.transport_catalog --render PATH
```

The completed twelve-case preflight rehearsal is
`20260912T060327Z-luna-transport-dry-run-04af288f21`. Its six correct ACCEPT
fixtures are not Luna results. The frozen CPU result remains balanced 12/12,
space-focused 12/12, time-focused 9/12, output-focused 12/12, random 12/12.
Even a perfect Luna run would not establish an adaptive-auditing advantage.
