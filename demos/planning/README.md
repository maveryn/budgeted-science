# Resource-rational scientific project planning

**Status:** the CPU allocation pilot and shared numerical foundation are preserved.
A complete single-episode agent runner now passes offline checks and includes an
independently budgeted fixed-policy CPU comparison. The first paid attempt ended
after one model response, before submission, because second-turn token counting
rejected response-only metadata. The local run is retained; the replay projection
is now covered by offline tests. There is no scored LLM result, and the scripted
fake-model result is not an agent-performance result.

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
