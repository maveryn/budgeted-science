# First planning-agent runner

Implemented and checked offline on 2026-09-10. No paid model evaluation has been
run for this milestone. The scripted dry-run checks the runner, not GPT-5.6 Sol's
scientific planning. The numerical foundation and allocation pilot are unchanged.

## Frozen first-run settings

| Setting | Value |
| --- | --- |
| Model / reasoning | `gpt-5.6-sol` / `high`, no substitution |
| Scientific budget | 20 shared credits |
| Sensor-record price / noise | 2 credits / independent Gaussian standard deviation 0.01 |
| Model API ceiling | $2, separate from scientific credits |
| Limits | 30 attempted generations, 8,192 output tokens per generation including reasoning, 20-minute episode deadline |
| API | Streaming Responses, standard (`default`) tier, `store=false`, `truncation=disabled`, no parallel tool calls or automatic retries |

The fixed target and noise seed are private harness configuration, recorded in a
separately marked manifest field, never the prompt. These are first-run choices,
not a calibrated benchmark budget or task distribution. Local source files and
raw reports contain evaluator information and must not become agent tools.

The scientific task uses the existing dimensionless periodic viscous-Burgers
system. The agent must submit the actual 16-value final forecast profile; scoring
does not replace it with an exact forecast from an estimated parameter.

## Reproduce

Use a Python 3.10+ virtual environment from the repository root. Ordinary
numerical work and the dry-run do not require the optional API SDK:

```powershell
python -m pip install -e .
python -m unittest discover -s tests -v
python -m unittest discover -s demos/planning/tests -v
python demos/planning/src/run_agent.py --dry-run
```

Install the optional integration only if needed:

```powershell
python -m pip install -e '.[agents]'
```

After inspecting the dry-run's `prompts.json` and `tools.json`, explicitly authorize
one paid episode with:

```powershell
python demos/planning/src/run_agent.py --live --api-key-file openaiapi.txt
```

`--live` performs one episode, not an automatic experiment loop. It returns exit
code 2 for an incomplete outcome. Inspect that run before deciding whether to
authorize another; the runner does not retry an episode. Model/account access and
the token-counting endpoint have not been verified with the user's credentials.
An inaccessible model or unavailable counter ends the attempt without substitution.

The key file is read only in live mode. Use one plain key or a single
`OPENAI_API_KEY="..."` assignment. Ambiguous/multiple-key files are rejected
without echoing them. Do not put credentials in a command-line argument value.
The root credential file and default run directory are already ignored by Git.

Offline regeneration needs neither credentials, the SDK, nor scientific tools:

```powershell
python demos/planning/src/run_agent.py --render demos/planning/runs/<run_id>
```

This replaces only derived transcript/report/evaluation artifacts in the selected
run. It does not replay tools, repeat API requests, resume a live run, or alter
the authoritative event log. All new executions receive unique directories;
earlier runs are never overwritten or automatically removed.

## Agent interface and separation

The frozen prompt states the equation, initial conditions, unknown-parameter
range, observation menu/noise, cost proxy, numerical method, reuse rules, limits,
forecast positions and actual-profile score. It does not prescribe an acquisition,
fit or refinement sequence, reveal the fixed policy, or require a long written plan.

- `observe(sensor_id, replicates)`: paid new five-time calibration records.
- `record(record_id)`: free retrieval of a purchased observation.
- `simulate(viscosity, resolution, protocol)`: candidate numerical computation.
- `fit(record_ids, resolution, max_evaluations)`: bounded fitting through metered
  candidate solves; best completed fit survives interruption.
- `budget()`: free scientific-ledger inspection.
- `simulation_record(result_id)`: free complete numerical-result retrieval.
- `submit(profile)`: first valid 16-value submission ends the episode immediately.

Every action returns the current scientific budget. Invalid requests are uncharged;
partial attempted solver work is charged. Scientific exhaustion does not disable
free retrieval or submission. Repeated call IDs cannot purchase another trial;
distinct observation calls represent distinct paid trials. A reused ID with altered
arguments is rejected. Calls are executed sequentially, even if several arrive.

Compact calibration responses contain sensor predictions; compact forecast
responses contain the 16 requested values. Full fields, recording times, grids,
status, work, charges and timing are saved separately. All fit-internal calls and
cache reuse appear in the chronological log, not automatically in agent context.
There is no code execution, shell, reference tool, Docker, GPU or trained model bank.

## Local audit artifacts

Default location: `demos/planning/runs/<UTC timestamp>-<mode>-<unique suffix>/`.

| Artifact | Contents |
| --- | --- |
| `manifest.json` | Public settings, marked private instance, API policy, dependency versions, source/prompt/schema hashes, Git HEAD, timestamps, termination |
| `prompts.json`, `tools.json` | Exact frozen initial messages and tool definitions |
| `api/` | Each input-token-count request/response and generation request/full response |
| `events.jsonl` | Ordered, append-only events: API stream chunks, IDs, tool arguments/results, numerical activity, budgets, errors, final evaluation |
| `numerical/`, `observations/` | Complete purchased numerical outputs/observations, separated by agent and fixed-policy role |
| `transcript.md` | Prompts, assistant text, available reasoning summaries, tool requests, exact tool-result payloads, links to full arrays |
| `evaluation.json`, `report.md` | Submitted/reference profiles, normalized RMSE, activity spending, API usage/bounds, termination and paired fixed-policy result |
| `fixed_policy_evaluation.json` | Independently budgeted CPU comparison |

Requests are persisted before sending. Events are flushed on arrival; artifact
writes and closed logs are synced. A severed stream keeps received events and its
unsettled cost reservation. A torn final JSONL line can be ignored during offline
rendering without editing the original log; middle-log corruption is reported.
Forcible process/power loss can prevent finalization; offline reports then explicitly
state that no finalized score was recorded. This is not live crash-resume.

Returned reasoning summaries and all replayable output items, including opaque
encrypted reasoning and assistant phase, are preserved in the conversation.
Nothing is automatically compacted. Raw internal reasoning is not exposed by
OpenAI. The transcript distinguishes saved tool results from those included in an
attempted subsequent request. No extra generation is purchased after submission.
API-visible errors are scrubbed; authorization headers, environment dumps, keys and
SDK client objects are never archived. Treat all raw logs as private and review
before sharing, even though they are untracked.

## API spending policy

Before each generation, the official Responses input-token-count endpoint counts
the complete input and tool context. Requests above 256,000 input tokens are
refused. The runner reserves `input_tokens * $5/M + 8192 * $20/M` before sending;
if the remaining allowance cannot cover it, generation does not start. This is
separate from the 20-credit scientific ledger.

The input upper rate includes the standard short-context cache-write premium;
output includes reasoning. After a response, provider usage produces a conservative
upper bound and a lower standard-price estimate using reported cached tokens.
These are not invoices: cache-write details are not fully disambiguated by usage.
Missing/invalid usage or a network failure retains the reservation and ends the
episode. A counter/usage inconsistency is recorded and stops further generation;
it is never concealed by clamping reported usage. No application can override an
incorrect provider count or future tariff change; recheck the documented rates
before later runs. This runner uses the verified 2026-09-10 tariff, not dynamic pricing.

Refusal, output truncation, deadline, response limit, API ceiling, unavailable
accounting, network failure and ending without submission are incomplete outcomes.
No fallback profile is fabricated. CPU tools are bounded by the scientific ledger;
the overall deadline is enforced at tool boundaries and during network awaits.

## CPU comparison and interpretation

The paired policy buys one sensor-2 record, fits at grid 32 with at most 16
predictor evaluations, forecasts at grid 64, and submits that actual profile.
It has its own 20-credit ledger and the same target/noise stream. It is a simple
comparison point, not an optimal or adaptive baseline. Its results never enter
agent context.

For the selected private instance, the CPU policy's normalized forecast RMSE is
**0.03445358599**, with **4.449612403** credits spent: 2 on the observation and
2.449612403 on computation. The fake model deliberately follows that same policy,
so its matching result only establishes end-to-end wiring. No evidence of LLM
success, adaptive allocation benefit or model-discrepancy correction follows.
Fast Cole-Hopf computation is possible for this restricted family; a later
coding-enabled benchmark must address such lawful analytic shortcuts.

## Verification and sources

The offline suite exercises request serialization through the real SDK with an
in-memory mock HTTP transport; no request leaves the process. It also covers full
history/reasoning preservation, interrupted streams, regeneration, synthetic-secret
redaction, deduplication, free retrieval, compact/full numerical agreement,
fit-internal logging, budget errors/reservations, usage failures, output limits,
deadline/refusal/no-submission outcomes, actual-profile scoring and paired state.
Verification passed: **41 runner tests + 40 original foundation tests + 12
allocation-pilot tests = 93 tests**. The SDK mock-transport test ran (was not
skipped). The final dry-run submitted successfully, and offline regeneration
preserved its authoritative event log. Python compilation checks also passed.

Tested environment: Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1, OpenAI 2.54.0,
HTTPX 0.28.1. The existing local virtual environment inherited system packages;
an incomplete system HTTPX installation was bypassed with a local virtual-environment
installation. No system packages or credentials were changed. A fresh isolated
virtual environment remains the documented installation path.

Official documentation guided the model settings, encrypted-history preservation,
stream logging and conservative spending accounting:

- [GPT-5.6 Sol model and pricing](https://developers.openai.com/api/docs/models/gpt-5.6-sol)
- [Reasoning summaries and state](https://developers.openai.com/api/docs/guides/reasoning#reasoning-summaries)
- [Streaming Responses](https://developers.openai.com/api/docs/guides/streaming-responses)
- [Responses input-token counter](https://developers.openai.com/api/reference/resources/responses/subresources/input_tokens/methods/count)

The tested integration uses OpenAI Python 2.54.0; the optional dependency requires
at least that version. Each run records its actual package versions and source
hashes. Numerical-only installation remains independent of the SDK.
