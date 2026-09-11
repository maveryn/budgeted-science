# Shared CPU foundation

`budgeted_science` is installable from the repository root with `pip install -e .`.
It uses Python 3.10+, NumPy, SciPy, and standard-library tests. Shared code never
imports a demo. Planning and inference each own an episode ledger, purchased
records, and submission; only a deterministic backend cache may be shared.

## Independent resource-planning toy

The opt-in `harder_config()` adds doubled range widths, 1%-of-initial-scale
Gaussian observation noise, and 5% tolerance. `local_policy` implements the new
paid-data-only multistart local least-squares control; `harder_pilot` runs the
development budget sweep and frozen noisy comparison. V1 defaults remain intact.
See [v2 results](../docs/resource_planning_v2_results.md). Noise-aware GP updates
include the declared sensor variance separately from numerical regularization.
`ResourceRunConfig(environment_version="v2")` selects the same environment in
the logged agent adapter; prompts, fitting, comparisons, and resume all retain
the noisy contract. See the [first v2 agent run](../docs/resource_planning_v2_agent_run.md).

`budgeted_science.resource_planning` contains the CPU predator-prey environment,
flat-credit accounting, protected observations, shared multifidelity GP fitter,
two GP baseline policies plus the local-fitting control, supervised experiment
runner, and offline reports. It does not import Burgers or use its work-to-credit
conversion. The only reused
agent utility is SDK-independent durable local logging.

Use `Episode(...).tools` for public actions and keep `Episode.evaluate()` private.
The environment allows arbitrary times, while the baseline GP uses a fixed
16-time grid. Every parameter must meet its relative tolerance: the primary
continuous error is the maximum normalized parameter error, not its mean.
See the [full contract](../docs/resource_planning_toy_protocol.md) and
[measured pilot](../docs/resource_planning_toy_results.md).

The optional `agents.resource` adapter exposes the 16-time subset, the same GP
fitter over purchased evidence, and parameter-vector submission to a logged model.
It reuses the API/history/spending engine with task-specific prompt and reporting
hooks. The scientific package itself still requires no OpenAI SDK. See the
[agent-run protocol](../docs/resource_planning_agent_run.md).
Resource-specific JSON checkpoints restore purchased trajectories and evidence
without solver reruns. Explicit agent resume also restores conversation, fit and
call-ID caches, and cumulative scientific/API ledgers; see the protocol for the
supported finalized-interruption recovery path and authorized ceiling overrides.

## Restricted viscous-Burgers system

The current family solves `u_t + u*u_x = nu*u_xx` on periodic `[0, 2*pi)`, with
`nu` in `[0.1, 0.3]` and final time 1. Calibration starts from `sin(x)`;
forecasting starts from `1.5*sin(x)`. Candidate grids are 32, 64, or 128 points.
Records contain times 0.2, 0.4, 0.6, 0.8, and 1.0 (simulation results also include
the initial state). Values are nodal samples on `x_i = i*2*pi/N`, not cell averages.

The opt-in amplitude extension accepts `SolverConfig(..., initial_amplitude=A)`
with A in `[0.8, 1.2]`. Initial conditions become `A*sin(x)` and `1.5*A*sin(x)`.
The default A=1, original cache keys, credit normalizer, and existing facades
remain unchanged. See the [two-parameter CPU trial](../docs/burgers_two_parameter_trial.md).

The conservative Rusanov flux and centered diffusion use SSP-RK2. Each step is
the smaller of time remaining to the next record and
`0.4 / (max(abs(u))/dx + 2*nu/dx**2)`. The direct solver also accepts a smaller
positive safety factor in `SolverConfig`; facades use the default. Candidate
results distinguish `completed`, `budget_exhausted`, and `numerical_failure` and
report completed steps/time, recorded fields, RHS work, charged work, and timing.

The independent reference transforms the problem to the heat equation with
`psi(x,0)=exp(A*(cos(x)-1)/(2*nu))`, evolves Fourier coefficients, and evaluates
`u=-2*nu*psi_x/psi` at the requested positions. Validation compares 1,024 and 2,048
reference points. See the [Cole-Hopf derivation](https://math.nyu.edu/~tabak/PDEs/The_Burgers-Equation.pdf),
section 6.3. This is also a fast analytic-computation route available in principle
to a coding-enabled agent: this toy demonstrates controlled tool contracts, not
the unavoidable expense of simulation.

## Interfaces

Modules live under `budgeted_science.burgers`:

| Interface | Contract |
| --- | --- |
| `config.SolverConfig`, `numerics.solve_candidate` | Candidate viscosity, grid, and protocol to fields/status/work. Optional ledger enforces a cap during execution. Omitting it is for offline diagnostics. |
| `cache.SimulationService` | Episode-local purchases plus optional shared `SimulationCache`; the metered candidate prediction backend. |
| `observations.ObservationService` | `acquire(sensor_id, replicates=1)` buys trials; `retrieve(record_id)` returns an already purchased immutable record for free. |
| `fitting.fit_viscosity` | Inject `predictor(nu, acquired_records)` returning a `(records, 5)` array; bounded fit retains the best completed result if interrupted. |
| `joint_fitting.fit_viscosity_amplitude` | Opt-in Python helper with injected `predictor(nu, A, acquired_records)`; counts all forward calls, including numerical Jacobian evaluations. Used by `AmplitudePlanningTools` in the two-parameter runner. |
| `tools.AmplitudePlanningTools` | Opt-in planning facade with candidate amplitude in `simulate` and joint `fit`; the same actions, accounting and profile submission as planning. |
| `tools.PlanningTools` | `observe`, `record`, `budget`, `simulate`, `fit`, `submit`; adjustable candidate resolution. |
| `tools.InferenceTools` | `observe`, `record`, `budget`, `predict`, `fit`, `submit`; only pre-registered fixed predictors, with no adjustable-solver/reference action. |
| `reference`, `scoring` | Trusted evaluator-side reference and final scores. Never exposed by tool dispatch. |

Fitting has a declared maximum number of predictor evaluations; its statuses are
`completed`, `evaluation_limit`, `budget_exhausted`, and `numerical_failure`.
Predictors are responsible for charging underlying computation. Both facades use
the metered service; arbitrary injected callbacks are not automatically metered.
Best-fit summaries can survive incomplete attempts, but no incomplete simulation
is treated as a complete calibration record or forecast. Fit orchestration,
small-array post-processing, and dispatch overhead are not included in the work
proxy; this milestone does not meter arbitrary user code.

The `FixedNumericalPredictor` registry is currently a resolution-locked numerical
**contract fixture**, not a trained or validated complementary surrogate bank.
Its fixed resolution cannot be overridden through inference dispatch. Future
model-bank adapters and their cost contracts remain to be implemented.

## Observations and costs

Sensor IDs 0, 1, and 2 correspond to `pi/4`, `pi/2`, and `3*pi/4`. One acquisition
buys all five calibration-time readings at one sensor from the same fixed hidden
target. Default noise is independent Gaussian with standard deviation 0.01;
`noise_std=0` is a diagnostic mode. Acquisition accepts neither a candidate
viscosity nor a forecast protocol. Prediction at a candidate parameter and
observation of the fixed target are distinct operations.

Noise streams depend on a private instance seed, sensor, and replicate index.
Equivalent trials have identical values regardless of query order or batching.
Repeats are new paid trials, including in noise-free mode. Record IDs are assigned
in purchase order and need not match between differently ordered episodes.

- Work proxy: `N * RHS evaluations`, not measured FLOPs. The canonical public
  calibration solve at `nu=0.2, N=64, safety=0.4` costs **16,512 work units**,
  defining one credit independently of the hidden target. A regression test
  checks this normalization.
- A sensor record costs two credits by default; `record_price` is configurable.
  This is an illustrative price, not a measured laboratory/computation exchange rate.
- `Ledger.shared(total)` creates one pool. `Ledger.separate(observations,
  computation)` creates two non-fungible caps. `Ledger.unlimited()` is for
  offline diagnostics only. Budgets and prices are capabilities, not a finalized
  benchmark configuration.
- Each attempted RHS evaluation is charged before execution. A cap can interrupt
  between RK stages; attempted failed work is retained. Invalid requests cost
  nothing. Observation batches are atomic: an unaffordable batch produces no
  records, no charge, and no consumed replicate indices.
- Reusing a complete purchased deterministic solve within an episode is free.
  A backend cache hit in a new episode costs the full scientific work. If that
  full result is unaffordable, the normal bounded solver path runs to preserve
  cold/warm partial fields, status, and charges. Wall times may differ and cached
  ledger debits are batched; scientific outputs and total charges do not.
- Only completed solves are cached. The key includes full numerical configuration
  and solver version, with exact floating-point identities. Interrupted runs are
  not resumable in v1; retrying them pays for attempted work again.

## Submissions and privacy

Planning submits 16 forecast values at `x_j=(j+0.5)*2*pi/16`, final time 1.
Its score is the actual submitted profile's RMSE against the noise-free target
reference, divided by fixed public scale 1.5. Scoring never replaces that profile
with a perfect calculation using an estimated parameter.

For the two-parameter CPU trial, the private reference accepts
`initial_amplitude=A`, and scoring uses `score_planning(profile, target_nu,
target_amplitude=A)`. The normalization remains the fixed public scale 1.5;
it does not change with the private amplitude. Existing inference scoring stays
viscosity-only at A=1.

Inference submits a viscosity in `[0.1, 0.3]`. The private evaluator uses that
viscosity to compute a reference forecast at the same positions and reports
normalized response RMSE and absolute viscosity error separately. Lower errors
are better; neither contract uses a subjective judge or a success threshold.

The trusted host constructs services with hidden target parameters and seeds.
Only allowlisted dispatch responses go to an agent. These omit private target
parameters, seeds, unpurchased readings, and evaluator scores. The Python objects
and local files are **not a security sandbox**; do not expose this process, source
state, backend cache, or validation artifacts as an arbitrary-code workspace.

## Reproduction

After the root editable install, run from the repository root:

```powershell
python -m unittest discover -s tests -v
python -m budgeted_science.burgers.validate
```

The validator writes evaluator-only CSV/JSON/Markdown, two scripted traces, and a
cache under ignored `tmp/burgers_foundation/`. Use `--output` to choose another
private directory. [Measured results](../docs/burgers_foundation_results.md)
describe the numerical milestone. That validator includes no API agent, trained
bank, adaptive-allocation comparison, or model-discrepancy correction.

## Optional agent integration

`budgeted_science.agents` adds a logged planning adapter, frozen first-run settings,
separate API-dollar reservations, streaming Responses integration, a scripted fake
gateway and offline transcript/report regeneration. It does not modify the
numerical methods or the inference facade. OpenAI imports and credential loading
are deferred until an explicitly requested live run; `pip install -e '.[agents]'`
installs the optional SDK. Base numerical tests and the dry-run need no SDK/key.

The adapter adds free `simulation_record(result_id)` retrieval, compact numerical
tool replies, complete per-fit solver logging and duplicate-call protection.
All replayable output fields and available reasoning summaries are preserved in
API history; complete returned objects, including response-only metadata, remain
unchanged in the raw archive.
There is no arbitrary-code environment, and local raw records include private
evaluator state. See the [runner protocol](../docs/planning_agent_runner.md).
