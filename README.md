# Budgeted Science

The [six-study Luna/high follow-up](docs/paired_claim_followup_luna_results.md)
completed at **32 credits per study**: **29/36 correct, four wrong, three
abstentions**, versus 33 correct and three abstentions for the saved
measurement-first adaptive CPU policy. All 18 specified-model claims were
correct; errors and abstentions were confined to target claims. Total API
cost upper bound: **$0.18630**. Logs and numerical artifacts are retained.
This is an engineered development pilot, not a general performance estimate.

The [evidence-conditioned CPU follow-up](docs/paired_claim_followup_results.md)
now tests whether a target measurement changes which high-fidelity calculation
is worth buying. At 32 credits the measurement-first adaptive policy gets
**33/36 correct, zero wrong, three abstentions**. An uncertainty-aware fixed
policy gets 30 correct and six abstentions; a fixed intervention-label guess
gets **34 correct and two wrong**. Adaptation wins under the declared wrong-answer
penalty, not raw correct count. The corrected v2 report includes the cheap control
that invalidated v1, an overfitting check, and limitations. That initial
commissioning comparison was CPU-only; the separate Luna evaluation is above.

The [paired claim-audit CPU extension](demos/paired_claim_audit/README.md)
uses six studies with identical early evidence within each pair but opposite
target verdicts. At 24 and 32 credits, adaptive and fixed measurement-first
policies all get **36/36** claims correct; simulation-first gets 18 correct
and abstains on 18. The [results](docs/paired_claim_audit_results.md) demonstrate
the value of target evidence, **not an adaptive-allocation accuracy advantage**.
No new agent/API run was made.

The [mixed six-claim study](demos/mixed_claim_audit/README.md) adds cumulative
abundance, intervention, recovery and population-composition claims alongside
simple checks, with shuffled presentation and shared evidence. At the planning
toy's **32 credits and 1/8/12 prices**, [Luna/high got 5/6 correct and 1 wrong](docs/mixed_claim_audit_results.md)
using 27 credits; the fixed classical baseline got 4/6 and abstained twice,
using 32. Luna's fitted target trajectory missed an actual recovery. A 52-credit
CPU-only complete-evidence diagnostic got 6/6; it is not a matched competitor.

At [24 credits](docs/mixed_claim_luna_24_results.md), a fresh Luna/high episode
again got **5/6 correct and 1 wrong**, spending 23 credits. It made the same
recovery error, using two high and seven low simulations with no paid target
measurements. The unchanged CPU control got 3/6 and abstained three times,
spending 20/24 credits. This is one episode per condition, not a budget-effect
estimate.

After an [initial API-ceiling interruption](docs/mixed_claim_sol_results.md),
the same [Sol/high episode completed through explicit continuation](docs/mixed_claim_sol_resumed_results.md):
**5/6 correct, 1 wrong, 32/32 credits**. Like Luna, it rejected the true recovery
claim. Cumulative API cost upper bound: $0.80116 under the owner-approved $1.50
ceiling. Prior history, evidence and both ledgers were retained; this is not a
new sample. No automatic retry or limit increase was performed.

The [multi-claim predator-prey audit](demos/multi_claim_audit/README.md) reuses the
planning environment and its 32-credit budget with 1/8/12-credit resources.
One short study has four numerical-accuracy and two simulated-target-accuracy
claims, with reusable evidence, a fixed CPU control, and a logged Luna/high
runner. See the [protocol](docs/multi_claim_audit_protocol.md); one solve may
inform several claims, intentionally. The [completed comparison](docs/multi_claim_audit_results.md)
scores both Luna/high and the fixed CPU control 6/6 at 32 credits; Luna's API
accounting upper bound is $0.00518. This is a small mechanics demonstration.

The [20-credit follow-up](docs/multi_claim_twenty_results.md) gives Luna 6/6
verdicts at 18 credits, versus Sol and the fixed control at 5/6 plus one
abstention at 20 credits. Luna's C6 explanation has the wrong error direction,
so verdict accuracy must not be mistaken for six soundly verified claims.

At [12 credits](docs/multi_claim_twelve_results.md), Luna and Sol each score
6/6 using one high plus four low simulations; the unchanged fixed control
gets 4/6 and abstains twice, spending 8 credits. Both models again give the
wrong error direction for C6 despite the correct rejection. Complete logs
and the distinction between verdict accuracy and explanation quality are
preserved in the report.

The [costed heat-tool extension](docs/heat_costed_tools_protocol.md) provides
four paid numerical services, free artifact/field analysis, and eight scientific
credits per case. It compares Luna/high and Sol/high on the same four original
heat studies, without hosted Python. Fixed CPU controls use the same tariffs.
The [completed comparison](docs/heat_costed_tools_results.md) scores both models
4/4: Luna averages 4.80 credits and Sol 5.06. Both use only the matrix-solve
service for paid work; the larger menu has not removed the cheap fixed route.

The [four-study CPU heat-workflow audit](docs/heat_workflow_results.md) tests a
correct study, premature iteration stopping, incorrect spatial extraction, and
a mismatch between stated and executed boundary conditions. It is an independent
small NumPy/SciPy implementation inspired by SimulCost's steady heat problem,
not execution of the SimulCost package. No model calls or artificial credit cap
are involved; an inexpensive independent-reconstruction control remains available.

The subsequent [Luna/high hosted-Python attempt](docs/heat_workflow_luna_results.md)
ended with three abstentions and one tool-limit interruption across those four
studies. Its combined model/hosting accounting bound was $0.380. This exposed an
interface failure before scientific auditing, not a harder benchmark.

After an explicit continuation fix, the [fresh Luna/high rerun](docs/heat_workflow_luna_continuation_results.md)
completed all four studies with correct verdicts (4/4), matching independent
reconstruction, at a $0.394 combined upper bound. The interaction now works;
these four development studies still do not establish a difficult benchmark.

The [verification follow-up](docs/verification_reconstruction_and_ambiguity.md)
re-scores the saved pilot using its cited forecasts: at four credits, correct
verdict plus accurate reconstruction is 8/10 for adaptive residual versus 6/10
for fixed splitting. It also adds a separate two-case, finite-grid forecast
ambiguity demonstration with checkable evidence. These are CPU diagnostics,
not new model evaluations; original results are preserved.

The new [numerical fitting-and-forecast verification CPU pilot](docs/fit_prediction_verification_results.md)
uses ten development studies from two predator-prey systems, with actual
RHS-work accounting for both stages. Fixed-split and adaptive controls both
score 10/10 at four credits: this remains a mechanics demonstration, not an
established adaptive-auditing challenge. No new model/API calls were made.

The [three-stage study-verification pilot](docs/study_verification_protocol.md)
adds input processing and output analysis to the transport audit, with objective
numerical-claim scoring, CPU controls, and a logged Luna/high runner. It preserves
earlier demos; generated runs remain local and ignored. The
[matched results](docs/study_verification_results.md) include the completed
12-case Luna/high evaluation and CPU comparisons.

Lightweight testbeds for scientific agents making decisions under resource
constraints. The goal is to build clear, reproducible decision problems with
objective evaluation, beginning with small CPU-based demonstrations and later
adapting them to domain-specific scientific applications.

**1-D transport verification:** the [small PDE demonstration](docs/transport_verification_results.md)
adds mesh, timestep, scheme and output choices with work-based audit costs.
It uses 12 development claims across three systems. Balanced, space-focused,
output-focused and randomized CPU checks score 12/12; time-focused checks score
9/12. The implementation works, but this catalog still does not demonstrate
an adaptive-auditing challenge. That CPU pilot made no model/API calls.
The subsequent [Luna/high evaluation](docs/transport_verification_luna_results.md)
also scored 12/12, with mean expenditure 3.663 of four audit credits and an API
accounting upper bound of $0.1601 for the entire batch. All episodes completed;
correct verdicts do not establish that their explanations were fully accurate.

**Claim-specific verification revision:** the [earlier CPU pilot](docs/claim_verification_qoi_results.md)
adds peak-height, peak-time, and cumulative-population claims with configurable
Euler/RK2 checks. On 108 claims sharing six fresh systems, fixed RK2 scored
106/108, randomized checks 105/108, fixed Euler 99/108, and an adaptive heuristic
96/108. The setup remains easy for fixed RK2 and does not show an adaptive
advantage. All 810 development/fresh episodes completed without model/API calls.
See the [separate opt-in protocol](docs/claim_verification_qoi_protocol.md);
all previous task versions and saved results are preserved.

The [small 4-/2-credit follow-up](docs/claim_verification_low_budget_results.md)
uses just 12 development claims. Budget-matched RK2 scores 12/12 at four credits
and 11/12 at two, so reducing budget alone still leaves a strong fixed solution.
All 96 CPU episodes completed without model/API calls or new evaluation systems.

**Scientific claim verification:** a separate [predator-prey demo](demos/claim_verification/README.md)
now provides 30 completed-study variants, three report formats, 5-credit audit
tools, objective verdict scoring, and fully logged scripted fixtures. Numerical
commissioning checks integration and output-sampling errors independently.
The [fixed two-check baseline](docs/claim_verification_baseline_results.md) scores
30/30 on this development catalog. The [first Terra/high episode](docs/claim_verification_terra_first_result.md)
correctly accepted one sound claim using 5 credits, matching that baseline on
the same case. This single-case smoke test is not a model evaluation across the
catalog. See the [commissioning report](docs/claim_verification_toy_results.md)
and [logged runner/resume protocol](docs/claim_verification_agent_protocol.md).
The subsequent [30-case Luna/high evaluation](docs/claim_verification_luna_catalog_results.md)
scored 30/30, matching the fixed verifier, with 5 credits per case and an API
cost upper bound of USD 0.208. All 30 episodes completed without retry. These
variants share six development systems and do not establish general verification
performance or an adaptive-auditing advantage.

The [five-case alternative-tool comparison](docs/claim_verification_alternatives_results.md)
keeps that original peak claim and adds three genuine numerical choices.
Luna/high scores 5/5 with both the original and expanded menus, spending five
credits each; added tools are used on three cases. The entire ten-episode API
upper bound is $0.073. The fixed verifier also scores 5/5 in both conditions.

A separate [incremental-check CPU calibration](docs/claim_verification_incremental_results.md)
uses 30 new all-Euler studies and an 8-credit budget. Each check now halves
the timestep or output spacing. All four policies scored 29/30; same-evidence
extrapolation gave 30/30. This revision is still too easy to establish an
allocation challenge. No new model calls were made; original results and
model-tool contracts remain unchanged.

The [severity-recalibrated follow-up](docs/claim_verification_recalibrated_results.md)
adds coarser integration and balanced error families, with extrapolation as
the actual estimator. All four CPU policies scored 35/35 on six fresh systems
(one additional requested study could not be generated). This removes the
single-sampling-check shortcut but still does not establish an allocation
challenge. No new model calls were made.

The [recalibrated Luna/high evaluation](docs/claim_verification_incremental_luna_results.md)
scored **35/35**, matching all four classical policies. All episodes completed;
API accounting bounds were **$0.143–$0.396 total**, under a hard $2 batch ceiling.
Luna used 279 audit credits across the independent episodes. This revision still
does not establish an allocation challenge. The [logged runner protocol](docs/claim_verification_incremental_agent_protocol.md)
documents safeguards, complete local records, and restrictions on batch-funded resume.

**Harder planning toy (v2):** doubled parameter-range widths, noisy observations,
5% parameter tolerance, and a paid-data-only local least-squares baseline. The
new baseline passed 28/40 fresh cases, versus 0/40 for each GP control. The budget
remains 40 after a development sweep at 40/32/24. One subsequent GPT-5.6 Sol/high
episode used 40/40 credits and passed with largest parameter error 0.546%; the
local-fitting control also passed (0.877%). See the [single-agent run audit](docs/resource_planning_v2_agent_run.md).
See the [v2 setup, results, and commands](docs/resource_planning_v2_results.md).
At [32 credits on the same instance](docs/resource_planning_v2_32_credit_run.md),
GPT also passed, with largest error 3.035%; the local baseline passed at 4.700%.
The [matched Luna/high run](docs/resource_planning_v2_luna_run.md) completed 32
credits but failed the tolerance, with largest parameter error 15.682%.

The [five-case 32-credit campaign](docs/resource_planning_five_case_results.md)
now reports Sol 3/5, Luna 0/5, local fitting 1/5, and 0/5 for randomized
acquisition plus local fitting and both GP controls. On the four newly selected
cases alone, Sol passed 2/4 and every other method passed 0/4. All 30 results
submitted at exactly 32 credits. Eight new model episodes had an API cost upper
bound of $2.80; this small pilot is not a general performance ranking.

The [matched Terra/high extension](docs/resource_planning_terra_results.md)
added five fresh episodes without rerunning the earlier results. Terra passed
2/5 (2/4 excluding the exploratory anchor), with median largest error 20.92%.
All five submitted at 32 credits; total new API cost upper bound was $1.69.
The combined comparison contains 35 results, with full local logs preserved.

**Preserved planning toy (v1):** an independent predator-prey inverse problem compares
randomized nonadaptive acquisition with a cost-aware GP policy under 40 shared
credits. It uses live low/high-fidelity solvers and protected target measurements,
without LLM/API calls. See the [protocol](docs/resource_planning_toy_protocol.md)
and [paired CPU pilot results](docs/resource_planning_toy_results.md). An optional
[logged GPT adapter](docs/resource_planning_agent_run.md) now adds the shared
purchased-evidence fitter and a separate `run_resource_agent.py` entry point.
Explicit checkpoint/resume now preserves conversation, purchases, and cumulative
API charges. The first resumed predator-prey episode submitted successfully at
40/40 scientific credits; see the linked audit for limits and the single-instance result.
It does not replace the Burgers demo or its earlier agent runs.

**Status:** the CPU allocation pilot is preserved, and a shared viscous-Burgers
foundation now provides numerical tools, observations, budgets, fitting, and
separate planning/inference scoring contracts. Its numerical validation and
scripted contract checks are runnable. A single-episode planning runner now has
complete local audit logs, an offline fake-model mode, and an optional GPT-5.6 Sol
integration. Offline checks and its fixed-policy CPU comparison pass. Two live
attempts are retained: the first exposed a fixed replay-integration defect; the
post-fix attempt progressed for 11 responses and spent 19.17 scientific credits,
but reached its per-response output cap before submission. A subsequent
two-parameter episode completed: agent normalized RMSE 0.01834 at 19.80 credits,
versus 0.01812 at 17.88 credits for its fixed-policy comparison. This is one
development instance, not evidence of an adaptive-planning advantage. No trained
imperfect-model bank exists. See the [completed-run audit](docs/planning_two_parameter_agent_run.md).
See the [planning runner protocol](docs/planning_agent_runner.md).
See the [Burgers foundation results](docs/burgers_foundation_results.md),
[OCBA pilot results](docs/ocba_pilot_results.md), and
[pilot reproduction protocol](docs/ocba_pilot_protocol.md).

An [opt-in two-parameter CPU trial](docs/burgers_two_parameter_trial.md) now adds
unknown initial amplitude alongside viscosity. Reference/recoverability checks
and four budgeted fixed recipes run locally. The default agent task remains
one-parameter; `--two-parameter` now enables a logged amplitude/viscosity episode
with the same scientific budget and actual-profile scoring.

## Four independent demos

| Demo | Scientific decision | Final evaluation |
| --- | --- | --- |
| [Project planning](demos/planning/README.md) | Allocate a shared budget between target observations and computations. | Predator-prey toy: worst normalized parameter error and all-parameter success. Preserved Burgers: actual forecast-profile error. Allocation pilot: its own integral/selection scores. |
| [Imperfect-model inference](demos/imperfect_model_inference/README.md) | Use fixed approximate models and paid observations to infer a hidden target's parameters. | Held-out reference-response error from the submitted parameters. |
| [Surrogate development](demos/surrogate_development/README.md) | Acquire data and develop a predictor under acquisition, development-compute, and inference-cost limits. | Held-out predictive error and compliance with all three limits. |
| [Claim verification](demos/claim_verification/README.md) | Audit a completed numerical study using purchased verification computations. | Correctness of the original claim's within-5% verdict; coverage and error rates reported separately. |

## Repository layout

```text
demos/
  planning/                   # Preserved allocation pilot; logged Burgers agent runner
  imperfect_model_inference/  # Burgers fixed-predictor contract; model banks are future work
  surrogate_development/     # Planned CPU surrogate construction demo
  claim_verification/        # CPU catalog, scripted audits, optional logged agent runner
shared/budgeted_science/     # Scientific packages plus optional agent infrastructure
tests/                       # Numerical, tool-contract and offline runner tests
docs/                        # Protocol notes and proposal-appendix material
tmp/burgers_foundation/      # Ignored validation outputs and backend cache
```

Each demo has its own README and entry points; numerical contracts and tests
live in the shared package and root tests where appropriate. No demo imports
another demo. The two Burgers facades currently live in the shared package and
are tested independently; neither requires the other demo or surrogate training.

## Install and validate the shared foundation

Python 3.10+ and NumPy/SciPy are required. From the repository root, on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m unittest discover -s demos/planning/tests -v
.\.venv\Scripts\python.exe -m budgeted_science.burgers.validate
```

On POSIX use `.venv/bin/python` instead. After activating the environment,
`python -m budgeted_science.burgers.validate` is the same entry point. No Docker,
GPU, API key, or paid model call is needed. The older allocation pilot still runs
without NumPy/SciPy; see its own README.

Validation writes error/work tables, recoverability diagnostics, two scripted
interaction traces, configuration, software versions, and source hashes under
`tmp/burgers_foundation/`. Those files include private evaluator information and
are not agent inputs. See [shared interfaces and accounting](shared/README.md)
for the scientific contract and limitations.

## MMS verification CPU pilot

The [matched MMS menu protocol](docs/mms_alternatives_protocol.md) adds an
affine manufactured test, an alternative algebraic solver, and free Richardson
extrapolation. It compares six original-menu and six expanded-menu Luna/high
episodes at ten scientific credits, with a **$2 total batch API ceiling**.
Existing MMS commands, cases, claims, and saved results remain unchanged.
The [completed matched comparison](docs/mms_alternatives_results.md) scored
6/6 with both menus. Luna used only the free Richardson addition (five cases),
not the two paid alternatives; the task remained easy. API upper bound: $0.268.

The separate [six-study MMS verification CPU pilot](docs/mms_verification_results.md)
uses a 2-D advection-diffusion equation and scores point-value accuracy and a
finite-grid code-order claim separately. A simple study-aware CPU rule solves
6/6 at 10 credits; this is a working toy, not yet a difficult agent benchmark.
See its [protocol and commands](docs/mms_verification_protocol.md). No model calls
or changes to earlier verification experiments are included.

The [MMS Luna evaluation protocol](docs/mms_luna_protocol.md) adds an optional
logged six-case Luna/high batch with the same ten-credit science and a $2 total
API cap. Use `python -m budgeted_science.agents.mms_catalog --dry-run` for an
offline rehearsal; only explicit `--live` accesses the API.

The [completed Luna/high run](docs/mms_luna_results.md) got both claims right on
6/6 studies, averaging 9.4020 credits. The CPU study-aware rules also get 6/6
with fewer credits; this remains a working demonstration, not a hard benchmark.

## Initial implementation principles

The separate [hosted-Python verification prototype](docs/verification_python_protocol.md)
lets Luna/high write analysis code in an OpenAI sandbox, using public predator-prey
study files and generic raw-trajectory requests. No agent code executes locally.
Its first test is one existing development case at five scientific credits and a
$2 combined model/hosting ceiling; this changes the interface, not claim difficulty.
The [integration tests](docs/verification_python_results.md) preserve the first
interrupted attempt and a separately authorized successful fresh run: Luna and
the CPU verifier both correctly reject the claim using five credits. Luna wrote
its own analysis, but one accurate rerun still suffices for this case.

- CPU-only scientific computation and training; API-hosted agents use a separate
  optional integration. Classical controls run without API credentials.
- Structured actions executed by trusted numerical tools. No Docker, GPU, or
  arbitrary execution of agent-generated code is required for the first pilots.
- Explicit budgets, complete action/cost records, and private final evaluation.
  Keep hidden instance state and test answers out of agent-visible evidence.
- Separate scientific credits, actual execution costs, and agent API expenditure.
- Compare against competent numerical baselines; retain failed and abandoned work
  in reporting. Small pilots demonstrate the protocol, not broad agent rankings.

Next experiments can build on these contracts: budget/price sweeps, numerical
policies, and fixed imperfect-model banks. The current validation runner is not
an agent benchmark. Later coding-enabled evaluation needs separate isolation and
must account for lawful shortcuts: this restricted Burgers family also has fast
Cole-Hopf solutions, so it does not make expensive simulation unavoidable.

Raw data, generated models, run outputs, and credentials stay out of Git by
default. Curated, reviewed summaries can go in `docs/` for a self-contained
proposal appendix; readers should not need to inspect code to understand results.

## Logged planning episode

The separate [finite-grid support audit](docs/ambiguity_luna_results.md) runs
Luna/high on the two frozen ambiguity claims at two scientific budgets, with a
$2 whole-batch API cap and complete logs. Its dry-run is entirely offline.
The [report-style comparison](docs/ambiguity_report_luna_results.md) removes audit
strategy hints and uses neutral evidence references while preserving that science.

The dry-run uses a scripted fake model, does not read credentials, and makes no
network calls. After installing the numerical package:

```powershell
python demos/planning/src/run_agent.py --dry-run
```

Each run writes a frozen prompt/schema, full API-visible event log, complete
numerical records, readable transcript and paired comparison report under ignored
`demos/planning/runs/`. Inspect the [protocol](docs/planning_agent_runner.md) before
authorizing `--live`. Live mode requires `pip install -e '.[agents]'`, uses
`gpt-5.6-sol` with high reasoning, and enforces a separate $2 API spending bound.
Installation, tests and ordinary imports never start paid calls.
