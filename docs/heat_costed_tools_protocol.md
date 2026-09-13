# Heat-workflow verification with multiple costed tools

## Scope

This extension retains the four heat-workflow development studies and their
original public artifacts and private verdicts. Both GPT-5.6 Luna and Sol use
high reasoning, the same scientific prompt, and independent eight-credit
ledgers. There is no hosted Python, arbitrary code execution, or exact-reference
tool. Models select numerical jobs and analyze their returned records.

Four studies share one intended physical system: steady Laplace heat flow in
the unit square, with top temperature 1 and the other boundaries 0. Each claim
concerns the area-mean temperature over x=[0.1,0.3], y=[0.6,0.8], within 5%.
The original constructions are sound, prematurely stopped, incorrectly
extracted, and boundary-mismatched studies. These categories and evaluator
answers are not supplied to the models. They are development fixtures, not
four independent physical systems or held-out studies.

## Numerical tools and credits

Let n denote nodes per axis. Available n are 17, 33, 65; iteration blocks are
256, 1,024, or 4,096 weighted-Jacobi sweeps, with an agent-selected relaxation
in (0,1]. These are synthetic flat job tariffs, not empirical runtime or FLOPs.
Cross-method conversion is a declared assumption, not a realistic universal
exchange rate.

| Tool | Operation | Price |
|---|---|---|
| `iterate` | Continue a purchased field, preserving grid and boundary values | n² × sweeps / (33² × 1,024) |
| `remesh` | Start from zero interior on a chosen grid, preserving the source run's boundaries | n² × sweeps / (33² × 1,024) |
| `solve_matrix` | Separate sparse-matrix assembly with explicitly supplied boundary values and grid | 4n² / 33² |
| `perturb_boundary` | Change one boundary of a purchased run by a selected increment and solve the changed problem on that grid | 4n² / 33² |

At n=33, 256 sweeps cost 0.25, 1,024 cost 1, and a matrix solve costs 4.
Matrix solves at n=17 cost 1.06152; at n=65 cost 15.5188 and do not fit the
eight-credit cap. Iterative work at n=65 may still fit. The price schedule is
disclosed before the investigation. No numerical job automatically interprets
the claim, alters the original reported value, or certifies its error.

Five additional tools are free: `read_artifact`, paginated `record`,
`integrate_field`, `budget`, and `submit`. Integration computes the area mean
of a purchased field's bilinear interpolant for explicitly supplied rectangle
coordinates and array-transposition choice. This is a numerical analysis helper,
not a reference calculation. The full original analysis source is inspectable
but cannot be executed as arbitrary code through this interface.

All numerical jobs must fit before execution. Invalid and unaffordable calls
cost nothing. Once a valid job executes, failure retains its flat charge. Exact
repeated requests reuse their purchased numerical record for free, including
failed records. Continuing from a newly produced field is a different job.
Accounting uses exact rational charges internally. Complete numerical fields,
settings, timings, work diagnostics, purchases, and failures are retained.
No cross-episode purchase history or conversation state is shared.

## Evaluation and controls

ACCEPT/REJECT accuracy uses the unchanged private continuous-series reference.
ABSTAIN is completed but not a correct binary answer. Explanations and optional
numerical estimates are retained, not semantically graded. The estimate never
replaces the submitted verdict. Unknown evidence identifiers are rejected;
checking identifiers is not checking whether an explanation is scientifically
justified. No full-budget requirement, early-stop reward, or cost/accuracy
composite score is imposed.

Report each verdict, paid job count, spending by tool, total scientific credits,
elapsed runtime, and separately accounted API dollars. Report correct verdicts
out of four per model; incomplete attempts are nonsuccesses. Four cases do not
support statistical claims of general model superiority.

Two fixed CPU controls use the same tools and independent eight-credit budgets:

- **Refinement-only:** one n=33 matrix solve with executed boundary conditions,
  then original coordinate extraction, costing 4 credits.
- **Independent reconstruction:** matrix solves at n=17 and n=33 with intended
  boundary conditions and the stated rectangle. Check agreement within 1% and
  compare the finer result with the original claim. Cost 5.06152 credits.

Both controls use public study information, not the private reference. Their
judgments are practical numerical procedures, not mathematically certified
error estimates. A larger menu must not hide the fact that a fixed policy can
still solve a task. CPU control performance is measured before model execution,
and poor or easy outcomes are retained without retuning cases.

## Live limits and records

Eight fresh episodes: Luna and Sol on each of the original four cases. Case
order is preserved; which model runs first alternates. Each model has a $3
cumulative API ceiling across its four episodes ($6 total), with no transfers
or automatic increases. Each episode has at most 30 responses, 60 function
requests, 32,768 output tokens per response, and 20 minutes.

The existing streaming Responses runner retains standard service tier,
`store=false`, high reasoning, returned reasoning summaries and encrypted replay,
sequential function execution, complete raw archives, pre-request token counts,
and conservative token reservations. There are no generation retries or model
substitutions. Unknown usage retains its reservation and halts the campaign.
An exclusive attempt marker prevents automatically rerunning an attempted live
campaign. This extension does not implement live crash-resume.

Historical short-context accounting is retained: Sol input upper $5/M and
output $20/M; Luna input upper $0.25/M and output $1.20/M. Input upper bounds
include cache-write pricing; input over 256,000 tokens is refused. These rates
were checked against [Sol documentation](https://developers.openai.com/api/docs/models/gpt-5.6-sol),
[Luna documentation](https://developers.openai.com/api/docs/models/gpt-5.6-luna),
and [official pricing](https://developers.openai.com/api/docs/pricing).
Reported upper bounds are not invoices. Raw internal reasoning is unavailable.

```powershell
python -m budgeted_science.agents.heat_tools prepare
python -m budgeted_science.agents.heat_tools dry-run <prepared-directory>
# Paid: only after explicit authorization for a fresh evaluation.
python -m budgeted_science.agents.heat_tools live <prepared-directory>
python -m budgeted_science.agents.heat_tools render <saved-campaign-directory>
python -m unittest discover -s tests -p test_heat_tools.py -v
```

Preparation freezes code/dependency hashes, prices, case payload hashes, model
settings, CPU comparisons and execution order. Each episode freezes its actual
prompt and schemas before the first request. Offline rendering uses saved events
only; it must not execute tools, rerun scientific calculations, or contact APIs.
Raw runs and credentials remain ignored by Git. Previous experiments and
standalone proposal documents are unchanged.
