# Luna evaluation of recalibrated incremental verification

## Execution status

Implementation and offline verification are complete: **417 tests passed**
(403 root and 14 planning-pilot), and all 35 scripted rehearsal episodes
completed. The rehearsal is saved at
`demos/claim_verification/runs/20260912T030543Z-luna-incremental-dry-run-2cabf0fe0f/`.
Its predetermined ACCEPT responses are not model-performance results.

The initial live launch was blocked before any process or API calls. The user
subsequently authorized all 35 cases with a reduced **$2 whole-batch ceiling**.
The ceiling is not an expected cost. Live results will be reported separately;
do not describe scripted rehearsals as Luna performance.

## Frozen task and model

Evaluate all **35 generated fresh studies** from the
[recalibrated CPU pilot](claim_verification_recalibrated_results.md), in their
saved order. These are variants on six fresh systems, not 35 independent
systems. The generator's missing mixed-invalid slot remains missing; it is
not replaced. Earlier 30-study model runs are different tasks and stay separate.

| Setting | Value |
|---|---|
| Model | `gpt-5.6-luna`, no substitution |
| Reasoning | High |
| Scientific budget | 8 credits per independent episode |
| Integration refinement | Halve the selected Euler timestep; cost 3 |
| Sampling refinement | Bisect selected output intervals; cost 2 |
| Claim | Original reported population maximum accurate within 5% |
| API ceiling | $2 total across the entire 35-case batch, not per case |
| Other limits | 30 responses, 30 tool requests, 32,768 output tokens per response, 20 minutes per episode |

Luna supports high reasoning, streaming and function calling. Its documented
short-context prices are $0.20/M input, $0.02/M cached input and $1.20/M output;
cache writes cost 1.25 times ordinary input. The existing ledger conservatively
reserves $0.25/M input plus $1.20/M output and refuses input above 256,000 tokens.
Settings and prices were checked against the
[official Luna documentation](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
on 2026-09-12 UTC. Cost bounds are not invoices.

## Agent-facing contract

The prompt contains the original report, artifact inventory, public tool
semantics, costs and scoring rules. It does not reveal parameters, system seed,
reference peaks, case categories, commissioning rules or baseline outcomes.
Luna chooses its own workflow; no acquisition sequence or extrapolation formula
is prescribed. There is no full-budget requirement or savings bonus.

Tools: artifact list/read, stored-sample peak recomputation, incremental
integration/sampling checks, run comparison, budget, and final submission.
There is no reference query, automatic extrapolation helper, Python execution,
new target measurement or parameter-change action. Inspection/retrieval and
submission remain free. Reusing a purchased configuration is free; new-episode
cache hits still incur the normal scientific charge.

The eight-credit adapter is separate from the original five-credit task. Its
checks do not switch to DOP853 or instantly return densely sampled ground truth.
Existing model commands retain their original semantics.

## Comparison and interpretation

Reuse the four saved CPU comparisons for the exact same studies; do not rerun
or expose them to Luna. Validate their case identities and numerical evaluations,
then hash and archive the imported snapshots. Per-episode reports show saved
fixed IIS with extrapolation; campaign reports show all four methods.

CPU policies use their implemented extrapolation calculation, whereas Luna
reasons over returned records without arbitrary code execution. This is a
comparison of complete methods, not a controlled attribution to planning or
allocation alone. The evaluator scores Luna's actual ACCEPT/REJECT/ABSTAIN;
it never replaces a verdict with a numerical baseline answer. Explanations
are retained without semantic grading. Literal numeric citations are checked
mechanically, not treated as proof of justified confidence.

## Logs and safeguards

Use the existing streaming Responses transport, high reasoning summaries,
encrypted reasoning replay, `store=false`, standard tier, disabled truncation,
sequential tool execution and zero automatic generation retries. Raw internal
reasoning is unavailable; retain all API-visible material without claiming more.

Each episode records frozen prompts/schemas/source hashes, requests, streamed
events, complete responses, usage/reservations, exact tool requests/results,
purchased numerical artifacts, private evaluation, transcript and checkpoint.
Campaign files record the catalog/comparison hashes, ordering, immutable slot
attempt markers, per-case outcomes, and aggregate accounting. Episode folders
are siblings of campaign folders to avoid Windows path-length problems.

Requests are reserved before generation. Unknown usage retains its reservation;
uncertain failures are not retried automatically. Duplicate call IDs do not
repeat purchases. Invalid or unaffordable actions are recoverable, while API,
time, output and request limits produce explicit incomplete outcomes. Ordinary
episode failures remain in the denominator while untouched cases continue.
Authentication, provenance and accounting problems halt the campaign.

The campaign reserves its remaining dollar allowance durably before each
sequential episode. That allowance becomes the episode's hard per-request
spending ceiling. After finalization, measured upper-bound charges and unknown
request reservations remain committed; only unused allowance becomes available
to the next case. An unfinalized launch retains its entire reservation. If the
remaining allowance cannot fund another full-output reservation, the campaign
stops; it does not lower output limits, retry, or increase the ceiling. The
scientific task and eight-credit limit are unchanged. API allowances can shrink
between cases and are saved in each frozen prompt/manifest.

Credentials are read privately from the existing file only in live mode.
Headers, keys and client objects are not serialized. All raw files remain local
and ignored by Git. A new campaign never overwrites or silently resumes a run.

## Commands

From the repository root, using the existing editable installation and optional
`agents` dependency for live use:

~~~powershell
# Offline 35-case rehearsal: no credentials or API calls.
.\.venv\Scripts\python.exe -B -m budgeted_science.agents.verification_incremental_catalog --dry-run

# Paid run: execute only with user authorization.
.\.venv\Scripts\python.exe -B -m budgeted_science.agents.verification_incremental_catalog --live

# Regenerate a saved campaign or episode report; no API/tool execution.
.\.venv\Scripts\python.exe -B -m budgeted_science.agents.verification_incremental_catalog --render PATH

# Explicitly resume ONE finalized, unsubmitted episode when authorized.
.\.venv\Scripts\python.exe -B -m budgeted_science.agents.verification_incremental_catalog --live --resume EPISODE_PATH
~~~

Standalone (non-batch-funded) explicit resume preserves the exact case, eight-credit ledger, conversation,
API charges/reservations and cumulative limits. It cannot reset a ceiling or
resume an already-submitted episode. An active or ambiguously interrupted
process requires inspection; never relaunch it blindly. Resumed child results
are the same sample and must be reconciled explicitly with a campaign report,
not counted as an additional independent episode. No automatic campaign restart
is implemented.

Batch-funded episodes cannot use standalone resume: their unused dollars may
already have funded later cases. They require an explicit reconciliation of the
shared ledger before any additional paid work. This guard prevents a saved
episode ceiling from bypassing the $2 total cap. Logs and offline rendering
remain available for all incomplete cases.

Verification includes numerical-contract agreement, source/catalog matching,
private-input isolation, complete history/logging, duplicate protection,
credential-free dry runs, spending safeguards, resume above five spent credits,
and offline report regeneration. Scientific commissioning/results are frozen
in the preceding CPU report.
