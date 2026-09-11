# Two-parameter Burgers development trial

## Implemented scope

This opt-in CPU trial adds unknown initial amplitude `A in [0.8, 1.2]` alongside
viscosity `nu in [0.1, 0.3]`. Calibration starts from `A*sin(x)`; forecasting
starts from `1.5*A*sin(x)`. The factor 1.5 is known and the same unknown A applies
to both experiments. This is a known relative change in initial excitation, not
a fresh independent amplitude to infer for the unobserved forecast.

The equation, periodic domain, sensor/time menu, numerical schemes, three grids,
and final 16 forecast positions remain unchanged. The independent reference is
extended to the same amplitudes. The score remains actual-profile RMSE divided
by the **fixed public scale 1.5**, never by the hidden amplitude. Observations
still cannot choose candidate parameters or access the forecast experiment.

`SolverConfig(..., initial_amplitude=A)` and
`ReferenceOracle(..., initial_amplitude=A)` opt into the extension. Planning
evaluation accepts `score_planning(profile, target_nu, target_amplitude=A)`.
Every default remains A=1, including the existing planning/inference facades
and logged agent runner. This trial does **not** update their prompts or tools,
add arbitrary Python execution, or introduce incremental fitting actions.

The new `joint_fitting.fit_viscosity_amplitude` is an ordinary bounded SciPy
least-squares helper with an injected, metered candidate predictor. It starts
at the public midpoint `(0.2, 1.0)`, searches normalized parameter coordinates,
and counts every forward call, including finite-difference Jacobian evaluations.
An interrupted fit retains its best completed candidate without claiming
convergence. Candidate computation, including failed/interrupted work, uses the
existing ledger. Normalization stays at 16,512 work units per credit, defined
by the original public A=1 calibration solve.

## CPU trial results

Private development target: `nu=0.23, A=1.1`, noise seed 0. Every policy receives
an independent 20-credit ledger, pays two credits per acquired five-time record,
and observes Gaussian noise with standard deviation 0.01. Equal sensor/replicate
queries have paired noise. Policies do not receive target parameters or scores.
All four submit their own resolution-64 forecast at their best completed fit.

| Fixed recipe | Fit calls used / cap | Fit termination | Total credits | Normalized forecast RMSE |
| --- | ---: | --- | ---: | ---: |
| Sensor 2; fit at N=32 | 30 / 48 | Converged | 6.51938 | 0.05810635 |
| All three sensors; fit at N=32 | 24 / 48 | Converged | 9.88372 | 0.04882008 |
| Sensor 2; fit at N=64 | 12 / 12 | Evaluation limit | 13.72093 | 0.02228009 |
| All three sensors; fit at N=64 | 12 / 12 | Evaluation limit | 17.87597 | 0.01812009 |

These are fixed-recipe feasibility checks, not strong or optimal baselines.
Coarse/medium fitting use different call caps, chosen for this development
smoke, so the table is not a controlled resolution-only comparison. Incomplete
fits can still produce complete, scoreable forecasts. Smaller user-selected
budgets retain incomplete outcomes without fabricating a submission.

Reference grids 1,024 versus 2,048 agree within `7.50e-10` across the configured
outputs at nu in {0.1, 0.2, 0.3}, A in {0.8, 1.0, 1.2}, and both protocols.
Noise-free reference-based fitting recovers `(nu,A)` equal to `(0.14,0.9)`,
`(0.20,1.0)`, and `(0.26,1.1)` with maximum absolute errors `1.06e-13` in nu
and `6.49e-14` in A. This demonstrates numerical recoverability at these test
points, not global identifiability or recovery under noisy, restricted tools.
Reference-based fitting is a diagnostic, **not a matched 20-credit baseline**.

Tests cover decreasing candidate errors on grids 32/64/128 at the extended
parameter-box corners, initial conditions, mass conservation, energy decay,
amplitude-sensitive caching, charged interruptions, observation privacy,
scoring, fitting limits and artifact preservation. All 110 tests pass:
96 under `tests/` and 14 under `demos/planning/tests/`, including the original
40 foundation, 42 runner and 12 allocation-pilot tests.

## Reproduce and inspect

After the existing editable install, from the repository root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m unittest discover -s demos/planning/tests -v
.\.venv\Scripts\python.exe demos/planning/src/two_parameter_pilot.py
```

The trial prints the report path in a new, ignored
`tmp/burgers_two_parameter/<timestamp>-<id>/` directory. It never overwrites an
existing output directory. Optional `--viscosity`, `--amplitude`, `--seed`,
`--noise`, `--budget` and `--output` configure local development runs. There is
no live/API mode or credential loading. Outputs include a manifest with private
instance settings, Python/NumPy/SciPy versions and source hashes; reference and
recoverability checks; a readable summary; and each policy's complete numerical
trace, purchased records, spending, submitted profile and private evaluation.

Measured with Python 3.13.5, NumPy 2.3.4 and SciPy 1.16.1. Raw outputs include
private truth and are not suitable for an agent workspace or public release
without review. Source hashes in each manifest identify its exact implementation.

## Interpretation and next step

The added parameter gives the fitter another unknown to determine while leaving
the physical solver small. These checks establish an executable, scoreable toy,
not that it is harder for agents or that adaptive resource allocation helps.
Do not compare this table directly against the earlier A=1 one-parameter agent
trace as evidence of increased difficulty: the target and policy also differ.

A subsequent experiment should use paired parameter/noise instances and competent
classical joint-fitting policies, including coarse-to-fine fitting, before drawing
conclusions about planning. Numerical parameter bias and forecast-error
cancellation remain possible; scoring actual predictions permits them.

The sinusoidal family still permits fast Cole-Hopf analysis. A future coding
track must accommodate that lawful shortcut and separately isolate private
reference state. Extra parameters do not make expensive simulation unavoidable.
No paid agent run, new model bank, proposal-document change or API-limit change
is included in this trial.
