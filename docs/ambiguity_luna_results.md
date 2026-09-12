# Luna: finite-grid forecast-support pilot

## Frozen protocol

Two existing development claims, each at 32 and 256 scientific credits: four
independent Luna conversations, but only two related claims about one physical
system. Scientific definitions and CPU comparisons are unchanged from
[the reconstruction and ambiguity report](verification_reconstruction_and_ambiguity.md).

Explicit source catalog:
`demos/claim_verification/runs/20260912T090212Z-forecast-ambiguity-cpu-5c0876c378`.
The runner validates its catalog hash and scientific source hashes, requires all
12 CPU comparison results, and freezes imported artifact hashes. It never
regenerates cases or selects them based on model outcomes. Episode order is
sparse/32, sparse/256, rich/32, rich/256. Regime names, private reference banks,
labels and CPU results are withheld from model context.

Luna receives the public equations, 125 parameter vectors, bounded-error
observations, claimed forecast interval and original nominal calculations.
It chooses candidate calibration and forecast calculations. Tools return
computed numbers, not automatic consistency decisions or verdicts.

- Exact model `gpt-5.6-luna`, reasoning `high`, standard service tier.
- **$2 total batch API ceiling**, not $2 multiplied by four episodes.
- At most 30 responses, 30 tool requests, 32,768 output tokens per response
  including reasoning, and 20 minutes per episode.
- Tools: `describe`, `record`, `check`, `check_batch`, `budget`, `submit`.
- `check_batch` accepts up to 16 agent-selected candidate/stage pairs. Full
  argument validation precedes purchases. Checks execute sequentially and pay
  identical scientific charges to individual calls, with no automatic screening
  or stopping on a counterexample. It stops on an incomplete check or deadline.
  Every underlying calculation is logged. Batching avoids a 125-candidate task
  being limited purely by API conversation length; CPU controls already loop.
- One scientific credit is 256 actual RHS evaluations. Performed interrupted
  work is charged. Original/purchased results can be retrieved without charge.
- No full-budget requirement, savings bonus, LLM judge or arbitrary Python.

The [official Luna model page](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
confirms high reasoning, streaming and function calling. The
[official pricing page](https://developers.openai.com/api/docs/pricing), checked
2026-09-12, lists $0.20/M input, $0.02/M cached input, $0.25/M cache writes and
$1.20/M output. Reservations use $0.25/M for all input and $1.20/M for the entire
output allowance; input above 256,000 tokens is refused. The existing runner
retains unknown-usage reservations, disables generation retries, and never
substitutes models. API costs remain separate from scientific credits.

## Scoring and limitations

Binary verdict correctness and evidence-backed correctness are separate:
rejection needs completed checks of a compatible counterexample; acceptance
needs every candidate excluded by a calibration check or checked to forecast
inside the interval. Original nominal records count. Explanations are preserved,
not semantically graded. Abstention is completed but not a correct binary verdict.

These are finite-grid evidence certificates, not continuous-parameter
identifiability, probabilistic confidence, or formal numerical bounds. Rich-case
abstention at 32 credits is not automatically a reasoning failure; the screened
CPU control also cannot complete exhaustive coverage there. Other analytical
certificates are not recognized by this restricted evaluator.

## Reproduction and records

```powershell
python -B -m unittest discover -s tests -p test_ambiguity_agent.py -q
python -B -m budgeted_science.agents.ambiguity_agent --dry-run --catalog demos/claim_verification/runs/20260912T090212Z-forecast-ambiguity-cpu-5c0876c378
# Paid; run only after explicit authorization:
python -B -m budgeted_science.agents.ambiguity_agent --live --catalog demos/claim_verification/runs/20260912T090212Z-forecast-ambiguity-cpu-5c0876c378
python -B -m budgeted_science.agents.ambiguity_agent --render PATH_TO_BATCH_OR_EPISODE
```

Every fresh dry/live execution creates a unique ignored run. A new `--live` invocation starts
another paid batch, not a resume; there is no automatic repeat or crash-resume.
Episode inspection checkpoints and complete partial streams remain available.
Offline rendering calls neither tools nor API. Saved records include frozen
prompts/schemas, source/software hashes, all available API-visible responses and
reasoning summaries, opaque encrypted replay items, tool messages, full numerical
artifacts, actual submissions, private evaluations and imported CPU comparisons.
Raw internal reasoning is not available. Credentials are loaded only in live
mode; credentials and raw logs remain untracked.

## Results

Executed 2026-09-12, once per frozen slot, without retries. All four episodes
submitted; 26 model responses total; no API/runner errors or unknown usage.
There were **three correct, evidence-backed verdicts and one abstention**.
No false accepts or false rejects were submitted. Abstention still counts as
non-correct in the four-episode binary denominator; coverage was 3/4.

| Observations | Budget | Luna verdict | Evidence backed | Luna credits | Screened CPU verdict | Screened CPU credits |
|---|---:|---|---|---:|---|---:|
| Sparse | 32 | REJECT | Yes | 10.433594 | REJECT | 7.667969 |
| Sparse | 256 | REJECT | Yes | 29.527344 | REJECT | 7.667969 |
| Rich | 32 | ABSTAIN | No | 32.000000 | ABSTAIN | 32.000000 |
| Rich | 256 | ACCEPT | Yes | 125.574219 | ACCEPT | 125.574219 |

The other saved controls were unchanged: nominal-only ACCEPTs both claims at
zero cost (wrong for sparse, unsupported evidence for rich); fixed-full ABSTAINs
on sparse/32 and both rich budgets, and correctly REJECTs sparse/256 at
132.390625 credits. All controls had independent purchases and budgets.

### What Luna actually checked

- Sparse/32: 14 new calibration solves and three forecasts. It submitted
  candidate 27, `(0.8, 0.04, 1.4)`, as a counterexample: calibration prediction
  `13.025679239573249` differs from observation `13.106902828266445` by
  `0.081223588693196`, within the 0.1 bound. Its forecast `38.820224938711355`
  lies outside `[18.716064216889535, 19.873758910717754]`.
- Sparse/256: all 124 non-nominal calibration solves, then three forecasts.
  It submitted the same valid witness, spending more than at the lower cap.
  Neither trajectory is evidence of cost-optimal behavior.
- Rich/32: 28 attempted calibration solves, of which 27 completed and one
  exhausted the remaining work budget. With the original, 28 candidates had
  covered evidence; Luna abstained. No API interruption occurred.
- Rich/256: 124 new calibration solves excluded every non-nominal candidate.
  The free original forecast covered the nominal candidate, completing all 125.
  It accepted without buying unnecessary alternative forecasts.

| Case/budget | Responses | Runtime (s) | Usage-price estimate (USD) | Conservative ledger upper (USD) |
|---|---:|---:|---:|---:|
| Sparse/32 | 4 | 18.868 | 0.00373657 | 0.00761060 |
| Sparse/256 | 10 | 34.405 | 0.01180067 | 0.04187145 |
| Rich/32 | 3 | 90.957 | 0.01447978 | 0.01805420 |
| Rich/256 | 9 | 33.294 | 0.01688640 | 0.05688820 |
| Total | 26 | 177.524 | **0.04690342** | **0.12442445** |

The usage-price estimate includes returned cache-read and cache-write token
counts: `(ordinary_input*0.20 + cached_input*0.02 + cache_write*0.25 +
output*1.20)/1,000,000`. These are model-usage estimates, not invoices; no private
billing endpoint was queried. The more conservative reservation ledger counts
all input at $0.25/M and remains below the $2 batch cap. No reservations remain
unsettled. Output counts include reasoning tokens.

**Interpretation:** Luna matched the screened CPU control's four outcomes,
but spent more on both sparse runs. The rich low-budget abstention demonstrates
an evidence-coverage cost constraint, not by itself difficult scientific
reasoning. This small run does not establish agent superiority or a challenging
general verification benchmark.

### Local artifacts and verification

Batch directory (ignored):
`demos/claim_verification/runs/20260912T092913Z-luna-ambiguity-live-b317809f31`.
Its `report.md` links every transcript and includes all three CPU comparisons.
Its `summary.json`, `manifest.json`, `batch-budget.json` and `results/` retain
the full machine-readable comparison and provenance.

Episode directories under `demos/claim_verification/runs/`:

| Case/budget | Episode directory |
|---|---|
| Sparse/32 | `20260912T092913Z-live-0e3c1f3dc8` |
| Sparse/256 | `20260912T092933Z-live-e80b794f99` |
| Rich/32 | `20260912T093007Z-live-90355c0556` |
| Rich/256 | `20260912T093139Z-live-f6c6906cb5` |

Before paid execution: all **622 shared tests plus 14 planning tests passed**,
including 12 new adapter tests. A four-slot offline rehearsal also passed; its
predetermined ABSTAIN outputs are not model results. After live execution, every
frozen source/import hash was rechecked, all four transcripts were regenerated
offline byte-for-byte, and the 26 archived requests were checked for the exact
model and reasoning setting. Raw logs, credentials and original CPU results
remain unmodified by code checkpoints and untracked by Git.
