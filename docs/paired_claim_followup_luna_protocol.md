# Luna evaluation of the corrected follow-up toy

This adapter evaluates the **existing six development studies** from
`paired-claim-followup-v2`; it does not generate new cases or alter the CPU
experiment. See [the scientific setup and CPU results](paired_claim_followup_results.md).

## Frozen configuration

| Setting | Value |
|---|---|
| Model / reasoning | `gpt-5.6-luna` / `high` |
| Episodes | One per study, six total, independent histories and ledgers |
| Scientific credits | 32 per episode; all initially available |
| Prices | New low simulation 1; high simulation 8; target scalar measurement 12 |
| Utility | +1 correct verdict, -2 wrong verdict, 0 abstention |
| API ceiling | $1 per episode; $6 maximum total; allowances not transferred |
| Limits | 30 responses, 60 tool requests, 32,768 output tokens/response, 20 minutes |
| Execution | Streaming Responses API; standard tier; `store=false`; no retries |

The exact model supports high reasoning, streaming and function calling.
Prices were rechecked on 2026-09-13: standard input $0.20, cached input $0.02,
cache-write input $0.25 and output $1.20 per million tokens. Reservations use
$0.25 for every input token and $1.20 for the entire output allowance, including
reasoning. Requests above 256,000 input tokens are refused. Usage and conservative
bounds are recorded separately; neither is presented as a billing invoice.
Sources: [model documentation](https://developers.openai.com/api/docs/models/gpt-5.6-luna),
[pricing](https://developers.openai.com/api/docs/pricing).

## Agent interface

Luna receives the six shuffled claims, the original report and Euler trajectory,
the low-fidelity intervention summary, both competing parameter fits, public
parameter bounds and numerical settings, and the free noisy observations at
time 1. Candidate fits are not certified or guaranteed to exhaust the model
family. Private target identity, references, labels, seeds and CPU outcomes are
not included in the prompt or tool results.

Seven actions are available: `simulate_low`, `simulate_high`, `measure_target`,
`evidence`, `get_status`, `compare_cached_candidates`, and `submit`. Parameters
for simulation are freely selectable within the public bounds. No Python tool,
fitting helper, automatic acquisition policy or reference query is supplied.
The API adapter reuses the existing argument validation, duplicate-call guard,
scientific accounting, numerical artifact logging and private verdict scoring.

There are **no forced initial purchases** or prescribed acquisition sequence.
The CPU policies' 9-credit initialization is not imposed on Luna. Reuse and
measurement-noise rules are identical to the frozen CPU environment. Submission
can occur at any expenditure. There is no savings bonus, full-budget condition
or automated grading of explanations. Each verdict uses its own claim formula
and threshold, not a common 5% tolerance.

## Preservation and reproducibility

The imported catalog has SHA256 (canonical JSON)
`79543b99a111c52c25aff7d851b5a6e99b6cb3c9e660387fc4dcfd47908c6b3d`.
The original prepared directory and CPU pilot are:

- `demos/paired_claim_audit/runs/20260913T044814Z-followup-prepared-3e6ff0218b`
- `demos/paired_claim_audit/runs/20260913T044853Z-followup-pilot-a183dde9e0`

Preparation checks the catalog and every pre-existing source file in the CPU
manifest. New adapter files are allowed, but frozen scientific files must be
unchanged. CPU results are imported as private comparison snapshots, not rerun.
The new manifest separately records imported artifact hashes, current source
hashes and software versions, the six ordered slots, frozen prompts and tools,
pricing and spending caps.

From the repository root:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_followup_claim_agent.py -v
.venv\Scripts\python.exe -m budgeted_science.agents.followup_claim_audit prepare
.venv\Scripts\python.exe -m budgeted_science.agents.followup_claim_audit dry-run <prepared-directory>
# Only with explicit authorization for paid execution:
.venv\Scripts\python.exe -m budgeted_science.agents.followup_claim_audit live <prepared-directory>
.venv\Scripts\python.exe -m budgeted_science.agents.followup_claim_audit render <campaign-directory>
.venv\Scripts\python.exe -m budgeted_science.agents.followup_claim_audit render-episode <episode-directory>
```

`prepare`, `dry-run` and rendering use no credentials or API calls. Live mode
privately loads the existing ignored credential file. An exclusive campaign
marker and durable per-slot markers prevent repeating this prepared campaign.
An attempted but incomplete episode remains an outcome. Expected episode limits
allow untouched slots to continue; infrastructure/accounting failures halt the
campaign. This adapter does not implement crash-resume or automatic continuation.

Every episode retains requests, count requests, streaming events, complete API
responses, available reasoning summaries and opaque encrypted reasoning items,
exact tool requests/responses, full numerical artifacts, private evaluations,
transcript and report. Hidden internal reasoning is not available. All generated
records stay in unique ignored run directories. Offline report regeneration
executes neither scientific tools nor API requests.

## Interpretation

Report raw correct/wrong/abstain counts alongside utility, coverage, incomplete
outcomes, resource purchases, runtime and API cost bounds. These are engineered
development systems: paired studies share initial public evidence, and the last
pair even shares all six labels. Six episodes are not an estimate of general
scientific verification performance. CPU comparisons use restricted estimators
and different decision procedures; performance differences do not isolate a
causal planning capability or establish that explanations are scientifically sound.
