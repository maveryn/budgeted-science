# Predator-prey verification: alternative-tool comparison

This isolated experiment tests the user's suggestion to add plausible numerical
alternatives to the original five-credit peak-claim task. It does not replace
the original catalog, incremental revisions, or MMS toy. The added actions
perform real calculations; their descriptions do not misrepresent their scope.

## Frozen scientific task

- Same predator-prey equations, fixed initial state `(10,5)`, and interval `[0,8]`.
- Same original reported maximum of species A and 5% relative-accuracy claim.
- Same private independently checked numerical reference and verdict scoring.
- Same five-credit budget, free inspection/retrieval, and charged failed solves.
- No noise, parameter inference, physical validation, arbitrary code execution,
  LLM judge, spending penalty, or full-budget submission requirement.

Five existing development studies are selected by a rule fixed before this
experiment's numerical checks: category index `i` on system seed `7100+i`.
The categories in existing catalog order are sound, harmless integration,
consequential integration, harmless sampling, and consequential sampling.
Thus these are five studies on five systems, not a new 30-case catalog. They
were previously available for development, not held-out evaluation cases.

## Two menus

Both menus retain all eight original actions and their prices. The core
scientific prompt is identical within a case; it refers to tool descriptions
for prices and numerical settings. Tool schemas are sorted by name in both
conditions, preserving original tools' relative ordering. The expanded menu
adds only:

| Action | Credits | Executed calculation |
|---|---:|---|
| `tighten_integration(run_id)` | 1 | Halve an Euler timestep; for an adaptive integrator, divide both tolerances by ten. Keep the output times. |
| `bisect_output(run_id)` | 1 | Add a midpoint in each saved-output interval; keep integration settings and evaluate/rerun that numerical trajectory. |
| `crosscheck_integrator(run_id)` | 3 | Rerun with Radau at `rtol=1e-10`, `atol=1e-12`, preserving output times. |

All actions can operate on original or purchased runs. Identical purchased
configurations are free regardless of the action route. Cross-episode backend
cache hits do not waive a new episode's charge. Numerical artifacts, output
times and settings are retained. The first two actions give incremental changes,
not an immediate jump to the original tools' high-accuracy settings.

Radau is an alternative integrator of the same equations, not an independent
physical model or a private reference query. Chaining Radau and the existing
dense-sampling action provides another five-credit verification route.

These are declared flat resource prices, not measured runtime or money. They
are illustrative and not calibrated claims about actual scientific costs.
The original complete five-credit route remains available: this is a test of
tool-menu robustness, not a deliberate removal of solvability.

## CPU checks and live comparison

Before live calls, run the unchanged fixed two-check numerical rule once per
menu/case with independent budgets. Also record each added action used alone
as a diagnostic control. This produces 25 cheap CPU policy/check episodes on
the five studies, not 25 independent scientific problems. Single-check controls
are not competitive full-verification baselines and need not achieve correct
verdicts in every case. No target or tool setting is replaced based on results.

Then run exactly ten fresh model episodes: original and expanded menus for
each of the five cases. Alternate which menu runs first across cases. This
fresh original-menu control avoids treating the older 30-case Luna evaluation,
which used a differently worded prompt, as a matched causal control.

- Model `gpt-5.6-luna`, reasoning `high`; no substitution.
- Five scientific credits per episode; fresh conversation and purchases.
- Maximum 30 responses, 30 tool requests, 32,768 output tokens per response,
  and five minutes per episode.
- **$2 total for the whole ten-slot batch**, not $2 per case. Reserve the next
  request's input and maximum output cost before generation; unknown billing
  retains its reservation. An attempted slot is never retried automatically.
- Existing streaming Responses transport, standard service tier, `store=false`,
  sequential calls, full history, summaries and opaque encrypted reasoning replay.

[Official Luna documentation](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
and [pricing](https://developers.openai.com/api/docs/pricing) were rechecked on
12 September 2026. Standard short-context rates are $0.20/M input, $0.02/M cached
input, $0.25/M cache writes and $1.20/M output. The existing conservative reserve
uses $0.25/M input plus output allowance and rejects input over 256,000 tokens.

Only explicit live mode loads the existing credential privately. Tests and CPU
commands never access it. Raw requests, responses, streamed events, numerical
artifacts, explanations and private evaluations remain in unique ignored run
directories. Logs include API-visible reasoning summaries, not raw internal
reasoning. Model context excludes seeds, categories, private reference data
and baseline outcomes. Independent resume of batch-funded episodes is blocked.

## Reporting and reproduction

Report each case's verdict, correctness, coverage/abstention, incomplete status,
credits, extra-tool requests, runtime and API accounting. Tool calls are not
automatically classified as wasted effort: an added action may help. Five
pairs with one generation per condition support only a descriptive comparison,
not a precise estimate of a menu effect or general scientific competence.

```powershell
python -m unittest discover -s tests -p test_verification_alternatives.py -v
python -m budgeted_science.agents.verification_alternatives_catalog --cpu
python -m budgeted_science.agents.verification_alternatives_catalog --dry-run --prepared PATH_TO_CPU_RUN
python -m budgeted_science.agents.verification_alternatives_catalog --live --prepared PATH_TO_CPU_RUN
python -m budgeted_science.agents.verification_alternatives_catalog --render PATH_TO_SAVED_RUN
```

CPU preparation freezes cases, source hashes and tool hashes. Live execution
requires that freeze still match; no source changes are allowed between slots.
Offline rendering verifies saved JSON/JSONL integrity and event/result
consistency without executing tools, solvers or API calls. The dry-run uses
scripted responses, not model inference, and incurs zero real API expenditure.
