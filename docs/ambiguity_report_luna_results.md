# Luna: report-style claim audit without strategy instructions

## Frozen comparison

This is a separate, less-scaffolded condition for the same two development
claims and scientific budgets (32 and 256 credits) used in the
[earlier Luna pilot](ambiguity_luna_results.md). It does not modify the scientific
catalog, solver, observations, candidate list, numerical tolerances, original
records, claim endpoints, work accounting, CPU policies, or saved earlier runs.

The report states that calibration evidence, under the declared absolute
measurement-error bounds and finite parameter list, constrains the forecast to
the original interval. Task instructions ask the agent to audit that claim,
return ACCEPT/REJECT/ABSTAIN, and identify its evidence. The claim retains its
universal meaning, but the checking procedure is not spelled out.

Removed from agent-facing prompts and free views:

- The warning that a nominal fit alone does not establish the claim.
- Instructions to find a compatible counterexample.
- Instructions to complete calibration and forecast checks for a witness.
- Instructions or budget warnings about exhaustive candidate coverage.
- A dedicated `witness` field, replaced by neutral `evidence_ids`.
- Strategy-revealing wording in the batch-tool description.

Still supplied: the exact numerical data, finite candidate scope, equations,
measurement bounds, numerical-method settings, tool functionality, prices,
record identifiers, execution limits and verdict meanings. Computational tools
remain `check` and `check_batch`; this is not an unstructured coding environment.

The intervention changes task wording, report presentation, some tool-description
wording, and submission schema together. It is a **presentation/interface
comparison**, not a pure one-sentence prompt ablation. Each condition has just
one stochastic model run per case/budget. Any outcome differences cannot be
attributed uniquely to removal of the hints, nor establish general difficulty.

## Scoring

Primary scoring remains the frozen objective verdict correctness. Abstention is
completed but not a correct binary verdict. Evidence IDs are mechanically checked
for existence; even unsupported ACCEPT/REJECT submissions end the episode and
are scored, rather than being rejected until a prescribed method is followed.

The existing numerical evidence criteria are **secondary diagnostics only**:

- For REJECT, the diagnostic identifies matching completed calibration/forecast
  pairs among the agent's cited records, checks the public numerical relationship,
  and then applies the independent-reference consistency check. It does not search
  uncited historical results for favorable evidence. Derived candidate IDs are
  evaluator diagnostics, not candidate IDs explicitly submitted by the agent.
- For ACCEPT, the existing all-purchased-candidate coverage diagnostic is retained
  for comparison with earlier runs. It does not require citing all 125 records.
- Explanations and alternative analytical arguments are preserved without semantic
  grading. Failure of this specific procedural diagnostic is not proof that the
  agent's reasoning or confidence was unjustified.

## Execution and safety

Exactly four new episodes, in order: sparse/32, sparse/256, rich/32, rich/256.
Fresh independent conversations and scientific purchase histories; no new CPU
episodes. Source cases are fixed before execution, not selected by outcomes.

- Model `gpt-5.6-luna`, high reasoning, standard tier; no substitutions.
- **$2 TOTAL new API ceiling**, not $2 per episode.
- 30 responses/tool requests, 32,768 output tokens including reasoning per
  response, and 20-minute deadline per episode.
- Reuse the streaming Responses runner, full history replay, reasoning summaries,
  opaque encrypted items, token-count reservations, credential redaction and
  durable logs. Raw internal reasoning is not exposed.
- No automatic retries/resume; interrupted attempts and uncertain reservations
  remain recorded. A fresh live command creates a new paid batch.

The [official Luna documentation](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
was checked on 2026-09-12. High reasoning, streaming and function calling remain
supported. Prices are $0.20/M input, $0.02/M cached input, $1.20/M output; cache
writes are 1.25 times ordinary input. The runner conservatively reserves at
$0.25/M input and $1.20/M output and refuses input above 256,000 tokens.

Frozen CPU source:
`demos/claim_verification/runs/20260912T090212Z-forecast-ambiguity-cpu-5c0876c378`.
Frozen earlier Luna comparison:
`demos/claim_verification/runs/20260912T092913Z-luna-ambiguity-live-b317809f31`.
The new manifest hashes imported artifacts, study identities, implementation,
software versions and tool schemas. Earlier outcomes never enter model context.

```powershell
python -B -m unittest discover -s tests -p test_ambiguity_report.py -q
python -B -m budgeted_science.agents.ambiguity_report_catalog --dry-run --catalog demos/claim_verification/runs/20260912T090212Z-forecast-ambiguity-cpu-5c0876c378 --scaffolded demos/claim_verification/runs/20260912T092913Z-luna-ambiguity-live-b317809f31
# Paid; requires explicit authorization:
python -B -m budgeted_science.agents.ambiguity_report_catalog --live --catalog demos/claim_verification/runs/20260912T090212Z-forecast-ambiguity-cpu-5c0876c378 --scaffolded demos/claim_verification/runs/20260912T092913Z-luna-ambiguity-live-b317809f31
python -B -m budgeted_science.agents.ambiguity_report_catalog --render PATH_TO_BATCH_OR_EPISODE
```

Dry-runs use scripted fixtures without credentials or API calls. Rendering is
offline and executes no scientific tools. Every fresh execution creates unique
ignored logs with public artifacts, separately private labels/references, API
requests/responses/events, numerical outputs, actual neutral-field submissions,
evaluations and readable transcripts. Credentials and raw runs remain untracked.

## Results

Executed on 2026-09-12. All four authorized episodes submitted; no retries,
abstentions, incomplete episodes, or extra CPU evaluations. These are two related
development claims at two budgets, not four independent scientific systems.

The underlying toy uses 125 candidate parameter vectors for the predator-prey
system. Calibration starts at populations (10, 5); the forecast starts at (20, 2)
and asks for prey population at time 24. The report claims that the calibration
evidence constrains the forecast to [18.716064216889535, 19.873758910717754].
Sparse evidence is one early prey reading and admits four candidates, three of
which violate the interval. Rich evidence is 16 bounded population readings and
admits only the nominal candidate. The former claim is false; the latter is true
on the declared finite list. These truths and all measurements are unchanged.

| Evidence | Budget | Earlier verdict | Report-style verdict | Correct | Numerical evidence diagnostic | Earlier credits | New credits |
|---|---:|---|---|---|---|---:|---:|
| Sparse | 32 | REJECT | REJECT | Yes | Cited counterexamples verified | 10.434 | 26.895 |
| Sparse | 256 | REJECT | REJECT | Yes | Cited counterexamples verified | 29.527 | 29.527 |
| Rich | 32 | ABSTAIN | ACCEPT | Yes | Incomplete coverage: 33/125 | 32.000 | 32.000 |
| Rich | 256 | ACCEPT | ACCEPT | Yes | Complete coverage: 125/125 | 125.574 | 145.809 |

Primary verdict accuracy is **4/4**, compared with **3/4 plus one abstention**
previously. The secondary numerical evidence diagnostic passes **3/4 in both
conditions**. That difference matters: increased binary accuracy here is not an
extra completed verification.

### What the traces show

- Sparse/32: without being told to construct a counterexample, Luna cited
  candidates 27 and 29. Their calibration values, 13.025679239573249 and
  13.151578434454452, fall within 0.1 of the observation 13.106902828266445.
  Their forecasts, 38.820224938711355 and 55.51951425698939, lie outside the
  claimed interval. These are concrete numerical grounds for rejection.
- Sparse/256: Luna also cited candidate 28, with calibration value
  13.091459873224197 and forecast 47.405803411024074. Its rejection likewise
  passes the independent numerical evidence check.
- Rich/32: after exhausting the budget, Luna accepted based on the nominal fit
  and representative alternatives failing the observation bounds. Only 33 of
  125 candidates were covered by the saved completed numerical checks. The
  submitted explanation moves from no checked alternative violating the claim
  to accepting it over the entire list, without supplying a bound or argument
  ruling out the unchecked candidates. The verdict matches private truth, but
  that stated argument does not by itself establish the universal claim.
- Rich/256: Luna checked calibration compatibility throughout the list and
  established complete coverage with the original nominal forecast. It also
  spent additional work on forecasts; total cost exceeded the earlier run and
  the saved screened CPU policy (both 125.574 credits).

The rich/32 observation is a trace-based assessment of the submitted explanation,
not an LLM-judge score or a claim about inaccessible internal reasoning. A valid
alternative analytical argument would not have to enumerate every candidate;
none is supplied in this submission. Removing guidance has **not demonstrated
greater task difficulty** or a general reliability change. It exposes why verdict
accuracy alone can hide an incomplete audit in this particular example.

### API usage and runtime

| Evidence | Budget | Responses | Seconds | Usage-based estimate (USD) | Conservative upper bound (USD) |
|---|---:|---:|---:|---:|---:|
| Sparse | 32 | 11 | 47.704 | 0.01439780 | 0.05199410 |
| Sparse | 256 | 10 | 39.523 | 0.01223220 | 0.04227285 |
| Rich | 32 | 5 | 91.092 | 0.01828879 | 0.02977620 |
| Rich | 256 | 16 | 75.996 | 0.02980112 | 0.14480145 |
| Total | | 42 | 254.314 | **0.07471991** | **0.26884460** |

The usage-based estimate applies the documented rates to 972,908 input tokens
(843,993 cache reads, 128,789 cache writes, 126 ordinary input) and 21,348 output
tokens, including 15,887 reasoning tokens. This is an estimate, not an invoice.
The conservative ledger charges all input at its upper rate, without cache-read
discounts; it is not the expected bill. No usage is missing or reserved as
uncertain. The campaign stayed below its $2 total ceiling.

### Saved artifacts and verification

- [Full campaign report](../demos/claim_verification/runs/20260912T100354Z-luna-report-live-b80c4ca9f6/report.md)
- [Frozen manifest and provenance](../demos/claim_verification/runs/20260912T100354Z-luna-report-live-b80c4ca9f6/manifest.json)
- [Sparse/32 transcript](../demos/claim_verification/runs/20260912T100354Z-live-02a2b91ba7/transcript.md)
- [Sparse/256 transcript](../demos/claim_verification/runs/20260912T100442Z-live-ee945eda29/transcript.md)
- [Rich/32 transcript](../demos/claim_verification/runs/20260912T100523Z-live-dc45ca4d41/transcript.md)
- [Rich/256 transcript](../demos/claim_verification/runs/20260912T100654Z-live-c825c46254/transcript.md)

Artifacts are local and ignored; links will not resolve in a clean checkout.
Every episode retains full request/response/stream logs, purchased numerical
records, neutral-field submissions and separately private evaluations.

Before live execution, all **635 shared tests plus 14 planning-pilot tests**
passed (649 total), including 13 new report-condition tests. The four-slot offline
rehearsal used no credentials or API calls. After execution:

- All 129 frozen source hashes, 14 imported CPU-artifact hashes and 21 imported
  scaffolded-artifact hashes matched; no prior result was changed.
- All 42 saved generation requests used Luna/high, 32,768 output tokens,
  `store=false` and sequential tool execution.
- All four transcripts and the campaign report regenerated byte-identically
  offline, without executing solvers, tools or API requests.

Code lives in separate `ambiguity_report` and `ambiguity_report_catalog` modules.
The numerical environment and earlier scaffolded runner remain unchanged. No
proposal documents, credentials or raw runs are included in the code checkpoint.
