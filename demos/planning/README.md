# Resource-rational scientific project planning

## Harder predator-prey toy (v2)

The new CPU setup uses wider parameter ranges, Gaussian noise on all noninitial
observations (including free time-1 readings), and a 5% parameter tolerance.
The stronger local-fitting baseline passed 28/40 fresh paired-noise cases versus
0/40 for each GP control. A development sweep retained 40 credits. See the
[v2 results and protocol](../../docs/resource_planning_v2_results.md).

```powershell
python -m budgeted_science.resource_planning.harder_pilot development
python -m budgeted_science.resource_planning.harder_pilot pilot --freeze <DEVELOPMENT_DIR>
```

Use `harder_config()` for individual CPU cases. Add `--harder` to the logged
agent command for v2; omitting it preserves v1. One GPT-5.6 Sol/high v2 episode
completed 40/40 credits and passed (largest error 0.546%); the stronger local
baseline also passed (0.877%). See the [run audit and complete logs](../../docs/resource_planning_v2_agent_run.md).

```powershell
python demos/planning/src/run_resource_agent.py --dry-run --harder --api-ceiling-usd 3.00 --require-full-budget
```

The v2 runner discloses noisy observations and the 5% tolerance, uses the
noise-aware purchased-evidence fitter, and compares all three frozen baselines.
The full-budget flag discloses and enforces using all 40 credits. A paid `--live`
attempt needs explicit authorization; the $3 override is never automatic.
V2 logs live under ignored `runs/resource_agent_v2/`. Resume restores the saved
environment and noise seed without a new `--harder` flag.

Use `--scientific-budget 32` (or 24) for a lower-budget fresh v2 run; 40 remains
the default. Resume restores the saved budget and rejects a budget override.
The [32-credit follow-up](../../docs/resource_planning_v2_32_credit_run.md) passed
on the same instance: GPT's largest error was 3.035%, versus 4.700% for the local
baseline. This is one paired case, not a multi-target agent success rate.

The resource runner also supports explicit `--model gpt-5.6-luna`; Sol remains
the default. Both retain high reasoning and the same task interface, with
model-specific API price accounting. The [Luna 32-credit run](../../docs/resource_planning_v2_luna_run.md)
completed but failed the 5% tolerance (largest error 15.682%). A model cannot be
changed during resume, and there is no automatic fallback to another model.

## Preserved predator-prey resource-allocation toy (v1)

The new CPU-only implementation lives in the independent shared package
`budgeted_science.resource_planning`. It compares a randomized fixed allocation
against a one-step cost-aware GP policy: both pay for candidate simulations and
target evidence from one 40-credit pool. Scoring requires all three hidden
parameters to be within 10%; unused credits have no reward.

```powershell
python -m budgeted_science.resource_planning.validate --sparse-ambiguity
python -m budgeted_science.resource_planning.experiment --phase debug
python -m budgeted_science.resource_planning.experiment --phase development
```

Freeze the completed development run before generating pilot targets; exact
freeze, pilot, and offline regeneration commands are in the
[results](../../docs/resource_planning_toy_results.md). Read the
[protocol](../../docs/resource_planning_toy_protocol.md) for baseline assumptions,
paid warm starts, resource contracts, scoring, and limits. No API dependency,
credential, Docker container, or code-writing agent is used by these CPU baselines.

### Logged predator-prey agent

The separate `run_resource_agent.py` adapter gives GPT the same purchased-evidence
GP fitter while leaving all 40 credits available for its own choices. It uses the
16-time measurement grid and compares the submitted parameter vector against both
unchanged CPU policies. It does not use Burgers' profile-RMSE score.

```powershell
python demos/planning/src/run_resource_agent.py --dry-run
```

Read the [agent protocol and run audit](../../docs/resource_planning_agent_run.md)
before a paid run. `--live` starts exactly one GPT-5.6 Sol/high episode with a $2
API ceiling, 32,768 output tokens per response, 30 responses, and a 20-minute
deadline. Raw logs stay under ignored `runs/resource_agent/`; `--render RUN_DIR`
regenerates the transcript and report offline. No automatic retry or extra agent.

The first live attempt was interrupted by a provider-overload error after nine
low-fidelity simulations (9/40 credits), without a submission. It was not rerun.
It was subsequently explicitly resumed: the same episode used 40/40 credits and
submitted with worst normalized parameter error 0.00069321 (success threshold 1).
The original logs and unchanged baseline results are preserved. The user added
a full-credit requirement and authorized a $3 cumulative API ceiling for the final
response; see the linked audit. This is one instance, not a general model ranking.

Explicit resume is now available: add `--resume <RUN_DIR>` to `--live` to continue
the same episode and cumulative budgets. `--require-full-budget` records a user
instruction to spend all 40 scientific credits before submitting. Inspect recovery
offline with `--inspect-resume`. The original logs, purchases, API reservations,
and baseline results are preserved; see the audit for recovery safeguards.
After explicit authorization, `--resume-api-ceiling-usd 3.00` can raise the total
API ceiling without resetting prior usage; there is no automatic increase.

## Preserved Burgers and allocation work

**Status:** the CPU allocation pilot and shared numerical foundation are preserved.
A complete single-episode agent runner now passes offline checks and includes an
independently budgeted fixed-policy CPU comparison. The first paid attempt exposed
a replay-integration defect that is now fixed and covered by offline tests. A
post-fix attempt progressed for 11 responses and spent 19.17 scientific credits,
but generation 11 exhausted its 8,192-token response allowance entirely on
reasoning before submission. Both earlier runs are retained. The subsequent
two-parameter episode submitted successfully: normalized RMSE 0.01834 at 19.80
credits, versus 0.01812 at 17.88 credits for the fixed policy. See the
[completed-run audit](../../docs/planning_two_parameter_agent_run.md).
The scripted fake-model result is not an agent-performance result.

## Opt-in two-parameter CPU trial

The amplitude/viscosity extension uses calibration `A*sin(x)` and forecast
`1.5*A*sin(x)`, with unknown A in `[0.8, 1.2]` and nu in `[0.1, 0.3]`. It keeps
the original numerical methods, costs, and actual-profile scoring. Run locally:

```powershell
python demos/planning/src/two_parameter_pilot.py
```

This performs reference/recoverability checks and four independent 20-credit
fixed-policy trials, saving complete numerical traces to a new ignored
`tmp/burgers_two_parameter/` directory. No API access or credentials are involved.
The ordinary Python joint fitter is not an incremental agent action. The default
`run_agent.py` task remains one-parameter. An opt-in logged two-parameter task
uses the same seven actions, adds candidate amplitude to `simulate`, and makes
`fit` estimate both parameters. Its paired comparison uses three records,
an N=64 joint fit capped at 12 predictions, and an N=64 forecast.
See [measured results and limitations](../../docs/burgers_two_parameter_trial.md).

Verify the two-parameter runner without credentials or API calls:

```powershell
python demos/planning/src/run_agent.py --dry-run --two-parameter --max-output-tokens 32768
```

With explicit authorization for one paid run, replace `--dry-run` with `--live`.
The default response limit remains 8,192; the explicit 32,768 option was approved
for the first joint-parameter episode. High reasoning, the 20-credit pool, $2 API
ceiling, 30-response limit and 20-minute deadline remain unchanged. Larger
output reservations can stop a run before the full $2 is actually consumed;
the runner never sends a request whose maximum cost cannot be covered.

## First logged agent episode

From the repository root, after the editable numerical install:

```powershell
python demos/planning/src/run_agent.py --dry-run
```

Read the generated `prompts.json`, `tools.json`, `transcript.md` and `report.md`
under the unique ignored `demos/planning/runs/<run_id>/` directory. The raw JSONL
and numerical artifacts are complete; no paid API call or credential read occurs.

When explicitly authorizing one live episode:

```powershell
python -m pip install -e '.[agents]'
python demos/planning/src/run_agent.py --live --api-key-file openaiapi.txt
```

Settings: `gpt-5.6-sol`, high reasoning, 20 scientific credits, 2 credits per sensor
record, noise 0.01, and a separate $2 API ceiling. At most 30 model responses,
8,192 output tokens each including reasoning, and 20 minutes. No automatic retry,
model substitution, conversation truncation or extra closing narrative. Incomplete
outcomes are retained. API access and token counting must be available or the run
stops. Raw logs remain local and untracked.

Regenerate derived documents without API access or tool execution:

```powershell
python demos/planning/src/run_agent.py --render demos/planning/runs/<run_id>
```

See the [runner protocol and verification](../../docs/planning_agent_runner.md)
for the privacy boundary, complete records, fixed-policy comparison and pricing
assumptions. A single toy run cannot establish an adaptive-planning advantage.

## Five-case matched campaign

The campaign imports the completed 32-credit Sol/Luna case (seed 6000) and its
three CPU controls, then adds four preselected targets (6020-6023) with matched
noise. It includes Sol/high, Luna/high, local fitting, randomized acquisition
plus local fitting, and the existing random-GP/adaptive-GP controls. No changes
are made to physics, prices, tools, tolerance, or the full-budget requirement.

From the repository root:

```powershell
python -m budgeted_science.agents.campaign dry-run
python -m budgeted_science.agents.campaign prepare
python -m budgeted_science.agents.campaign live <PREPARED_CAMPAIGN_DIR>
python -m budgeted_science.agents.campaign continue <CAMPAIGN_DIR>
python -m budgeted_science.agents.campaign render <CAMPAIGN_DIR>
```

`dry-run` creates a separate scripted rehearsal on development seeds 5000-5003;
it reads no credentials and makes no API calls. `prepare` freezes the live case
list, imports, source hashes, settings, and alternating model order without
running any new solver. `live` requires explicit authorization for eight new
episodes, with $3 per episode and $24 maximum new spending. No allowance is
transferred between slots. CPU baselines run once per case, outside agent limits.

`continue` skips completed/imported slots and recovers finalized child records,
but never repeats an attempted episode. An ambiguous partial attempt requires
inspection. Explicit single-episode resume retains the original model, target,
conversation, and cumulative $3/32-credit limits; it is not another sample.
Systemic authentication, provenance, and accounting failures halt the campaign.

Each campaign has a unique ignored directory under `runs/resource_five_case/`.
Reports distinguish the imported exploratory case from the four newly selected
cases and preserve failed/incomplete outcomes. All API-visible logs and returned
reasoning summaries are retained; raw internal reasoning is not available.

Individual fresh v2 runs also accept `--target-seed` and `--noise-replicate`
alongside `--harder`. Defaults remain 6000 and 0. These private selectors cannot
override a resumed run and are never included in agent inputs.

## Terra extension of the completed five-case campaign

The separate Terra campaign adds five fresh `gpt-5.6-terra`/high episodes on the
same cases, with identical scientific prompts, tools, noise and 32-credit budgets.
It imports the 30 completed Sol/Luna/classical results without rerunning them.
Each Terra episode has a $3 API ceiling; the extension permits five live slots
and at most $15 new spending. Standard-price reservations use $2.50/million
input tokens (including cache-write upper bound) and $12/million output tokens.

```powershell
python -m budgeted_science.agents.terra_campaign dry-run
python -m budgeted_science.agents.terra_campaign prepare
python -m budgeted_science.agents.terra_campaign live <PREPARED_TERRA_DIR>
python -m budgeted_science.agents.terra_campaign continue <TERRA_DIR>
python -m budgeted_science.agents.terra_campaign render <TERRA_DIR>
```

Preparation verifies prior artifact hashes and freezes the extension separately.
The offline rehearsal uses scripted responses on these already evaluated cases;
it reads no credentials and runs no new CPU comparison. Live mode needs explicit
authorization. Continuation never relaunches an attempted episode. Logs are
stored under ignored `runs/resource_terra_five_case/`; earlier logs remain intact.
Terra was added after the previous results were known, so this is a matched
extension, not a new held-out evaluation. The standalone runner also accepts
`--model gpt-5.6-terra`; existing defaults and resume constraints are unchanged.

The [completed extension and audit](../../docs/resource_planning_terra_results.md)
reports Terra 2/5, all five submissions at 32 credits, and a $1.69 total new API
cost upper bound. The original Sol/Luna/classical results remain unchanged.

## Shared Burgers planning contract

Infer a fixed target's viscosity from paid calibration records, then submit a
16-value forecast profile for a different initial amplitude. Evidence acquisition,
calibration fits, and forecasting draw from the configured ledger. Adjustable
32/64/128-point simulations provide candidate predictions; all underlying solves
used by fitting are metered. The submitted profile itself is scored, so accurate
parameter estimation does not automatically remove numerical prediction error.

The implemented facade is `budgeted_science.burgers.tools.PlanningTools`, with
`observe`, `record`, `budget`, `simulate`, `fit`, and `submit` actions. It shares
physical machinery with inference, not an episode or an objective. See the
[shared contract](../../shared/README.md) for defaults, pricing, and API details.

After `python -m pip install -e .` from the root in a virtual environment:

```powershell
python -m unittest discover -s tests -p test_burgers.py -v
python -m budgeted_science.burgers.validate
```

The validator exercises one fixed acquisition/fit/forecast script with a shared
50-credit budget. This checks the wiring, not a good allocation strategy or a
recommended budget. Numerical tables and the trace are written to ignored
`tmp/burgers_foundation/`; see the [foundation results](../../docs/burgers_foundation_results.md).

Next work includes selecting useful budget/price regimes, matched classical
policies, stopping/allocation diagnostics, and paid agents. No result currently
establishes that adaptive allocation helps in this restricted system, which also
permits fast Cole-Hopf computation. The foundation is not a finalized benchmark.

## Preserved allocation pilot

The initial executable toy is deliberately simpler than the transport-pulse idea
below: estimate three curve integrals under a shared computation budget. It has
equal-spend and adaptive-refinement baselines. A separate Monte Carlo
best-alternative-selection variant compares cost-aware OCBA, equal spending,
equal sample counts, and a variance-based allocator. These are different tasks;
OCBA is not presented as a quadrature algorithm.

From the repository root, using Python 3.10 or later and no extra packages:

```powershell
python -m unittest discover -s demos/planning/tests -v
python demos/planning/src/ocba_pilot.py
```

See the [protocol](../../docs/ocba_pilot_protocol.md) for assumptions, costs,
references and sensitivity commands, and the
[results](../../docs/ocba_pilot_results.md) for the measured outcome.
Generated episode records live under `runs/` and are ignored by Git.

## Earlier transport-pulse sketch (not implemented)

Use an analytic Gaussian transport pulse with hidden transport speed,
diffusivity, and mass. At a specified downstream location, estimate peak timing,
peak concentration, and cumulative exposure within disclosed time windows and
tolerances. Measurements can inform several objectives at once.

The agent chooses point readings, time series, spatial profiles, and numerical
analysis under one scientific budget. A later matched variant adds uncertain
sensor gain and a purchasable calibration measurement. Supply competent fitting,
peak search, integration, and uncertainty tools.

### Evaluation and controls for that sketch

- Submit one final answer or abstention per objective. Each answer within its
  tolerance earns one point; budget violations are invalid.
- Compare question-by-question allocation, a fixed shared purchase plan, and an
  adaptive shared plan using the same numerical estimator.
- Preserve lawful analytic/global-fit solutions. Shared calibration alone does
  not prove a need for adaptive planning; include an always-calibrate-first control.
- Keep hidden truth and endpoint scores private until the episode ends.

## Local structure and later work

- `src/`: environment, tools, baseline policies, evaluator, and demo entry point.
- `configs/`: public task settings, observation menus, budgets, and tolerances.
- `tests/`: analytic checks, resource enforcement, scoring, and leakage tests.
- `runs/`: generated local records and summaries; ignored by Git.

The baseline-only allocation pilot is complete and unchanged. The Burgers
structured-tool facade and logged API runner are implemented in the shared
package; paid runs, randomized experiment suites and broader numerical policy
comparisons remain future work. Neither implementation requires running the inference or
surrogate-development demos.
