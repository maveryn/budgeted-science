# MMS verification: six-study CPU pilot

Implemented and evaluated on CPU, 12 September 2026. No model/API calls or
credentials were used. The scientific and logging implementation is separate
from all previous demos; their code and saved results were preserved.

**Result:** a short study-aware numerical rule correctly answers both questions
on **6/6 studies at 10 credits**. A full fixed checklist also gets 6/6 at 20
credits. This establishes working verification mechanics, **not a challenging
agent benchmark** or a need for sophisticated adaptive investigation.

Commissioning explicitly requires the complete study-aware policy's numerical
check to classify these development values correctly. Its 6/6 is therefore an
expected commissioning sanity check, not an independent generalization result.

## Setup

The [full protocol](mms_verification_protocol.md) specifies a steady 2-D
advection-diffusion equation on a unit square, three manufactured-solution
diagnostic families, and two separately scored claims:

- The original reported point value has relative error at most 2%.
- The audited implementation meets a declared near-second-order criterion on
  its relevant MMS test: both successive RMS orders at grids 8/16/32 lie in
  `[1.7,2.3]`. This finite-grid criterion does not certify asymptotic order.

Agents have not been evaluated. CPU rules use the intended coefficients and
boundary configuration, not free-form report understanding. They may rerun the
study or choose a diagnostic and grid. Both audited and independently assembled
numerical kernels are available at the same price. Only diagnostics expose
exact errors; the original study's reference answer is evaluator-side.

Six development studies share **three physical systems**. The harmless-control
study is numerically identical to the sound diffusion study. No held-out
systems, independent noise realizations, or statistical significance are claimed.
Five policies at two budgets yield 60 cheap policy episodes, not 60 new studies.

## Measured study outcomes

The printed original value, rather than an improved value, is scored. Selection
followed a saved numerical sweep before policy comparisons. No policy results
were used to replace cases or tune the policies.

| Development study | Original grid | Actual reported-value error | Relevant MMS orders | Value claim | Order claim |
|---|---:|---:|---|---|---|
| Sound diffusion | 16 | 0.3939% | 1.934, 1.961 | True | True |
| Correct mixed-BC code, coarse study | 8 | 7.3385% | 1.945, 1.971 | False | True |
| Upwind advection, coarse study | 8 | 2.8557% | 0.736, 0.856 | False | False |
| First-order Neumann boundary treatment | 16 | 6.1050% | 1.339, 1.154 | False | False |
| Upwind advection, finer study | 16 | 1.2983% | 0.736, 0.856 | True | False |
| Inactive upwind change in diffusion | 16 | 0.3939% | 1.934, 1.961 | True | True |

The fifth row is important: a failed code-order check does **not** justify
rejecting the value claim. Conversely, the second row has an inaccurate value
despite its implementation passing the order criterion.

## Diagnostic effects

Each cell reports successive RMS orders on 8/16/32 intervals. The table comes
from actual diagnostic solves, not assigned fault labels.

| Audited kernel | Diffusion MMS | Advection MMS | Mixed-BC MMS |
|---|---|---|---|
| Central, second-order boundaries | 1.934, 1.961 | 1.942, 1.964 | 1.945, 1.971 |
| First-order upwind | 1.934, 1.961 | 0.736, 0.856 | 2.474, 2.157 |
| First-order Neumann | 1.934, 1.961 | 1.942, 1.964 | 1.339, 1.154 |

Diffusion is blind to the inactive advection choice; Dirichlet cases do not
exercise Neumann treatment. Mixed-BC upwind errors have a cancellation-dominated
finite-grid pattern, not a clean order-one curve. This is why the labels use
measured finite-grid behavior and why no universal asymptotic diagnosis is made.
The mixed diagnostic can expose more than one defect; the suite does not prove
that there is a unique diagnostic for each failure.

## CPU policy results

Correct counts include abstentions in their denominators. The two component
scores must not be conflated. All 60 episodes completed; there were no wrong
binary verdicts. Lower counts below arise from explicit abstentions.

| Budget | Policy | Value correct | Order correct | Both correct | Mean credits spent |
|---:|---|---:|---:|---:|---:|
| 10 | Audited study refinement only | 6/6 | 0/6 | 0/6 | 4.1015 |
| 10 | Fixed diffusion diagnostic + independent study | 6/6 | 2/6 | 2/6 | 8.8166 |
| 10 | All three diagnostics, fixed sequence | 0/6 | 5/6 | 0/6 | 7.6090 |
| 10 | **Study-aware rule + independent study** | **6/6** | **6/6** | **6/6** | **8.8166** |
| 10 | Study-aware, stop order checks after a failed pair | 6/6 | 6/6 | 6/6 | 6.9325 |
| 20 | Audited study refinement only | 6/6 | 0/6 | 0/6 | 18.7209 |
| 20 | Fixed diffusion diagnostic + independent study | 6/6 | 2/6 | 2/6 | 8.8166 |
| 20 | All three diagnostics, fixed sequence | 6/6 | 6/6 | 6/6 | 18.9135 |
| 20 | Study-aware rule + independent study | 6/6 | 6/6 | 6/6 | 8.8166 |
| 20 | Study-aware, stop order checks after a failed pair | 6/6 | 6/6 | 6/6 | 6.9325 |

The strong rule is short: use the mixed test for mixed boundaries, otherwise the
advection test for nonzero velocity, otherwise diffusion. This public metadata
dispatch is sufficient; no model-based planning is required.

The refinement-only control does not attempt the order claim. Its 0/6 joint
score must **not** be presented as failure to estimate the original quantity:
it gets all six value verdicts right. The generic diffusion check abstains on
four out-of-scope order claims. At 10 credits the fixed full-suite sequence
uses resources on diagnostics and cannot buy a 32-grid study check; at 20 it
completes everything correctly. Its tight-budget failure is a property of this
fixed sequencing rule, not proof that adaptivity is necessary.

Early rejection saves one 32-grid MMS solve on three cases, because a failed
first pair already refutes the explicitly conjunctive order claim. The mean
saving is 1.8841 credits. There is no spending reward, confidence score, or claim
that stopping is generally optimal.

## Budget and numerical checks

Credits are `(grid+1)^2/289`, a grid-size proxy, **not** measured FLOPs, sparse
factorization work, CPU time or money. A complete targeted path costs 8.81661
credits; all three tests plus the independent study check cost 18.91349. These
paths were commissioned before policy evaluation. Independent 32-grid study
point errors were 0.0972%, 0.0518%, and 0.3017% for diffusion, advection and mixed
systems, respectively. They support this development demonstration, not a
certified error bound on arbitrary problems.

Numerical validation observed:

- Maximum analytic first-derivative disagreement: `1.78e-15`.
- Maximum analytic Laplacian disagreement: `2.13e-14`.
- Maximum scaled algebraic residual across diagnostic validation: `3.60e-13`.
- Independent tensor/loop assembly field disagreement at grid 32: `0.0` at
  recorded precision, consistent with assembling the same discretization.
- Inactive upwind diffusion field difference: exactly zero.
- Sound RMS errors decrease through grids 8,16,32,64 for all three families.

Commissioning and 60 episodes took 2.85 seconds of harness elapsed time in this
run, before offline report rendering. Mean per-policy episode times ranged
from roughly 0.01 to 0.06 seconds and include logging. These are not controlled
runtime benchmarks.

## Records and reproduction

Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1; Windows 11. API expenditure: **$0**.

Local ignored run:
[complete report and episode links](../demos/claim_verification/runs/20260912T191002Z-mms-cpu-fc4ad49335/report.md).
Its `manifest.json` contains the full configuration and SHA-256 hashes for all
six MMS modules plus the reused logging module. `private/catalog.json` retains
the analytical references, `validation.json` the error tables, and each episode
contains purchased numerical arrays, actions, charges, exact responses and a
readable transcript. All JSON/JSONL hashes are checked on replay, along with
submission/charge/evidence/evaluation consistency. The source freeze matched
at completion. Interrupted batches retain replayable partial summaries.
Raw data are local and untracked; this curated report is self-contained.

An initial internal CPU run (`20260912T190213Z-mms-cpu-e4fc331e01`) is also
preserved. Review removed an unused 16-grid independent solve from the complete
policies, saving one credit with no verdict changes. It also removed undeclared
Neumann data from all-Dirichlet public artifacts and strengthened log replay;
the updated run above is the reported checkpoint. No cases were changed.

Verification: all 635 pre-existing shared tests and 14 planning-pilot tests
passed. The final new MMS suite passes 27 tests, including numerical checks,
separate truth scoring, cache/budget behavior, interruption, source-freeze
mismatch, and rejection of inconsistent/tampered replay artifacts.

```powershell
python -m unittest discover -s tests -p test_mms_verification.py -v
python -m budgeted_science.mms_verification.experiment validate
python -m budgeted_science.mms_verification.experiment cpu
python -m budgeted_science.mms_verification.experiment render demos/claim_verification/runs/20260912T191002Z-mms-cpu-fc4ad49335
```

## Verdict

The toy now separates calculation accuracy from a checkable code-order claim,
has relevant/irrelevant diagnostics and harmless controls, and has feasible
full-audit budgets. **It remains easy for a competent classical rule.** It is
usable as a small executable proposal illustration, but not evidence that LLM
agents are needed or that this design already supplies a difficult benchmark.
No additional agent evaluation is implied by this CPU milestone.
