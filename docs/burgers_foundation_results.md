# Shared viscous-Burgers foundation: measured validation

Validated on 2026-09-10. This milestone implements the shared CPU numerical
environment and two distinct tool/scoring contracts. It does not compare agents,
planning policies, or trained imperfect models. The existing allocation pilot,
its results, and its 12 tests are unchanged.

## Configuration and verified contracts

- Periodic `u_t + u*u_x = nu*u_xx` on `[0, 2*pi)`, final time 1, viscosity
  range `[0.1, 0.3]`. Calibration IC `sin(x)`; forecast IC `1.5*sin(x)`.
- Rusanov conservative flux, centered diffusion, SSP-RK2, safety 0.4;
  grids 32/64/128. Record times 0.2/0.4/0.6/0.8/1.0, plus the initial field.
- Three calibration sensors at `pi/4`, `pi/2`, `3*pi/4`; a paid acquisition is
  one sensor's five readings. Default independent Gaussian noise is 0.01.
  Repeated trials are paid; retrieving an acquired record is free. Sensor/replicate
  noise is reproducible independently of query order and batch size.
- Final forecast positions are `(j+0.5)*2*pi/16`, `j=0,...,15`. Planning scores
  the actual submitted profile against the noise-free reference by RMSE/1.5.
  Inference scores the submitted viscosity's reference-generated forecast on the
  same grid/scale, and separately reports absolute viscosity error.
- The public canonical calibration solve at `nu=0.2, N=64` uses 16,512
  grid-point/RHS work units, defining one credit. Sensor records cost two credits
  by illustrative default. This is a work proxy, not measured FLOPs or a real
  laboratory exchange rate. Shared pools and separate acquisition/compute caps
  are supported, not prescribed as final experiment budgets.
- Invalid actions do not spend. Interrupted/failed RHS attempts remain charged;
  incomplete calculations cannot masquerade as complete predictions. Full backend
  cache hits are paid in new episodes; within-episode reuse is free. Warm/cold
  caches agree on scientific fields, work, cap exhaustion, and budget totals;
  wall times and internal debit batching may differ.
- The bounded fitting helper accepts an injected predictor. Both facades meter
  underlying solves; fitting retains its best completed candidate on interruption.
  Inference exposes only registered resolution-locked numerical fixtures, not an
  adjustable-solver/reference action. These fixtures are not trained or validated
  complementary surrogates.

Verification: **40 shared-foundation tests and all 12 existing pilot tests pass**.
The shared suite also passes with Python warnings treated as errors. The separate
validation command passes **37/37 checks**, covering 18 numerical cases, three
analytic-access recoverability cases, and two scripted interface checks. Editable
installation was verified by importing the package outside the repository CWD.

## Numerical accuracy and work

The independent Cole-Hopf/Fourier implementation agrees between 1,024 and 2,048
reference points to a worst observed absolute difference of **9.40e-11**, below
the required `1e-7`. This comparison covers both initial profiles, viscosities
0.1/0.2/0.3, all five record times, and all sensor/forecast positions. It is not
another run of the candidate discretization. The transformation is described in
[The Burgers Equation, section 6.3](https://math.nyu.edu/~tabak/PDEs/The_Burgers-Equation.pdf).

Errors below are unnormalized final-profile RMSE over the 16 positions, using
the **true viscosity** in the candidate solve. Divide by 1.5 for the normalized
profile metric. They isolate discretization error, not fitting/agent performance.

| Viscosity | Forecast grid | Profile RMSE | Work units | Credits |
| ---: | ---: | ---: | ---: | ---: |
| 0.1 | 32 | 0.15079851 | 2,112 | 0.127907 |
| 0.1 | 64 | 0.07943057 | 11,392 | 0.689922 |
| 0.1 | 128 | 0.03977050 | 71,936 | 4.356589 |
| 0.2 | 32 | 0.08256536 | 2,880 | 0.174419 |
| 0.2 | 64 | 0.04024118 | 17,920 | 1.085271 |
| 0.2 | 128 | 0.01944771 | 124,160 | 7.519380 |
| 0.3 | 32 | 0.05827156 | 3,648 | 0.220930 |
| 0.3 | 64 | 0.02831402 | 24,320 | 1.472868 |
| 0.3 | 128 | 0.01385444 | 176,640 | 10.697674 |

Calibration-profile RMSE also decreases strictly across 32/64/128 points: from
0.04970135 to 0.01085776 at viscosity 0.1; 0.03439383 to 0.00803868 at 0.2;
and 0.02606924 to 0.00612894 at 0.3. All 18 runs complete with finite values,
mass conservation within `1e-12`, and no recorded-state discrete-energy increase
beyond `1e-12`. Initial-condition and periodic-indexing tests pass separately.
The full calibration/forecast error-work table is in the generated artifacts.

## Fitting diagnostics and scripted submissions

With noise-free records from all three sensors and an injected **reference-based
predictor**, bounded fitting gives:

| True viscosity | Fitted viscosity | Absolute error | Predictor calls |
| ---: | ---: | ---: | ---: |
| 0.14 | 0.140000000491 | 4.91e-10 | 11 |
| 0.20 | 0.199999999747 | 2.53e-10 | 11 |
| 0.26 | 0.259999999959 | 4.06e-11 | 12 |

These are recoverability diagnostics with privileged analytic prediction access,
**not matched restricted-tool baselines**. They do not establish noisy or
imperfect-model recovery within a budget.

Two fixed scripts exercise the actual facade contracts using one noisy record at
sensor 2, target viscosity 0.2, instance seed 0, and a 32-point numerical fit.
Both return estimated viscosity 0.119844964597 after 12 predictor evaluations.
The planning script then computes a 64-point forecast; inference submits the
parameter directly. The re-requested inference prediction is a free purchased
result, not a new computation.

| Script | Configured cap(s) | Observation spend | Compute spend | Private normalized error |
| --- | --- | ---: | ---: | ---: |
| Planning | 50 shared credits | 2 | 2.317829 | 0.03984658, submitted-profile RMSE/1.5 |
| Inference | 8 observation, 30 compute | 2 | 1.550388 | 0.08318721, reference-response RMSE/1.5 |

Inference's absolute viscosity error is 0.08015504. Thus the restricted numerical
fit is not accurately recovering viscosity in this smoke case, despite the
separate analytic-access diagnostic passing. The two scores implement different
submission contracts; they are not comparable project/policy performance results.
Tool responses contain neither these private scores nor hidden parameters/seeds.

## Reproduce and identify the source

From the repository root on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -W error -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m unittest discover -s demos/planning/tests -v
.\.venv\Scripts\python.exe -m budgeted_science.burgers.validate
```

On POSIX, replace `.venv\Scripts\python.exe` with `.venv/bin/python`. Install
the measured NumPy/SciPy versions below to reproduce this software environment;
the package also declares broader supported dependency ranges. Only the measured
environment was exercised here, not every supported Python/dependency version.

- Package 0.1.0; Python 3.13.5; NumPy 2.3.4; SciPy 1.16.1.
- Platform: Windows 11, build 10.0.26200.
- Solver version: `rusanov-centered-diffusion-ssprk2-v1`.
- Reference version: `periodic-cole-hopf-fourier-v1`.
- Package-source aggregate SHA-256:
  `c21f5e3155c4d8339f46755c29e1748ff36388a26c428899a10e36b133e6d8ae`.
- Test source SHA-256 (`tests/test_burgers.py`):
  `b87a5a43698cfc2e7b2bf15d06782043aa6b6c0fb2bc54f0f36830f8061da6cb`.
- Editable-install specification SHA-256 (`pyproject.toml`):
  `72a0f972ead5ca470e6d2b49ea16917ede64466e5837d7c8fd03834190c5b1e9`.

The aggregate hashes a canonical sorted JSON mapping of package-relative Python
source paths to byte-level SHA-256 hashes. `summary.json` records every individual
hash, the configuration, software versions, timestamp, all check outcomes, and
raw numerical/fit results. Byte-level hashes are sensitive to newline conversion.

Generated files under ignored `tmp/burgers_foundation/` are `summary.json`,
`results.md`, `numerical_results.csv`, `reference_comparisons.csv`,
`recoverability.csv`, `profiles.csv`, two `*_trace.json` files, and `cache/*.npz`.
They are private evaluator artifacts, not agent inputs. The measured validation
body took 0.454 seconds; individual numerical cases took about 0.0015-0.045
seconds. These are single-machine observations excluding install/import startup,
not portable performance guarantees or credit prices. No API calls or GPU runs
were made.

## Limits and next experiments

This restricted family permits fast Cole-Hopf computation. It therefore
demonstrates controlled tool contracts rather than intrinsically costly physics;
later coding-enabled evaluation must acknowledge lawful analytic shortcuts.
Trusted in-process separation and ignored files are not a security sandbox.

No adaptive-allocation benefit, robust model-discrepancy correction, or agent
success has been established. Budget/price sweeps, matched policy comparisons,
model-bank preparation and calibration, and agent integration remain future work.
The small scripted runs do not choose final budgets or establish statistical
power. Neither this report nor the implementation changes the standalone
proposals or the existing allocation pilot.
