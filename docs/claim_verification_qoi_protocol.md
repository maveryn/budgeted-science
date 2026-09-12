# Claim-specific predator-prey verification: CPU revision

This opt-in revision keeps the existing predator-prey system and audits completed
numerical studies. It does not alter earlier catalogs, policies, model tools, or
saved results. No model/API integration is included in this milestone.

## Scientific contract

The unchanged equations are

`x' = a*x - b*x*y - 0.01*x*x; y' = 0.9*b*x*y - c*y`,

with initial state `(10,5)`, horizon `[0,8]`, and parameter bounds
`a in [0.6,1.4], b in [0.04,0.12], c in [0.8,2.0]`. Parameters are fixed within
each study and are harness-private. This is numerical verification of this
mathematical model, not physical validation or parameter inference.

Each episode audits one original printed claim:

| Quantity | Original analysis | Claim tolerance |
|---|---|---|
| Peak prey population | Maximum of stored samples | 1% or 5% relative |
| Peak time | Earliest time of the largest stored sample | 0.04 or 0.16 absolute time units |
| Cumulative prey population | Trapezoidal integral on the actual stored time grid | 1% or 5% relative |

The private label is whether the value printed to ten significant digits meets
its tolerance against the independently checked reference. The agent may ACCEPT,
REJECT, or ABSTAIN. Correct binary verdicts, false acceptance/rejection, coverage,
abstention, incompletes, and spending are reported separately. Explanations are
retained but not semantically graded. A defective numerical process can still
yield a valid particular claim; labels follow the claimed quantity, not defects.

Reference calculations use DOP853 and Radau at `rtol=1e-11, atol=1e-13`.
An augmented state integrates `z'=x`; independent dense-output quadrature checks
the integral. Derivative roots are bracketed on 4,097 and 8,193 points, refined,
and compared with both endpoints. Required agreement is below `1e-7` relative
for height/integral and `1e-6` absolute for time. These are independently checked
numerical references, not mathematical certificates.

Peak-time claims require a unique interior maximum, at least `1e-4` relative
height separation from competing maxima/endpoints, and at least `1e-7` relative
drop at both offsets `+/-0.02`. Ineligible timing claims are explicitly omitted;
their systems are not replaced. Actual transient regimes are recorded, without
claiming this model generates arbitrarily fast or sustained oscillations.

## Checks and accounting

`run_check(method, dt, output_step, output_offset)` reruns the fixed physical
setup using Euler or explicit-midpoint RK2. Integration steps range from `0.01`
to `0.32` and must divide 8. Output spacing ranges from `0.01` to `2`; offsets
are fractions of the output spacing in `[0,1)`. Endpoints are always included.
Both methods use their own piecewise-linear numerical interpolation; denser
output cannot recreate features absent from the integration trajectory.

The episode has **8 credits**, with

`credits = (attempted RHS evaluations + completed output samples) / 100`.

This is a declared synthetic work proxy, not measured FLOPs, runtime, monetary
cost, or the old flat-check credit system. Output samples are explicitly priced;
the relative price is a task assumption, not a realism claim. A full successful
check must fit the remaining budget before execution. Invalid requests are free;
failed computations are charged for performed work. Unknown interrupted work
retains its reservation and ends the episode. Backend cache hits do not waive
scientific charges; already purchased configurations are free within an episode.

Original reports, logs, trajectories, and analysis records are free to inspect.
Free actions quote costs, retrieve purchased runs, recompute quantities from
stored samples, compare those quantities, and read the ledger. No tool exposes
the private reference, target parameters, evaluator label, or internal unsaved
integration nodes. This is trusted-process separation, not a code sandbox.

## Frozen case generation

- Development systems: seeds `7300-7302`.
- Prospectively chosen fresh systems: seeds `7400-7405`.
- Uniform parameters within the unchanged bounds; no measurement noise.
- Original profiles: Euler `(dt=.16, output=.4, offset=0)`; Euler
  `(.04,.8,.25)`; RK2 `(.16,.4,.5)`.
- Every complete, finite, nonnegative original yields all three quantities at
  both tolerances, except explicitly ineligible peak-time claims.
- Three factually equivalent report formats, assigned by `(seed+profile+quantity)%3`.
- No selection by reference error, verdict label, or baseline performance.
- Opaque public identifiers; a saved private map preserves physical-study pairs.

This permits at most 54 development and 108 fresh claims. Claims share 9 physical
systems, and the six claims from an original study share its numerical output.
They are not independent trials. Every policy/claim episode has an independent
budget. Policy seed 0 is fixed across all cases, independent of hidden identities.

## CPU comparisons

| Policy | Purchased check(s) |
|---|---|
| Fixed RK2 | `dt=.04, output=.04`, cost 6.01 |
| Fixed Euler | `dt=.02, output=.04`, cost 6.01 |
| Fixed dense-output RK2 | `dt=.08, output=.02`, cost 6.01 |
| Randomized | Seeded ordering of a fixed configuration menu; buy affordable unpurchased checks |
| Adaptive | Integration/sampling probes, then claim-specific discrepancy and refinement heuristics divided by cost |

All use the same purchased-data estimator. The resolution ranking is
`(dt/8)^p + (output_step/8)^s`, with `p=1` for Euler and `p=2` for RK2 for
height/integral; sampled peak time uses `p=1` for both methods. The sampling
exponent is `s=1` for peak time or `s=2` otherwise. It assumes comparable leading-error
coefficients. The primary estimate must come from an independent check, not
the original report verifying itself. Compatible same-method/output-schedule
coarse/fine pairs permit Richardson correction for height/integral only.
Sampled peak times are not extrapolated. These approximations are not certified
error estimates; method order alone does not validate the asymptotic regime.
Matching output schedules does not guarantee that interpolation-error coefficients
remain constant across timesteps, and extrapolation need not improve accuracy.

The adaptive policy is a transparent heuristic, not an optimal verifier or a
reproduction of a literature algorithm. It uses observed changes, not private
truth. The randomized schedule is fixed before target evidence is read; valid
numerical failures can change its remaining budget. All policies receive a
structured claim, so these comparisons do not test free-text understanding.

There is no requirement to spend the full budget and no spending penalty or
early-stopping bonus. All attempted episodes remain in correctness denominators.
Cooperative deadline checks surround tool calls and policy completion (300
seconds); late submissions cannot score successfully. CPU policies have 2,000
tool requests, including free menu quotes. No crash-resume is implemented here.

## Reproduce and inspect

From the repository root with the existing editable installation:

```powershell
.\.venv\Scripts\python.exe -B -m budgeted_science.claim_verification_qoi validate
.\.venv\Scripts\python.exe -B -m budgeted_science.claim_verification_qoi run
.\.venv\Scripts\python.exe -B -m budgeted_science.claim_verification_qoi run --development-only
.\.venv\Scripts\python.exe -B -m budgeted_science.claim_verification_qoi render PATH_TO_RUN
```

Every run freezes protocol, source hashes, and software versions before case
generation in a unique ignored `demos/claim_verification/runs/*-qoi-cpu-*` folder.
It retains separate public artifacts and private references, complete tool events,
full numerical runs, policy diagnostics, actual submissions, and private scores.
Offline rendering reads saved records only, including incomplete outcomes. It
never executes a solver, policy, or API request. Summary reports expose protocol
completion, source-freeze verification, expected/recorded counts, and unknown
accounting. Changing code during a pilot halts it rather than silently pooling
different implementations.
