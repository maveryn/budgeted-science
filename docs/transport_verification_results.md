# Transport verification: small CPU demonstration

Completed 2026-09-12. The implementation works, but this first PDE catalog
**still admits a perfect fixed audit rule**. Moving from an ODE to a PDE did
not, by itself, establish an adaptive-verification challenge. No model/API calls,
credentials, proposal edits, or changes to earlier scientific environments.

## Results

| CPU policy | Correct | False acceptance / 6 invalid | False rejection / 6 valid | Mean credits |
|---|---:|---:|---:|---:|
| Balanced fixed rule | 12/12 | 0/6 | 0/6 | 3.0065 |
| Space-focused fixed rule | 12/12 | 0/6 | 0/6 | 3.0065 |
| Time-focused fixed rule | 9/12 | 1/6 | 2/6 | 3.0039 |
| Output-focused fixed rule | 12/12 | 0/6 | 0/6 | 3.0049 |
| Randomized affordable check, seed 0 | 12/12 | 0/6 | 0/6 | 2.0807 |

Only **12 distinct claims**, each evaluated by five policies: 60 CPU episodes,
not 60 independent scientific systems. All completed with binary verdicts;
no abstentions, incomplete outcomes or overspending. Each episode has its own
four-credit budget. Backend caching saves CPU time but not scientific charges.

The best tested fixed rule and a private-truth hindsight selector among the
four executed fixed checks both score 12/12: **zero selection headroom**.
Hindsight selection is not an adaptive policy or evidence of attainable agent
performance. No adaptive policy was evaluated. Randomized performance uses one
policy seed, not an estimate over repeated randomized investigations.

## Physical system and claims

Dimensionless equation: `c_t + v*c_x = D*c_xx - k*c`, periodic domain `[0,1)`,
time interval `[0,1]`. Initial condition: wrapped Gaussian centered at 0.25,
width 0.045, unit peak to numerical precision. Sensor location: 0.75.

We use `v=0.6`, `k=0.1`, and `D=0.0005, 0.003, 0.015`. Pulse-scale Peclet numbers
`v*width/D` are 54, 9 and 1.8: increasing diffusive influence, not three sharply
separated universal regimes. Physical coefficients are public in this new demo;
reference values, truth labels and case-selection metadata stay evaluator-side.
There is no parameter estimation, observation noise, physical validation or
paid real-world data acquisition. Existing predator-prey interfaces are unchanged.

Each system supplies one claim about each of:

- Maximum sensor concentration.
- Earliest time of the maximum of the saved sensor samples.
- Cumulative exposure, using trapezoidal quadrature of saved samples.
- First crossing of concentration 0.1, interpolated between saved samples.

The reference uses the continuous quantities, including continuous peak time.
Every claim specifies **3% relative accuracy**. Horizon stays fixed: extending
it would change the exposure being claimed, rather than refine that same quantity.
All selected reference events exist; a missing crossing in an audit calculation
produces no estimate and an abstention, not an invented event time.

## Small development catalog

Eight original configurations are executed per system: **24 candidate numerical
studies**, not hundreds of labelled tasks. They vary mesh, upwind/centered
advection, Euler/RK2 integration and output spacing. Actual numerical outputs
generate every report; the final answer is never artificially altered.

For each system/quantity pair, a predeclared alternating pattern requests a
valid or invalid claim. Valid cases have at most 2.4% error and are selected
nearest 1.5%; invalid cases have at least 3.6% error and are selected nearest
8%. Configuration order breaks ties. This yielded six valid and six invalid
claims. Selection uses reference errors, **never policy outcomes**, and avoids
the exact 3% decision boundary. It is not a sample of natural claim prevalence.

Reported numbers are printed to ten significant digits and scored literally.
Three short report wordings are assigned without using labels. CPU policies
receive structured claims, not a test of natural-language comprehension.
All twelve examples are developmental and share only three underlying systems.

## Numerical choices and tools

The solver has periodic first-order upwind or second-order centered advection,
centered diffusion, and Euler or two-stage SSP RK2 integration. The sensor is
on every allowed grid. Output fields use linear interpolation between actual
internal time steps. Denser output reruns that numerical calculation, rather
than interpolating only the sparse published data.

```python
run_verification(nx, dt, spatial_method, temporal_method, output_dt)
```

Free actions: `describe`, `quote`, paginated `inspect_existing_run`,
`recompute_qoi`, `compare_runs`, `budget`, and
`submit(verdict, evidence_ids, justification)`. There are no defect-labelled
buttons and no reference-query action. Grids: 32, 64, 128, 256, 512. Spacings
divide the horizon into 4 through 65,536 intervals. An exact Fourier-amplification
stability check for the selected linear discretization rejects unstable explicit
requests before execution. It checks stability, not solution accuracy.

Work credits are `nx * (RHS evaluations + saved output fields) / 16384`.
RK2 incurs two RHS evaluations per step. Output interpolation/storage also
costs proxy work. Upwind and centered methods use the same stencil weight.
This is **not measured FLOPs, runtime or money**. The default 64-point RK2 run
with 256 steps and 129 saved fields costs 2.50390625 credits.

Invalid/unaffordable requests do not execute or charge. Performed work on failed
solves is charged; uncertain execution retains the reservation and aborts the
episode. Identical purchased results and the original run are free to retrieve.
Cross-episode cache hits still charge, and duplicate call IDs cannot repurchase.
Early submission is allowed without a stopping bonus or expenditure penalty.

## What the classical controls do

Each rule buys one independently configured centered-space/RK2 run and compares
its estimate with the literal reported number. Original self-comparison is
excluded. All rules use the same affordable, stable configuration menu.

The balanced rule minimizes a public numerical-order proxy over spatial,
temporal and output resolution. The three focused rules multiply one proxy
term by 16. Configuration choices depend only on public physics, quantity type,
budget and original configuration, not observed numerical values or hidden truth.
Different rules can choose the same configuration. The random control selects
uniformly from that admissible menu with seed 0.

These are simple task-specific numerical controls, not optimal verifiers,
literature reproductions or certified error-bound methods. No classical general
verifier for free-form scientific studies is claimed.

In the weak-diffusion system, the time-focused rule chooses a 64-point mesh and
finer time/output resolution. The balanced rule instead chooses 128 points with
coarser time resolution. More temporal effort does not repair the former's
spatial error: it falsely rejects peak and exposure claims and falsely accepts
a crossing claim. Nevertheless the static balanced rule already gets every
claim right. This does not establish a causal advantage for adaptive reasoning.

## Numerical checks

The private reference is a translated, decaying, periodized Gaussian heat kernel,
checked independently against analytic Fourier coefficients with 128 and 256
modes in each direction. Continuous peak/event searches and quadrature are
repeated across representations, with 4,097/8,193-point peak-search brackets.
Maximum image/Fourier sensor disagreement is `3.33e-16`; maximum quantity
disagreement is `3.23e-9` in arrival time.

Maximum sensor-trajectory error in the dense-output mesh study:

| Diffusion D | nx=32 | nx=64 | nx=128 | nx=256 |
|---|---:|---:|---:|---:|
| 0.0005 | 0.32930 | 0.14137 | 0.03444 | 0.00839 |
| 0.003 | 0.08534 | 0.02310 | 0.00607 | 0.00156 |
| 0.015 | 0.00797 | 0.00206 | 0.00052 | 0.00013 |

Timestep decreases when needed for stability. Individual quantities need not
converge monotonically; weak-diffusion exposure provides a counterexample.
Mass follows the expected exponential decay with maximum absolute discrepancy
below `2.21e-9` in this sweep.

The 256-point validation runs cost about 32, 80 and 272 credits, beyond the
four-credit audit cap. **An expensive fine solve does not make the verdict
problem difficult:** cheaper checks already decide these 3% claims correctly.
These fine runs are not asserted to be minimum-cost or certified references.

One-axis mesh/timestep/output/scheme comparisons are retained as privileged
commissioning diagnostics. Unstable one-axis changes are excluded explicitly,
not silently modified along a second axis. They are not additive error
decompositions, dominant-defect labels, or evidence supplied to the policies.
Cancellation and justified confidence are not separately scored; an accurate
number by cancellation remains accurate under the stated truth contract.

## Scope and interpretation

The numerical environment, general tools, accounting and objective scoring are
implemented. **The proposed pre-LLM difficulty gate is not met.** Several fixed
rules and the one randomized control already score 12/12. This catalog should
not be used to claim a challenging adaptive-auditing benchmark.

The equation has cheap analytic solutions. Reference exclusion is a trusted-tool
contract, not an inherent computational barrier or a sandbox against arbitrary
Python. Explanations are preserved but not semantically graded. The twelve
claims are correlated development examples, not held-out independent systems.

## Logs and reproduction

Run: `20260912T054409Z-transport-cpu-b5aefbda0e`.

- [All results and 60 transcripts](../demos/claim_verification/runs/20260912T054409Z-transport-cpu-b5aefbda0e/report.md)
- [Frozen manifest and source hashes](../demos/claim_verification/runs/20260912T054409Z-transport-cpu-b5aefbda0e/manifest.json)
- [Numerical error/work table](../demos/claim_verification/runs/20260912T054409Z-transport-cpu-b5aefbda0e/numerical_validation.json)
- [One-axis diagnostics](../demos/claim_verification/runs/20260912T054409Z-transport-cpu-b5aefbda0e/axis_diagnostics.json)

Saved material includes commissioning trajectories, public/private study data,
chronological requests and exact responses, charges/cache events, purchased
full fields, submissions and evaluations. Raw data remain local and ignored.
Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1. **542 tests pass**: 528 repository tests
(including 21 new transport tests) plus 14 preserved planning-pilot tests.

```powershell
.\.venv\Scripts\python.exe -B -m budgeted_science.transport_verification.experiment validate
.\.venv\Scripts\python.exe -B -m budgeted_science.transport_verification.experiment run
.\.venv\Scripts\python.exe -B -m budgeted_science.transport_verification.experiment render demos\claim_verification\runs\20260912T054409Z-transport-cpu-b5aefbda0e
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_transport_verification.py -q
```

Rendering reads saved logs without executing solvers, policies or APIs. Run
creates a new unique directory. CPU episodes have a 30-tool-call limit and
cooperative five-minute deadline. Crash-resume and live model integration are
not included. No previous numerical experiments were overwritten.

For numerical context, Clawpack has a [periodic Gaussian advection
example](https://www.clawpack.org/gallery/pyclaw/gallery/advection_1d.html).
This demo is an independent finite-difference implementation adding diffusion
and decay, not a Clawpack reproduction or a claim to CFD realism.
