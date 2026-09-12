# Luna/high: recalibrated incremental verification results

## Outcome

GPT-5.6 Luna with high reasoning correctly judged **35/35 claims** on the frozen
fresh-system catalog. All episodes submitted a binary verdict; there were no
false acceptances, false rejections, abstentions, incomplete episodes, failed
tools, or retries. All four saved classical methods also scored 35/35.

The whole batch stayed below its **$2 total API ceiling**. Recorded usage gives
a lower accounting bound of **$0.14324472** and a conservative upper bound of
**$0.39635295**, with no unresolved usage reservations. These are usage-based
accounting bounds, not an invoice. The remaining conservative allowance was
$1.60364705; it was not spent or used for additional runs.

This revision is still easy for Luna on the selected cases. It demonstrates
working tools, logs, and objective verdict evaluation, but does not establish
an adaptive-allocation challenge or an agent advantage over simple policies.

## Frozen experiment

The [scientific commissioning report](claim_verification_recalibrated_results.md)
defines the unchanged predator-prey system, case generator, independent
reference checks, and CPU policies. The [agent protocol](claim_verification_incremental_agent_protocol.md)
defines the prompt, tools, and logging contracts.

- Six fresh systems, seeds 7200–7205, produced 35 study variants: 18 valid and
  17 invalid claims. These are not 35 independent physical systems.
- The generator could not populate the mixed-invalid slot for seed 7204.
  That pre-existing commissioning failure remains recorded; no replacement or
  post-result selection was performed.
- Each report claims that its original stored-sample population maximum is
  within 5% of the mathematical-model maximum. No physical validation or
  unknown-parameter estimation is involved.
- Eight audit credits per independent episode. Integration refinement halves
  the selected Euler timestep for 3 credits. Sampling refinement bisects the
  selected output intervals for 2 credits. Checks can be chained.
- Exact model `gpt-5.6-luna`, high reasoning, standard service tier, Responses
  streaming, `store=false`, sequential function calls, no arbitrary Python.
- Maximum 30 responses and 30 tool requests per episode; 32,768 output tokens
  per response; 20-minute episode deadline. No model substitutions or retries.
- No prescribed checking sequence, full-budget requirement, spending penalty,
  or early-stopping reward. Final verdicts, not explanations, determine accuracy.

The first $105 worst-case allowance was never used. After the user requested
a smaller cap, the runner enforced $2 across all 35 episodes, reserving the
remaining allowance before each sequential episode and enforcing per-request
token reservations within it. Unknown usage would retain its reservation.
Standalone resume is blocked for batch-funded episodes until shared-accounting
reconciliation, preventing reuse of an old episode allowance.

## Matched results

| Method | Correct verdicts | Incomplete | Total audit credits |
|---|---:|---:|---:|
| Luna/high | 35/35 | 0 | 279 |
| Fixed IIS + extrapolation | 35/35 | 0 | 280 |
| Fixed ISS + extrapolation | 35/35 | 0 | 245 |
| Random acquisition + extrapolation | 35/35 | 0 | 272 |
| Adaptive change + extrapolation | 35/35 | 0 | 263 |

I denotes integration refinement and S denotes sampling refinement. CPU
outcomes were imported from verified saved results on these exact studies,
not rerun or exposed to Luna. Every method had independent scientific purchases.
Spending is descriptive; it is not part of the verdict score.

| Study family | Valid claims correct | Invalid claims correct |
|---|---:|---:|
| Integration | 6/6 | 6/6 |
| Sampling | 6/6 | 6/6 |
| Mixed | 6/6 | 5/5 |

False acceptance was 0/17 invalid claims; false rejection was 0/18 valid claims.
Coverage was 35/35. All attempts are included.

## Observable actions and usage

Luna made three paid checks per case:

- IIS in 29 cases, SII in five cases, and SSI in one case.
- Thus, 34 cases used two integration checks and one sampling check (8 credits);
  one used one integration and two sampling checks (7 credits).
- Total: 69 integration refinements and 36 sampling refinements.
- Across all episodes: 394 model responses and 394 tool requests, including
  184 artifact reads, 34 run comparisons, and 35 final submissions.

This near-uniform expenditure pattern is not evidence of sophisticated adaptive
allocation. Nor does a correct verdict establish justified confidence or a
correct explanatory diagnosis. The CPU methods have an implemented numerical
extrapolator; Luna has the same primitive audit tools but no automatic fitting
helper or Python execution. Their comparison is between complete methods,
not an isolated test of language interpretation or planning.

Usage was 1,253,919 input tokens and 69,061 output tokens, including 45,461
reasoning tokens. Summed episode time was 1,384.04 seconds (23.07 minutes),
averaging 39.54 seconds. Logs retain all returned API-visible material,
including 309 encrypted reasoning items and 217 items with reasoning summaries.
Opaque encrypted items are not readable internal reasoning.

## Records and verification

Live run (2026-09-12 UTC):

`demos/claim_verification/runs/20260912T030958Z-luna-incremental-live-2c76398a85/`

- [Complete comparison and all 35 transcript links](../demos/claim_verification/runs/20260912T030958Z-luna-incremental-live-2c76398a85/report.md)
- [Machine-readable summary](../demos/claim_verification/runs/20260912T030958Z-luna-incremental-live-2c76398a85/summary.json)
- [Batch spending ledger](../demos/claim_verification/runs/20260912T030958Z-luna-incremental-live-2c76398a85/batch-budget.json)
- [First complete transcript](../demos/claim_verification/runs/20260912T030959Z-live-ab5e6015e9/transcript.md)

Episode directories sit beside the campaign directory. Each retains prompts,
schemas, complete requests/responses/stream events, tool arguments/results,
numerical artifacts, checkpoints, and private scoring. Raw runs and credentials
remain untracked; these local links are not portable without the run artifacts.

Before live execution, **417 tests passed** (403 root plus 14 planning-pilot).
The updated 35-case offline rehearsal completed without credentials or API calls.
Its scripted answers are not included as model-performance results.

After completion, a read-only audit confirmed all 35 unique slots, exact model
and reasoning settings, final submissions, successful paid checks, eight-credit
limits, intact event sequences, complete transcripts, and token usage within
every pre-request reservation. The batch ledger reconciled exactly to the sum
of episode charges; all scientific source and imported comparison hashes were
unchanged. Offline report regeneration produced identical report bytes.

Code checkpoint: `84dc114bb11afa670d96a9516e464a7458e26fc7`.
Frozen source-manifest SHA-256:
`d75cf0c6f231d881c031db94d2be94fc2cde386746019da8e6ae1666708aad14`.
Software: Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1, OpenAI SDK 2.54.0,
HTTPX 0.28.1, budgeted-science 0.1.0.

To regenerate the report without API calls or solver execution:

~~~powershell
.\.venv\Scripts\python.exe -B -m budgeted_science.agents.verification_incremental_catalog --render demos/claim_verification/runs/20260912T030958Z-luna-incremental-live-2c76398a85
~~~

Do not rerun `--live` as a report-regeneration step: it creates a new paid batch
and requires new authorization. Prior five-credit and CPU experiments remain
unchanged and are not pooled with this evaluation.
