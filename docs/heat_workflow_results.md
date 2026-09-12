# Four-study heat-workflow audit: CPU results

Completed 2026-09-12. **Refinement-only: 2/4 correct; independent reconstruction:
4/4 correct.** All eight CPU controls completed; no agent/API calls or credentials
were used. The stronger control remains cheap, so this is a workflow-verification
demonstration, not an established budgeted-investigation challenge.

## Setup and implementation

The square plate has `T_top=1` and the other three edges at zero. Temperature is
dimensionless. The intended equation is `T_xx + T_yy = 0` on `[0,1]^2`; the claim
concerns the area-mean temperature in `x=[0.1,0.3], y=[0.6,0.8]`, within **5%**
relative error. All four reports concern this same target and region.

This independent NumPy/SciPy implementation uses the same type of five-point
stencil and weighted-Jacobi iteration as the
[SimulCost steady-heat example](https://github.com/Eydcao/simulcost-tools/blob/main/solvers/heat_steady_2d.py).
It neither vendors nor executes SimulCost. It requires no GPU, CFD installation,
Docker, OpenAI dependency, or scientific-data acquisition. Existing simulations,
tools, proposals and saved results were not modified.

The numerical settings were specified before this four-study run; no severity
sweep, case replacement, or agent-result-based tuning was used:

- All original grids: 33 x 33, zero initial interior temperature, at most 50,000
  weighted-Jacobi updates. Adjacent boundary values are averaged at corners.
- Sound, extraction-error and boundary-error studies: relaxation 0.8 and global
  RMS update threshold `1e-10`.
- Premature-stopping study: relaxation 0.02 and update threshold `2e-4`. It reaches
  that update criterion even though the regional temperature is very inaccurate.
- Extraction-error study: the executed analysis transposes the field before
  computing the requested spatial average.
- Boundary-error study: the executed left boundary is 0.5 instead of the intended
  zero. The intended specification remains unchanged and available for inspection.

The mean is computed by exactly integrating the stored field's bilinear
interpolant over the patch. The reported number is that executed analysis result
rounded to ten significant digits. Evaluation scores that literal printed value,
not a separately fabricated answer or a label assigned from the defect name.

## Measured results

The continuous-reference patch mean is **0.31202913598154375**.

| Study construction | Reported mean | Error vs reference | Correct verdict | Refinement-only | Independent reconstruction |
|---|---:|---:|---|---|---|
| Sound | 0.3122230645 | 0.06215% | ACCEPT | ACCEPT | ACCEPT |
| Premature stopping | 0.00005208051623 | 99.98331% | REJECT | REJECT | REJECT |
| Incorrect spatial extraction | 0.05991316415 | 80.79886% | REJECT | ACCEPT (wrong) | REJECT |
| Boundary mismatch | 0.590588893 | 89.27364% | REJECT | ACCEPT (wrong) | REJECT |

These are deliberately obvious smoke-test defects. They are not a calibrated
difficulty distribution, and one physical system is not four independent systems.
There are three invalid claims and one valid claim; always rejecting would score
3/4. No claims about superiority over arbitrary simple baselines follow from the
refinement-only result.

### What each control actually does

**Refinement-only** reruns weighted Jacobi at 65 x 65, relaxation 0.8 and update
tolerance `1e-12`. It retains the study's executed boundary inputs and literal
analysis script. It compares the refined quantity with the original report at
the same 5% threshold. This fixes premature iteration stopping but cannot repair
incorrect spatial extraction or an incorrect problem setup.

**Independent reconstruction** reads the intended boundary values and patch,
assembles the discrete Laplace equation separately, and uses SciPy's
[sparse direct solver](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.linalg.spsolve.html)
on 33 x 33 and 65 x 65 grids. It computes the stated patch average independently
of the study script, checks successive estimates agree within 1%, and uses the
finer estimate for the verdict. That agreement check is not a certified bound.
Neither control reads the private Fourier reference or case labels.

Independent reconstruction took **0.021-0.107 seconds per control**, including
saved numerical artifacts. Refinement-only took **0.690-2.029 seconds**. Individual
sparse solver times in the numerical validation were 0.003, 0.008 and 0.035 seconds
at 33, 65 and 129 points per side. These are descriptive observations on this host;
the existing regression suite ran concurrently, so they are not controlled timing
benchmarks. Startup, reference construction, and original-study creation are not
included in control times.

No credit cap, spending penalty, early-stopping reward or artificial relative
price was introduced. Jacobi records `grid_points * performed_iterations`, labelled
as a work proxy. Sparse solves record unknowns, nonzeros and runtime. Those counts
are not treated as interchangeable FLOPs or credits. Each control solves afresh;
there is no cross-control result reuse or hidden cost-free reference query.

## Numerical checks and artifacts

The evaluator uses a separately derived harmonic Fourier series for constant
Dirichlet edge temperatures, integrated analytically over the interior rectangle.
The 128- and 256-odd-mode results agree to displayed floating-point precision.
The sparse discretization's errors decrease under refinement:

| Points per side | Independent numerical mean | Relative error |
|---:|---:|---:|
| 33 | 0.3122230890 | 0.062159% |
| 65 | 0.3120780494 | 0.015676% |
| 129 | 0.3120416451 | 0.004009% |

The reference is independently checked, not a mathematically certified enclosure.
The five-percent labels are far from the decision boundary. Tests also check
constant-boundary reference identities, maximum principles, boundary indexing,
same-grid Jacobi/direct agreement, exact patch integration for an affine field,
invalid requests, explicit interruption/iteration-limit outcomes, policy isolation,
literal script/report consistency, and offline hash-verified regeneration.

Each study's `public/` folder has the report, intended specification, executed
configuration, solver log, field/coordinates, executable analysis script, and
analysis result. Labels and evaluator outputs are stored separately. This is
trusted file separation, not an agent security sandbox. The CPU harness executes
only its two exact repository-owned analysis templates; arbitrary-code execution
and live agent evaluation are not implemented.

Run: `20260912T222216Z-heat-workflow-cpu-5ea7c5b5f3`.

- [Complete report and all study/control links](../demos/claim_verification/runs/20260912T222216Z-heat-workflow-cpu-5ea7c5b5f3/report.md).
- [Four public study folders](../demos/claim_verification/runs/20260912T222216Z-heat-workflow-cpu-5ea7c5b5f3/studies/).
- [Chronological event log](../demos/claim_verification/runs/20260912T222216Z-heat-workflow-cpu-5ea7c5b5f3/events.jsonl).
- [Frozen configuration, software versions and source hashes](../demos/claim_verification/runs/20260912T222216Z-heat-workflow-cpu-5ea7c5b5f3/manifest.json).
- [Artifact integrity hashes](../demos/claim_verification/runs/20260912T222216Z-heat-workflow-cpu-5ea7c5b5f3/completion.json).

Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1; prototype version `heat-workflow-1`.
Generated arrays, studies and raw logs remain ignored by Git. The code and this
curated report are retained; no proposal document is changed.

The earlier commissioning run `20260912T221805Z-heat-workflow-cpu-bb59962055`
is also preserved. The final run only clarifies the public patch metadata as
explicit x/y intervals; its cases, policies and numerical answers are unchanged.
These two software runs are not pooled as additional scientific samples.

## Reproduction

From the `budgeted-science` repository with its existing environment:

```powershell
python -m budgeted_science.heat_workflow.experiment validate
python -m budgeted_science.heat_workflow.experiment run
python -m budgeted_science.heat_workflow.experiment render demos/claim_verification/runs/20260912T222216Z-heat-workflow-cpu-5ea7c5b5f3
python -m unittest discover -s tests -p test_heat_workflow.py -v
```

`run` never overwrites an earlier run. `render` verifies recorded artifact hashes
and reads logs without running any solver, analysis script, or model. Each public
`analysis.py` can also be run directly; it reads only the neighboring trajectory
and prints its calculated mean without modifying the study.

Verification: all **21 new tests** and **14 preserved planning-pilot tests** pass.
The full shared suite ran **744 tests: 743 passed, one frozen-campaign source
guard fired during a concurrent edit to the new module's public metadata**. That
guard hashes the entire shared source tree. With source edits finished, its whole
18-test module (`test_study_verification.py`) passed on rerun. No existing runner
was modified to suppress the guard. Final artifact hashes, source hashes, report
links, standalone study scripts, and offline regeneration were also checked.

## Conclusion

The CPU prototype demonstrates that a more accurate rerun of the same workflow
can preserve consequential study errors. It also demonstrates that an independent
reconstruction resolves these four cases very cheaply. **We have not demonstrated
a hard agent benchmark, meaningful budget-allocation pressure, or justified
confidence.** This result should not be described as having solved those design
problems.
