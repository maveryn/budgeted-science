# Mixed scientific claims with shared evidence

Six claims about numerical accuracy, target agreement, cumulative abundance,
intervention effects, recovery and population composition. Reuses the existing
predator-prey environment with **32 credits and 1/8/12-credit prices**. The
older point-claim study and all previous results are preserved.

See the [frozen protocol](../../docs/mixed_claim_audit_protocol.md).

The [completed comparison](../../docs/mixed_claim_audit_results.md) reports
Luna/high at 5/6 correct, one wrong and 27 credits; the fixed classical
baseline gets four correct and two abstentions at 32 credits. Full
transcripts, resource purchases, the 52-credit CPU-only diagnostic and
the explanation/error qualifications are linked there.

The [24-credit Luna follow-up](../../docs/mixed_claim_luna_24_results.md) scored
5/6 correct, one wrong and no abstentions at 23 credits. It again missed C6
(target recovery). The matched fixed control scored 3/6 with three abstentions
at 20 credits. Full logs and the budget-only comparison are linked in that report.

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m budgeted_science.agents.mixed_claim_audit validate
.\.venv\Scripts\python.exe -m budgeted_science.agents.mixed_claim_audit prepare
.\.venv\Scripts\python.exe -m budgeted_science.agents.mixed_claim_audit dry-run <prepared-directory>
.\.venv\Scripts\python.exe -m budgeted_science.agents.mixed_claim_audit live <prepared-directory>
.\.venv\Scripts\python.exe -m budgeted_science.agents.mixed_claim_audit render <episode-directory>
```

`validate` runs CPU references and the fixed policy at 32 and 52 credits; the
latter is a complete-evidence diagnostic, not a matched agent comparison.
`prepare` reruns the independent 32-credit control and freezes the study,
sources, prompts, schemas and configuration. `dry-run` is a fake-model test
with zero real API spending. Only `live` accesses credentials or the API;
invoke it only after explicit owner authorization. It is locked to one
attempt with the prepared model, high reasoning, the frozen scientific budget
and a $1 API ceiling. The default remains Luna with 32 scientific credits.

For the explicitly requested lower-budget Luna condition, use:

```powershell
.\.venv\Scripts\python.exe -m budgeted_science.agents.mixed_claim_audit prepare --model gpt-5.6-luna --budget 24
```

Then use the new preparation directory with `dry-run` and, when authorized,
`live`. This keeps the same six claims, order, target, noise stream, tools and
1/8/12 prices. The prompt changes only in its budget/accounting fields.
Model and budget cannot be overridden at launch; Sol remains restricted to
the existing 32-credit condition. The fixed CPU control is independently run
at the selected budget without changing its acquisition policy.

Full logs and artifacts are saved in unique ignored `runs/` directories.
No auto-retries, model substitutions or limit increases. Source/input
mismatches prevent launch. Explicit continuation of finalized unsubmitted
Sol attempts is supported below; ambiguous crashes require manual inspection.
Rendering uses saved logs only. No arbitrary Python or extra
scientific tools are exposed to the model.

## Matched Sol follow-up

The [initial Sol segment](../../docs/mixed_claim_sol_results.md) ended at the
API reservation ceiling before submission, after 31/32 scientific credits.
With explicit approval, the [same episode subsequently completed](../../docs/mixed_claim_sol_resumed_results.md):
**5/6 correct, one wrong, 32 credits**, with cumulative API upper bound $0.80116
under the revised $1.50 ceiling. It missed the same recovery claim as Luna.
All original logs remain preserved; the continuation is not another sample.

```powershell
.\.venv\Scripts\python.exe -m budgeted_science.agents.mixed_claim_audit prepare --model gpt-5.6-sol
```

Use the printed directory with `dry-run` and, when authorized, `live`. The
scientific study, shuffled order, prompts, tools, prices and limits are
identical to Luna's. Model selection is frozen at preparation and cannot
be overridden at launch. Sol uses its existing model-specific conservative
API prices; the $1 ceiling is unchanged. Earlier Luna logs remain untouched.

Offline Sol rehearsals use a fixed synthetic token-usage fixture, not a
tokenizer or spending estimate. The older byte-count fixture is retained
in a test for API-ceiling termination. All live counting still uses the
API's token-count endpoint and the unchanged reservation rules.

## Explicit continuation of the same Sol episode

```powershell
.\.venv\Scripts\python.exe -m budgeted_science.agents.mixed_claim_resume check <parent-episode-directory> --api-ceiling-usd 1.50
# Only after explicit approval of this cumulative ceiling:
.\.venv\Scripts\python.exe -m budgeted_science.agents.mixed_claim_resume live <parent-episode-directory> --api-ceiling-usd 1.50
```

`check` is read-only and never accesses credentials or the API. `dry-run`
continuation accepts only an offline parent; it cannot turn a live attempt
into a synthetic result. The original fresh-run command retains its $1 ceiling.
Continuation accepts only Sol/high with 32 credits, preserves all cumulative
limits, and permits a ceiling no higher than $1.50. An omitted ceiling keeps
the previous allowance. Never increase it without owner approval.

The child contains the earlier conversation, encrypted reasoning items,
tool responses, API archives, observations, numerical trajectories and paid
purchase state. Prior API usage and uncertain reservations remain charged;
response and tool counts and active runtime remain cumulative. No solver or
observation acquisition runs during restoration. Earlier inspection-only
checkpoints can migrate from complete finalized logs; incomplete or inconsistent
tool activity fails closed. An exclusive parent marker prevents two children
from spending the same remainder. Continue a child explicitly if necessary,
never restart its parent. Submitted episodes cannot resume.

Only an operational continuation notice is appended to the original frozen
prompt; claims, tools, evidence, prices and scoring do not change. There is
still no full-budget requirement. The prior report remains an immutable
historical record, and the child result is the same sample, not another trial.
Offline `render` on the child regenerates its cumulative report/transcript.

The replay follows [official OpenAI documentation](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-without-stored-responses):
preserve replayable output, including opaque encrypted reasoning and assistant
phase. No raw private reasoning is available or claimed.
