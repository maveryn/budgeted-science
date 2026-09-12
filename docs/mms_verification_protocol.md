# Manufactured-solution verification: CPU development protocol

This is a separate implementation under `budgeted_science.mms_verification`.
It does not modify the predator-prey, Burgers, transport, forecast-support, or
previous claim-verification experiments. No model calls, SDK requirement,
credentials, GPU, or Docker are involved.

## What is being verified

For a completed numerical study, submit two independent verdicts:

1. Does the **original printed point value** have relative error at most 2%?
2. Does its implementation meet a **declared finite-grid near-second-order
   criterion** on the study-relevant manufactured-solution test?

The second criterion requires both RMS-error orders for 8 -> 16 and 16 -> 32
intervals per axis to lie in `[1.7, 2.3]`, inclusively. This is an operational
finite-grid claim, **not** proof of universal correctness or asymptotic order.
An implementation can fail it while the original point value is accurate.
A correct implementation can also produce an inaccurate coarse-grid value.

This distinction follows the separation of code and calculation verification in
[NASA's verification tutorial](https://www.grc.nasa.gov/www/wind/valid/tutorial/verassess.html).
The diagnostic design is motivated by manufactured-solution testing, including
feature activation and blind tests, in
[Salari and Knupp, SAND2000-1444](https://www.sandia.gov/research/publications/details/code-verification-by-the-method-of-manufactured-solutions-2000-06-01/).
We implement a small new toy, not a reproduction of NASA/Sandia test suites.

## Numerical system

Solve `-kappa*Laplacian(u) + vx*u_x + vy*u_y = f` on `[0,1]^2`.
Reaction is omitted in this first implementation.

| Diagnostic family | kappa | vx | vy | Boundaries |
|---|---:|---:|---:|---|
| Diffusion | 1 | 0 | 0 | All Dirichlet |
| Advection | 0.2 | 1.6 | 0.7 | All Dirichlet |
| Mixed | 0.6 | 0.4 | -0.2 | Left/bottom Dirichlet; right/top normal derivative |

These are modest coefficients: the largest directional cell Peclet number on
the coarsest grid is 0.5. This is not a strongly convection-dominated stability
test. Mixed-boundary data specify outward derivatives, **not diffusive fluxes**.
At left/bottom corners Dirichlet takes precedence. At the top-right corner the
two normal-derivative equations are summed.

The audited kernel uses a central five-point Laplacian, central advection,
second-order one-sided Neumann formulas, and SciPy sparse direct solution.
Controlled alternatives use first-order upwind advection or first-order
Neumann formulas. The independent kernel assembles the intended operator using
Kronecker products and separately constructed boundary rows. It does not call
the audited assembler, disable a fault flag in that assembler, or receive an
interior exact solution. Both kernels share SciPy's sparse linear solver; they
are not independently developed physical models or formal certificates.

Manufactured profiles are

`u = offset + ax*x + ay*y + axy*x*y + A*sin(fx*pi*x+px)*sin(fy*pi*y+py)`.

Forcing and boundary data are derived analytically. Offsets/phases and
noninteger frequencies avoid homogeneous-boundary and zero-curvature blind
spots. The diagnostic profile has `(offset,ax,ay,axy)=(1.1,0.2,0.35,0.15)` and
`(A,fx,fy,px,py)=(0.45,1.3,1.7,0.2,0.4)`.
The study profiles use the same polynomial part with:

| Study system | A | fx | fy | px | py |
|---|---:|---:|---:|---:|---:|
| Diffusion | .8 | 2.7 | 2.2 | .31 | .17 |
| Advection | .8 | 2.3 | 1.8 | .41 | .27 |
| Mixed | .7 | 1.6 | 2.4 | .13 | .37 |

Those study profiles and exact answers are **evaluator-side**. This developer
document and the experiment manifest are not auditor inputs. Diagnostics expose
their exact solutions and errors openly, as MMS requires. The study quantity is
`u(0.375,0.625)`, a common grid node at all allowed resolutions. RMS errors include
all nodes. Claims print ten significant digits; labels use that literal value.

Validation checks analytic derivatives using complex-step differentiation,
affine exactness including mixed corners, scaled algebraic residuals, sound
convergence, independent assembly agreement, and feature-inactive equivalence.

## Six deliberately selected development studies

| Study type | System | Audited kernel | Original grid |
|---|---|---|---:|
| Sound study | Diffusion | Central | 16 |
| Correct code, coarse study | Mixed | Central | 8 |
| Inaccurate advection study | Advection | Upwind | 8 |
| Inaccurate boundary study | Mixed | First-order Neumann | 16 |
| Accurate value despite failed order | Advection | Upwind | 16 |
| Inactive advection change | Diffusion | Upwind | 16 |

These share **three physical problems**, not six independent systems. The first
and last studies have identical numerical values/fields. Selection followed a
complete 3-system x 3-kernel x 4-grid numerical commissioning sweep, before
policy comparison. Truth is calculated from actual results, not mutation names.
All selected QoI errors are at least 0.5 percentage points from the 2% boundary.
The full sweep and selection are retained. Failed commissioning stops the run;
there is no silent substitution or widening of criteria.

## Public evidence and tools

Public material includes a short neutral report, intended equation/coefficient
and boundary information, the original grid and numerical field, forcing/BC
arrays at that grid, residual, point value, and the three-test MMS menu. Opaque
IDs do not reveal labels. Algorithms read structured metadata; report-language
understanding is not tested by these CPU policies.

| Action | Result | Price |
|---|---|---|
| `run_mms(family, grid, kernel)` | Diagnostic field, point value, exact-error norms | `(grid+1)^2/289` |
| `run_study(grid, kernel)` | Original physical problem's numerical field/point value; no exact error | `(grid+1)^2/289` |
| `record(result_id)` | Purchased full arrays | Free |
| `budget()` | Limit, spent, remaining | Free |
| `submit(qoi, order, evidence_ids, explanation)` | Two verdicts, no private score | Free |

`kernel` is `audited` or `independent`; grids are 8, 16, 32, 64. The default
is audited. The independent option is available to every policy. Full-field
artifacts are retained; ordinary solve responses omit the field array and give
its record ID. Re-reading the original result or any purchased computation is
free. New episodes pay even for backend-cached calculations. Invalid and
unaffordable requests are rejected without charge; executed failures retain
their charge and are cached. Call IDs deduplicate purchases. The purchase is
logged before numerical execution, so interruption cannot erase charged work.

One credit is 289 grid points. This is a **grid-size price proxy**, not FLOPs,
sparse-factorization work, calibrated CPU runtime, or dollars. Prices for grids
8/16/32/64 are approximately 0.2803/1/3.7682/14.6194. Actual runtime is separate.

Budgets are 10 and 20. Before policies run, commissioning verifies that the
three relevant MMS solves plus one independent study solve at 32 cost
**8.81661 credits** and give an adequate numerical check on every development
case: the independent 32-grid point error is below 0.5%, and its plug-in verdict
matches the analytical truth. This is executable-path feasibility on these
cases, not a generally certified sufficient budget. Testing all three families
and the independent study solve costs **18.91349 credits**. The same estimator
is used by the complete study-aware policy: its correct scientific answers are
therefore a commissioning invariant, assuming successful execution, rather
than independent evidence of policy performance.

## CPU policies

All use the same final estimator: compare the original report with the finest
purchased study check at grid 32 or higher; classify at 2%. This is a plug-in
comparison, not a validated error bound. Relevant audited MMS pairs determine
the separate order verdict. One failed pair refutes the conjunctive finite-grid
claim; accepting it requires both pairs. Irrelevant tests cannot certify it.

1. `study_refinement`: rerun the audited study at 16/32/64 when affordable.
   This **QoI-only partial-task control** abstains on order.
2. `fixed_diffusion`: always do diffusion MMS at 8/16/32, then independent
   study check at 32. A deliberately generic diagnostic control.
3. `fixed_suite`: fixed diffusion/advection/mixed MMS sequence, then independent
   study checks. Skip unaffordable purchases but continue to later affordable
   ones. All checks fit at 20 credits.
4. `study_aware`: choose mixed if mixed boundaries are active; otherwise choose
   advection if velocity is nonzero, else diffusion. Three relevant MMS grids,
   then an independent study check at 32. This is the **competent simple rule**.
5. `early_reject`: same study-aware rule, but omit the third MMS grid if the
   first pair already refutes the finite-grid criterion. Still perform the
   independent study check. This is limited response adaptation, not general
   experimental design.

Unused credits have no reward. Every policy has a separate ledger and a cold
numerical backend for timing comparability. Maximum 30 requests/five minutes.
Score QoI and order separately, plus both-correct counts; retain coverage,
abstentions, false acceptance/rejection with true/false class counts, incomplete
outcomes, spending, and runtime. Explanations are not semantically judged.

## Reproduction and records

From the installed repository environment:

```powershell
python -m unittest discover -s tests -p test_mms_verification.py -v
python -m budgeted_science.mms_verification.experiment validate
python -m budgeted_science.mms_verification.experiment cpu
python -m budgeted_science.mms_verification.experiment render <saved-run-directory>
```

Each CPU command creates a unique ignored `demos/claim_verification/runs/` folder.
The manifest freezes configuration, source hashes and dependency versions before
commissioning and comparisons. Public study artifacts, private analytical
references, numerical validation, full commissioning sweep, per-episode requests,
responses, arrays, charges, cache events, private scores, and transcripts are
retained. Source hashes are checked again on completion. Report regeneration
verifies all JSON/JSONL artifact hashes and reconciles submissions, charges,
evidence IDs and private scores against episode events and the catalog; it
never invokes tools or solvers. Interrupted batches retain a renderable summary
with attempted incomplete episodes separate from unattempted slots.
Crash-resume and automatic reruns are not implemented.

## Interpretation boundary

Success demonstrates separated verification claims and executable budgeted
checks. It does **not** establish a difficult agent benchmark, adaptive-policy
superiority, reliable confidence, physical validation, or arbitrary-report
understanding. A short study-aware rule may solve every case, and that result
must be retained. Manufactured forcing may support analytic shortcuts in a
future coding environment. This is trusted in-process separation, not a security
sandbox or a claim that these computations are unavoidably expensive.
