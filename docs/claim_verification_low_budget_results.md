# Small claim-verification budget sweep

Completed 2026-09-12. **Budget reduction alone did not remove the strong fixed
RK2 solution:** it scored 12/12 at four credits and 11/12 at two credits.
No LLM/API calls, new scientific systems, comparative-claim tasks, or proposal
edits were included. Previous results remain unchanged.

## Same 12 development claims at both budgets

| Policy | 4 credits | 2 credits | Mean spent at 4 / 2 |
|---|---:|---:|---:|
| Budget-matched fixed RK2 | 12/12 | 11/12 | 4.000 / 2.000 |
| Budget-matched fixed Euler | 10/12 | 9/12 | 4.000 / 2.000 |
| Existing randomized checks | 9/12 | 8/12 | 3.913 / 1.920 |
| Existing adaptive heuristic | 7/12 | 8/12 | 3.845 / 1.791 |

All **96 CPU episodes** completed: 12 claims x 2 budgets x 4 policies.
There were no abstentions, incomplete episodes, duplicate slots, overspends,
missing results, or unknown accounting. Twenty-two purchased numerical checks
failed; their performed work was charged and their records retained. This did
not prevent any episode from submitting a verdict. Actual API spending: zero.

| Budget / policy | Peak height | Peak time | Cumulative population |
|---|---:|---:|---:|
| 4 / RK2 | 4/4 | 4/4 | 4/4 |
| 4 / Euler | 3/4 | 4/4 | 3/4 |
| 4 / random | 3/4 | 3/4 | 3/4 |
| 4 / adaptive | 2/4 | 1/4 | 4/4 |
| 2 / RK2 | 4/4 | 3/4 | 4/4 |
| 2 / Euler | 3/4 | 3/4 | 3/4 |
| 2 / random | 2/4 | 2/4 | 4/4 |
| 2 / adaptive | 3/4 | 2/4 | 3/4 |

The two-credit RK2 error was a false rejection. The report claimed peak time
2.2 within 0.16; the reference is 2.07006596, so it is valid. The purchased
check estimated 2.02409639, making the apparent difference 0.17590361 and
triggering rejection. Height and integral verification remained perfect for
RK2 at both budgets. The adaptive method's nonmonotonic results are not evidence
that fewer credits help: it is an unchanged heuristic with imperfect acquisition
and estimation rules, tested on only 12 claims.

## Case selection and interpretation

The source was the previous frozen catalog
`20260912T043026Z-qoi-cpu-e6c9d30dd9`. Only development seeds 7300-7302 were
eligible. For each quantity, selection took two valid and two invalid claims
from a seeded shuffle, preferring different original studies within each label
stratum. The selection seed is 20260912, with deterministic quantity/label
offsets. It does not inspect baseline scores, failure cases, error severity,
or proximity to tolerance. This is deliberately **truth-label-stratified**,
not label-blind or an estimate of natural claim prevalence.

The resulting 12 claims share **three physical systems and eight original
numerical studies**. They include six valid and six invalid claims. No fresh
systems were evaluated, and no cases were replaced after looking at results.
Both budgets and all methods use exactly these same claims and independent
purchase histories. The earlier 108-claim fresh result is not a matched sample
for this sweep; do not directly attribute differences from that aggregate to
budget alone.

## Affordable fixed checks, not unaffordable legacy checks

The old fixed check cost 6.01, so it was not reused unchanged. Instead, each
fixed method chooses its configuration from public budget and claimed quantity
alone, before using numerical evidence to decide the verdict.

For every allowed integer integration-step count `n`, the selector takes the
densest affordable uniform output grid with `m` intervals. It checks actual
quotes, including floating-point endpoint handling, and minimizes the existing
public resolution-order proxy. This is a budget-matched numerical control, not
a reference-selected or proven optimal solver. All configurations remain valid
actions in the unchanged public tool interface.

| Budget | Method | Quantity group | Integration steps n | Output intervals m |
|---|---|---|---:|---:|
| 4 | RK2 | Height / integral | 122 | 155 |
| 4 | RK2 | Time | 117 | 165 |
| 4 | Euler | Height / integral | 338 | 61 |
| 4 | Euler | Time | 199 | 200 |
| 2 | RK2 | Height / integral | 61 | 77 |
| 2 | RK2 | Time | 58 | 83 |
| 2 | Euler | Height / integral | 162 | 37 |
| 2 | Euler | Time | 99 | 100 |

Here `dt=8/n`, output spacing is `8/m`, and output phase is zero. Credits are
still `(performed RHS evaluations + completed output samples)/100`, a synthetic
work proxy rather than time or money. Fixed checks use the full budget; this
is their acquisition rule, not a task requirement. Random/adaptive menus and
the common purchased-evidence estimator are unchanged. The fixed methods can
use finer integer-grid choices than those policies' original restricted menus,
so performance differences do not isolate adaptation as a causal factor.

## Records and reproduction

Run: `20260912T050528Z-qoi-low-budget-8263e2d7de`.

- [Complete per-claim results and transcripts](../demos/claim_verification/runs/20260912T050528Z-qoi-low-budget-8263e2d7de/report.md)
- [Frozen settings, selected claims, source hashes, and imported-artifact hashes](../demos/claim_verification/runs/20260912T050528Z-qoi-low-budget-8263e2d7de/manifest.json)
- [Aggregate JSON](../demos/claim_verification/runs/20260912T050528Z-qoi-low-budget-8263e2d7de/summary.json)
- [Two-credit RK2 false-rejection transcript](../demos/claim_verification/runs/20260912T050528Z-qoi-low-budget-8263e2d7de/episodes/20260912T050535Z-fixed_rk2_budget-498223e756/transcript.md)

The manifest freezes source hashes, imported study hashes, case order, policy
seed 0, both budgets, and all fixed configurations before evaluation. Raw logs
and copied private studies remain local and ignored. Python 3.13.5, NumPy 2.3.4,
SciPy 1.16.1. Episode limits remain 2,000 tool calls and a cooperative 300-second
deadline. Offline rendering invokes no solver or policy and preserves partial
result files as incomplete instead of treating them as successful submissions.

Verification: **521 tests pass** (507 repository tests plus 14 planning-pilot
tests), including 14 new small-sweep tests. Source hashes and all imported study
hashes matched after execution. Offline regeneration reproduced the summary and
full report exactly with solver and policy execution blocked; all 96 transcripts
are present.

```powershell
.\.venv\Scripts\python.exe -B -m budgeted_science.claim_verification_qoi.budget_sweep run
.\.venv\Scripts\python.exe -B -m budgeted_science.claim_verification_qoi.budget_sweep render demos\claim_verification\runs\20260912T050528Z-qoi-low-budget-8263e2d7de
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_claim_qoi_budget_sweep.py -q
```

The run command imports the preserved catalog above by default; `--source`
can explicitly select a compatible saved catalog. Regeneration needs only the
saved sweep directory. The shared episode runner gained optional policy
injection and atomic result publication; its default scientific behavior is
unchanged. No existing solver, original policy, or scoring contract was edited.
