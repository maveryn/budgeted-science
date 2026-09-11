# Logged GPT-5.6 Sol resource-planning evaluation

## Executed attempt: 2026-09-11

Exactly one live episode was attempted. It ended **incomplete** when the provider
reported `APIError: Our servers are currently overloaded. Please try again later.`
Generation 10 produced no completed response or usable usage record. The runner
did not retry, substitute a model, resume, or fabricate a final estimate.

GPT completed nine low-fidelity simulations, spending **9 of 40 credits**. It had
not purchased a high-fidelity simulation or additional target measurement, called
the fitting helper, or submitted parameters. This is an infrastructure-interrupted
attempt, not evidence that the model failed parameter recovery.

| Method | Outcome | Worst normalized parameter error | Credits | Low / high / measurement purchases |
|---|---|---:|---:|---|
| GPT-5.6 Sol, high | Incomplete: provider overload | No submission | 9 | 9 / 0 / 0 |
| Randomized fixed policy | Submitted; tolerance not met | 2.14827575 | 40 | 12 / 2 / 1 |
| Adaptive GP policy | Submitted; tolerance not met | 1.93331646 | 40 | 20 / 1 / 1 |

The success threshold is worst normalized error <= 1. The completed baseline
results cannot be ranked against an interrupted agent with no submission.
Elapsed time was 115.430 seconds for the agent, 0.109 seconds for the fixed policy,
and 6.985 seconds for the adaptive policy (descriptive, not matched-compute timing).

Nine completed API responses recorded 34,893 input tokens and 1,285 output tokens,
including 1,015 reasoning tokens. Their conservative cost upper bound is
**$0.200165**. The interrupted request retains its full **$0.691100** reservation;
the combined accounting bound is **$0.891265**, below the $2 ceiling. The interrupted
request's actual usage is unknown. These figures are not an invoice or a claim
that the reserved amount was charged.

Local, ignored run: `demos/planning/runs/resource_agent/20260911T102349Z-live-53548d68b4/`.
It contains the [transcript](../demos/planning/runs/resource_agent/20260911T102349Z-live-53548d68b4/transcript.md),
[comparison report](../demos/planning/runs/resource_agent/20260911T102349Z-live-53548d68b4/report.md),
and full raw records. These links resolve in this local checkout; raw runs are not
included in the repository or checkpoint.

Verification: **223 tests passed** (209 shared tests plus 14 planning-pilot tests;
all 199 pre-existing tests retained). The interrupted live transcript, report,
evaluation JSON, and raw event log were byte-identical after offline regeneration.
All 45 recorded source-file hashes matched the checkout after execution. Numerical
environment and baseline-policy source files were unchanged from the prior pilot.
The agent source-manifest hash is
`777baa356810c07cf6a7e5353e08fdefb20d605cc75f96cf09eaf66f0c82622c`;
prompt hash `5cddae22d065f8e0b8d8da5e95b969653cc1a821ce5587faacb9f758b0b2ee25`;
tool-schema hash `09895daa242954460341a0d685a552b7436dbfe42e6aa62704c1c96041917d4d`.
Software: Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1, OpenAI SDK 2.54.0,
httpx 0.28.1, budgeted-science 0.1.0.

## Protocol

This adapter evaluates one structured-tool agent on the existing predator-prey
resource-planning task. It does not replace Burgers, change the physical system,
retune either baseline, or revise the frozen 120-episode CPU pilot.

- Model: exactly `gpt-5.6-sol`, high reasoning, standard service tier.
- Scientific pool: 40 credits; low simulation 1, high simulation 8, new scalar
  target observation 12. Measurements are noiseless; simulation error is numerical.
- Agent starts with known initial conditions and free x/y observations at time 1,
  without the baselines' paid 12-credit initialization.
- Target: first frozen evaluation target by its original ordering. The instance
  identity and parameters are private harness configuration, not prompt inputs.
- Tools: `simulate_low`, `simulate_high`, `measure_target`, `get_status`,
  `evidence`, `compare_cached_candidates`, `fit_purchased`, and `submit`.
- Tool-wrapped measurements use the baselines' 16-time grid, 0.5 through 8.0.
  The underlying environment still supports continuous-time queries.
- `fit_purchased` uses the unchanged two-fidelity GP, 2,048 particles and seed 0.
  It needs one successful purchased simulation, returns the approximate posterior
  mean and diagnostics, and cannot acquire data or recommend actions. Numerical
  fitting is uncharged scientific analysis; runtime and full diagnostics are saved.
  Unchanged-evidence fits are cached. The estimates are not validated confidence.
- The actual submitted vector is scored by the maximum parameter error normalized
  by 10% of the corresponding true parameter. All three must pass. There is no
  savings reward, early-stopping bonus, or confidence score.
- Both unchanged baseline policies run independently on the same target with
  policy seed 0 and their own 40-credit budgets. They retain five-minute limits.
  Their outcomes and all private truth are withheld from the model.

This is a black-box tool-use experiment: equations and hidden constants are not
given to the agent or fitting helper. No shell, arbitrary Python, or Docker is
provided. This is trusted-process separation, not a security sandbox.

## API limits and durable records

At most 30 responses, each with up to 32,768 output tokens including reasoning,
within a 20-minute agent deadline. Baseline CPU time is outside that deadline.
The independent API ceiling is $2, enforced before generation using official
input-token counts and worst-case output reservations. Inputs above 256,000 tokens
are refused. The conservative reservation uses $5/million input tokens, covering
cache writes, and $20/million output tokens. Current base input pricing is
$4/million. Verified 2026-09-11 against the
[official model documentation](https://developers.openai.com/api/docs/models/gpt-5.6-sol).
Accounting is a conservative usage bound, not an invoice.

Streaming Responses calls use `store=false`, no automatic retries, no automatic
context compaction, and sequential tool calls. All replayable reasoning/message/
function items are preserved using the existing tested history serializer.
Requested reasoning summaries and opaque encrypted reasoning are stored; raw
internal reasoning is not exposed. A valid submission ends the run without another
paid generation. Missing usage or an uncertain stream failure retains the request
reservation and ends the episode. The runner does not silently retry or substitute
a model. A large maximum-output reservation can prevent another request while
actual charges are still below $2.

Each invocation creates a new ignored directory containing frozen prompts and
schemas, source hashes and dependency versions, request JSON bodies, complete
stream events/responses, a chronological JSONL log, full numerical artifacts,
purchased observations, fitting inputs/particle weights/diagnostics, private
reference data, baseline records, transcript, and evaluation report. Private
environment events never enter the model history. Credentials are read only in
live mode and are redacted from logs; neither secrets nor raw runs are tracked.
The existing Burgers entry point and report format remain compatible.

## Reproduction

From the repository root, with the editable package installed:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m unittest discover -s demos/planning/tests -v
.\.venv\Scripts\python.exe demos/planning/src/run_resource_agent.py --dry-run
```

The dry-run is a scripted fixture, not an LLM result. It neither reads credentials
nor contacts the API. Live mode requires the existing optional `agents` dependency
and explicit authorization for one episode:

```powershell
.\.venv\Scripts\python.exe demos/planning/src/run_resource_agent.py --live --api-key-file openaiapi.txt
```

The default run parent is `demos/planning/runs/resource_agent/`. Regenerate readable
artifacts from an existing directory without API access or scientific execution:

```powershell
.\.venv\Scripts\python.exe demos/planning/src/run_resource_agent.py --render demos/planning/runs/resource_agent/<run_id>
```

## Interpretation limits

One preselected instance cannot establish a model ranking, general planning
ability, or an adaptive-allocation advantage. The model can use the same numerical
estimator as the baselines, but controls its own initialization and acquisitions
and need not submit the estimator's answer. API latency and uncharged analysis
make runtime a descriptive quantity, not a matched compute comparison. This
prototype tests fixed-price resource allocation, not unexpected costs, reliable
confidence, efficient stopping, or structural simulation-target mismatch.

Incomplete outcomes must remain incomplete. Neither a fallback estimate nor a
replacement live run should be generated automatically.
