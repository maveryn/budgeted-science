# Harder resource-planning toy and stronger classical baseline

## Result

Implemented and evaluated on 2026-09-11, CPU-only. The new local-fitting baseline
passed **28/40 fresh-target cases (70%)**, versus **0/40** for each GP baseline.
All 120 evaluation episodes submitted within their 40-credit budgets. During
this CPU milestone no LLM/API call was made and no credential file was read.
The original toy and saved agent results are retained as v1; these are separate
v2 experiments.

## Task changes

| Setting | Original v1 | Harder v2 |
|---|---|---|
| Parameter 1 range | [0.8, 1.2] | [0.6, 1.4] |
| Parameter 2 range | [0.06, 0.10] | [0.04, 0.12] |
| Parameter 3 range | [1.1, 1.7] | [0.8, 2.0] |
| Observation noise | None | Independent Gaussian, sigma_x=0.1 and sigma_y=0.05 |
| Success tolerance | Every parameter within 10% | Every parameter within 5% |
| Selected budget | 40 | **40**, after comparing 40/32/24 on development targets |

Noise standard deviations are 1% of the **known initial population scales** 10
and 5, not 1% of the unknown response at each time. This is disclosed to methods.
The free x/y observations at time 1 are noisy too. Initial conditions at time 0
remain exact. Noisy values are not clipped; this is an additive sensor-noise
model. A seed plus variable and exact time identifies a reproducible reading.
Reordering requests does not change equivalent readings. Repeated retrieval is
free and returns the same stored reading, not an independent replicate.

Dynamics, initial conditions, horizon, 16-time working grid, low/high numerical
methods, and prices remain unchanged: low solve 1, high solve 8, target scalar 12.
The high-fidelity model and target still share the same physical equations.
Scoring uses the submitted parameters, with no savings reward or confidence score.

The implementation is opt-in through `harder_config()` and the v2 CPU command.
`Config()` and the logged GPT runner retain v1 defaults. The subsequent opt-in
`--harder` agent adapter discloses the noise model, uses noise-aware fitting,
and compares all three baselines. See the separate
[v2 agent evaluation](resource_planning_v2_agent_run.md); this CPU pilot is unchanged.

## New classical baseline

The new `local` method uses **multistart bounded local least-squares with a
high/low-fidelity correction**, rather than the GP posterior mean:

1. Purchase midpoint and coordinate-perturbation low-fidelity trajectories.
2. Estimate local sensitivities from those trajectories; select one additional
   target measurement using a log-determinant information criterion.
3. Fit local affine response approximations from purchased simulations. Optimize
   them from up to three candidate starting points, then purchase low-fidelity
   simulations to test and refine the proposals.
4. Purchase one high-fidelity trajectory at the best current low candidate.
   Use the paired high-minus-low response as a locally constant correction.
5. Continue cheap local refinement, then submit a continuous fitted estimate.

At 40 credits it purchases 20 low solves, one high solve, and one measurement.
Acquisition **locations** adapt to results, but this baseline fixes those resource
counts. It is a stronger fitting control, not an optimal budget-allocation policy.
Its final interpolated estimate need not itself be simulated, just as an agent
may submit a calculated estimate. Every actual physical simulation passes through
the paid tool service; local approximation fitting and optimization are free
analysis of purchased data. It receives neither equations nor hidden parameters.

The bounded optimization uses SciPy's
[least_squares](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html).
The surrounding acquisition and fidelity-correction policy is an engineering
baseline, not a claimed reproduction of a published algorithm. It uses nearest
eight-point affine fits, up to three starts, normalized trust radius 0.3, initial
coordinate radius 0.2, and ridge 1e-8. These settings were frozen before evaluation.

The method also passed the original agent demonstration target under its original
noiseless bounds and 10% tolerance: worst normalized error 0.0381592, or **0.3816%**
largest relative error, at 40 credits. This is a post-hoc smoke test, not held-out
evidence. The original GP controls failed that target.

## Development budget sweep

Eight fresh development targets (seeds 5000-5007), two noise realizations per
target, and one deterministic policy seed were used at each budget. All 48 runs
completed. The selection rule was fixed before these runs: retain 40 unless the
local method passes at least 90%; then consider 32, and then 24 by the same rule.

| Credits | Successes | Success rate | Median worst normalized error |
|---:|---:|---:|---:|
| 40 | 9/16 | 56.25% | 0.71434 |
| 32 | 8/16 | 50.00% | 1.03043 |
| 24 | 2/16 | 12.50% | 7.46180 |

The selected budget remains **40**. The wider ranges, noise, and tighter tolerance
already make this nontrivial for the stronger baseline. Lower budgets are
implemented for subsequent controlled comparisons, not selected retrospectively
from evaluation results.

## Frozen fresh-target evaluation

Twenty previously unused targets (seeds 6000-6019), two paired noise realizations
per target, three policies: **120 episodes / 40 cases per policy**. The private
noise seed is derived from target seed and noise-replicate index, identically
across policies. Policy seed is zero. Development and evaluation targets are
disjoint. No method or configuration was retuned after examining evaluation.

Both GP controls use their existing algorithms with the declared observation
variance added to likelihood and hypothetical-update covariances. It is distinct
from numerical regularization. The random policy at 40 retains its original
12-low / 2-high / 1-measurement plan. The adaptive GP retains its existing
one-step expected uncertainty-reduction-per-credit criterion.

| Method | Successes | Median worst error | Mean worst error | Median runtime |
|---|---:|---:|---:|---:|
| Local least-squares | **28/40** | **0.37335** | **2.91013** | 0.273 s |
| Random acquisition + GP | 0/40 | 4.03289 | 4.20575 | 0.145 s |
| Adaptive GP | 0/40 | 3.87079 | 4.07720 | 3.575 s |

Errors are normalized by 5% of each true parameter; the maximum must be <=1 to
pass. All methods spent exactly 40 credits. There were no incomplete outcomes.
The local method has some large failures, hence its mean error is considerably
higher than its median. Its 70% success rate is not a claim that the task is easy
for every target or that the baseline is optimal.

The local-minus-GP success difference is 70 percentage points for either control;
a paired bootstrap resampling **targets**, retaining both noise realizations,
gives an interval of [50, 87.5] percentage points (2,000 draws). The effective
number of distinct physical targets is 20, not 40.

## Verification and saved records

**251 tests passed:** 237 shared tests plus all 14 planning-pilot tests. New checks
cover noisy free evidence, deterministic noise streams and free retrieval,
observation-seed checkpoint restoration, widened-domain numerical agreement,
5% scoring boundaries, noise-aware GP likelihood against direct covariance
calculations, exact paid-call accounting, local analysis without solver access,
budget caps, deterministic baseline replay, and complete local worker logs.

All eight corners of the wider box produce successful high and low solves.
Maximum high-fidelity disagreement with an independent Radau integration on the
working grid was **2.032e-8**, below 1e-6. Maximum low/high trajectory disagreements
across corners ranged from 0.1825 to 17.6592 population units. These are numerical
checks, not task-success metrics or claims about all possible interior inputs.

The 120-case design was complete and unique, with no budget violations. Paired
initial noisy evidence matched exactly. Development and evaluation summaries,
reports, and event logs were unchanged by offline regeneration. All **51 frozen
source/test/build hashes** matched development, evaluation, and the executed
checkout. Source-manifest digest:
`ed4449f4758c974f736a269b999355baecce67613f2d936d91521daffc592163`.
Software: Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1. Two spawned CPU workers;
single-thread BLAS settings per worker. Episode time limits are cooperative
300-second analysis limits, not a sandbox or hard process-kill guarantee.

Local, ignored records:

- [Development](../demos/planning/runs/resource_planning_v2/20260911T112631Z-development-2b8aabbd84/report.md)
- [Frozen evaluation](../demos/planning/runs/resource_planning_v2/20260911T112714Z-pilot-1dc68f3473/report.md)

Each campaign contains a manifest, source hashes, complete chronological events,
per-episode private configuration, purchases, full numerical artifacts, fitting
and acquisition diagnostics, submissions, and private scores. Raw records contain
private targets and stay untracked. Neither original proposal files nor earlier
raw runs were modified.

## Reproduction

From the repository root with its editable package installed:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m unittest discover -s demos/planning/tests
.\.venv\Scripts\python.exe -m budgeted_science.resource_planning.harder_pilot development
.\.venv\Scripts\python.exe -m budgeted_science.resource_planning.harder_pilot pilot --freeze <DEVELOPMENT_DIR>
.\.venv\Scripts\python.exe -m budgeted_science.resource_planning.harder_pilot render <RUN_DIR>
```

Development writes `freeze.json` only when every development attempt completes
and the source has not changed. Pilot execution checks code, runtime, settings,
and public configuration against that freeze before generating evaluation targets.
Repeat invocations create new run directories. Rendering uses saved events only.

For a single offline case, create `Episode(theta, harder_config(), noise_seed=...)`
and pass only `episode.tools` to `run_local_policy`; keep the episode and evaluator
private. This is trusted-process separation, not protection from arbitrary Python
introspection. This CPU pilot alone makes no claim about GPT performance; the
subsequent single-agent evaluation is reported separately above.
