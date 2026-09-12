# Luna transport-verification results

Completed 2026-09-12. **GPT-5.6 Luna with high reasoning scored 12/12**, matching
the strongest saved CPU controls on the exact same development catalog.

| Method | Correct | Mean scientific credits |
|---|---:|---:|
| GPT-5.6 Luna, high | 12/12 | 3.6626 |
| Balanced fixed CPU rule | 12/12 | 3.0065 |
| Space-focused CPU rule | 12/12 | 3.0065 |
| Time-focused CPU rule | 9/12 | 3.0039 |
| Output-focused CPU rule | 12/12 | 3.0049 |
| Randomized CPU check, seed 0 | 12/12 | 2.0807 |

All twelve episodes submitted a binary verdict: six correct acceptances and
six correct rejections. There were no abstentions, incomplete outcomes,
automatic retries, model substitutions or budget increases. Each of peak,
arrival, exposure and crossing scored 3/3. CPU results were imported and
verified, not rerun or shown to Luna.

## Resources

- Scientific budget: **4 credits per independent episode**; actual range
  3.0078 to 3.8867, total 43.9512 across the twelve episodes.
- API accounting interval: **$0.08120530 to $0.16008110 for the whole batch**,
  below its $2 cap. No unknown usage or pending reservations remain. These
  are rate-based accounting bounds, not an invoice.
- 97 completed model responses, 411,062 input tokens and 47,763 output tokens
  across all requests; 41,604 output tokens were reported as reasoning tokens.
- Total agent runtime: 630.6 seconds; mean 52.5 seconds per case.

The unchanged limits were high reasoning, 32,768 output tokens per response,
30 responses, 30 tool requests and 20 minutes per episode. The verified
[official Luna pricing](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
informed the conservative spending reservations, including cache-write input
pricing. See the [runner protocol](transport_verification_agent_protocol.md).

## What this does and does not show

The general numerical tools work with a live agent: it selected checks, inspected
existing runs and submitted correctly within the scientific budget. However,
**this does not rescue the current catalog as an adaptive-auditing challenge**.
Several fixed rules and the single randomized control already solve every claim.
There is no spending penalty in the task, so mean expenditure is descriptive,
not an efficiency score. Twelve claims share only three physical systems and
nine original numerical studies; they are not twelve held-out independent systems.

Some final explanations invoke the analytic Gaussian solution or travel-time
approximations alongside purchased runs. That is possible with the public
equation and coefficients even without Python or a reference-query tool. It
is a limitation of this analytically tractable toy, not hidden-reference access.
We have not isolated how much those approximations caused the correct verdicts.

Correct verdicts also do not establish correct reasoning. In the
[middle-diffusion arrival episode](../demos/claim_verification/runs/20260912T061222Z-live-b92d152b40/transcript.md),
Luna's final explanation equates the continuous peak time with the advective
travel time 0.8333333. The independently checked reference is 0.8231106671:
diffusion and decay shift the sensor maximum. The reported value 0.8359375
still satisfies 3%, so ACCEPT is correct despite that inaccurate explanation.
This is a qualitative inspection example, not an added semantic grading metric.

## Preservation and verification

The frozen source was the twelve-case CPU run
`20260912T054409Z-transport-cpu-b5aefbda0e`. The numerical setup, selected cases,
tolerance, work prices and four-credit budget were not changed for Luna. All
cases ran once in saved order with independent history and purchases.

**550 tests passed** before live execution: 536 repository tests, including
eight new agent-adapter tests, plus 14 planning-pilot tests. The exact twelve
cases also completed an offline scripted rehearsal; those predetermined ACCEPT
fixtures are not counted as model results.

Post-run checks verified all twelve case identities, source/catalog/import
hashes, exact Luna/high settings, prompt/schema hashes, 97 response archives,
scientific charges and final API reconciliation. Every episode transcript,
evaluation and report, plus the campaign report, regenerated identically offline
with solver execution blocked. No further API calls were needed.

Raw logs retain API-visible requests, stream events, complete responses,
reasoning summaries, opaque encrypted reasoning items, exact tool results,
full numerical artifacts and submissions. Raw internal reasoning is unavailable.
Credentials were loaded privately only in live mode and remain untracked.
No previous experiments or proposal documents were modified; nothing was pushed.

## Local artifacts

Live campaign: `20260912T060707Z-luna-transport-live-76fa7cd6b5`.

- [Complete comparison and links to all transcripts](../demos/claim_verification/runs/20260912T060707Z-luna-transport-live-76fa7cd6b5/report.md)
- [Aggregate results](../demos/claim_verification/runs/20260912T060707Z-luna-transport-live-76fa7cd6b5/summary.json)
- [Frozen manifest and source/import hashes](../demos/claim_verification/runs/20260912T060707Z-luna-transport-live-76fa7cd6b5/manifest.json)
- [Final batch accounting](../demos/claim_verification/runs/20260912T060707Z-luna-transport-live-76fa7cd6b5/batch-budget.json)

```powershell
# Offline regeneration, no science or model rerun:
.\.venv\Scripts\python.exe -B -m budgeted_science.agents.transport_catalog --render demos\claim_verification\runs\20260912T060707Z-luna-transport-live-76fa7cd6b5
```

Running `--live` again would create a NEW paid batch, not resume this result.
No additional batch is authorized by this completed run.
