# Scientific claim verification: predator-prey toy

## Small CPU heat-workflow audit

The [four-study implementation](../../docs/heat_workflow_results.md) is separate
from the predator-prey, transport and MMS demos. It tests the complete study
workflow using a tiny heat-plate problem, including incorrect coordinate
extraction and boundary configuration. It contains no agent/API runner.

```powershell
python -m budgeted_science.heat_workflow.experiment validate
python -m budgeted_science.heat_workflow.experiment run
python -m budgeted_science.heat_workflow.experiment render PATH_TO_RUN
```

Each run creates a unique ignored directory here under `runs/`, with four public
study folders, private evaluation records, eight independent CPU-control traces,
numerical arrays, source hashes, and a report. Each public `analysis.py` can be
executed on its neighboring `trajectory.npz`. These are repository-authored
scripts, not untrusted agent code. No scientific budget cap is imposed; this
prototype measures workflow errors and records computational work/runtime.

## MMS alternative-tool comparison

The [MMS menu protocol](../../docs/mms_alternatives_protocol.md) adds affine
manufactured tests, same-operator ILU-GMRES checks, and Richardson extrapolation
to the existing 2-D toy. It preserves both claims and the ten-credit limit.
Six cases receive each menu in fresh Luna/high episodes, with **$2 total**.

```powershell
python -m budgeted_science.agents.mms_alternatives_catalog --cpu
python -m budgeted_science.agents.mms_alternatives_catalog --dry-run --prepared PATH_TO_CPU_RUN
python -m budgeted_science.agents.mms_alternatives_catalog --live --prepared PATH_TO_CPU_RUN
python -m budgeted_science.agents.mms_alternatives_catalog --render PATH_TO_SAVED_BATCH
```

CPU/dry-run commands never read credentials or call the API. Live mode requires
explicit authorization. The original complete CPU route remains available;
adding alternative checks is not assumed to make the task difficult.

The [completed MMS comparison](../../docs/mms_alternatives_results.md) scored
both claims correctly on 6/6 studies with either menu. Richardson was used on
five expanded-menu cases; neither new paid check was called. The full batch's
API upper bound was $0.268. All twelve transcripts and CPU diagnostics are
linked in the report.

## Alternative-tool menu experiment

The [matched-menu protocol](../../docs/claim_verification_alternatives_protocol.md)
retains the original five-credit peak claim and adds three genuine numerical
alternatives: incremental integration tightening, output bisection and Radau
cross-checking. Five existing studies receive original and expanded menus, with
independent budgets. The original successful two-check route remains available.

```powershell
python -m budgeted_science.agents.verification_alternatives_catalog --cpu
python -m budgeted_science.agents.verification_alternatives_catalog --dry-run --prepared PATH_TO_CPU_RUN
python -m budgeted_science.agents.verification_alternatives_catalog --live --prepared PATH_TO_CPU_RUN
python -m budgeted_science.agents.verification_alternatives_catalog --render PATH_TO_SAVED_RUN
```

The optional live comparison is Luna/high with ten fresh slots and a **$2 total
batch ceiling**. Explicit live mode is required; old commands remain unchanged.

The [completed comparison](../../docs/claim_verification_alternatives_results.md)
scored 5/5 with each menu. Luna used added tools on three of five expanded-menu
cases, but accuracy and scientific expenditure were unchanged. Total API upper
bound: $0.073. Full transcripts and CPU diagnostics are linked in the report.

## Reconstruction diagnostics and forecast ambiguity

The [latest CPU follow-up](../../docs/verification_reconstruction_and_ambiguity.md)
keeps original verdict scores intact and evaluates their cited check forecasts.
It also provides two matched forecast-support cases on one system, with 125
public parameter candidates (not 125 studies), bounded-error observations and
mechanically checked evidence. Its finite-grid acceptance does not establish
continuous identifiability. Commands, resources, results and limitations are
in the linked report; no new model/API calls are included.

## Numerical fitting and forecast audit (CPU only)

The separate `budgeted_science.fit_prediction_verification` package replaces
the earlier trivial preprocessing stage with numerical parameter fitting.
Both fitting and forecasting consume metered RHS work. Ten development studies
share two systems; six controls run at three caps. Fixed-split and adaptive
controls both score 10/10 at four credits, so no further paid run was launched.
See the [full setup, results, limitations and traces](../../docs/fit_prediction_verification_results.md).

```powershell
.\.venv\Scripts\python.exe -B -m budgeted_science.fit_prediction_verification.experiment cpu
.\.venv\Scripts\python.exe -B -m budgeted_science.fit_prediction_verification.experiment render --path PATH_TO_RUN
```

Run these commands from the repository root. The second command regenerates
saved reports and policy transcripts offline. There is no model adapter for
this revision. Original studies, old runners and saved results remain unchanged.

## Small transport PDE experiment

The independent `budgeted_science.transport_verification` module adds 12 claims
across three 1-D transport systems, general reruns, a four-credit work budget
and five CPU controls. See [setup, results and commands](../../docs/transport_verification_results.md).
Several fixed rules score 12/12. The [subsequent Luna/high run](../../docs/transport_verification_luna_results.md)
also scored 12/12 under the same four-credit limit; total API upper bound was
$0.1601. This catalog does not establish adaptive-auditing value. The
[runner protocol](../../docs/transport_verification_agent_protocol.md) documents
the $2 whole-batch cap and complete logs. Earlier demos below remain unchanged.

## Claim-specific revision (CPU only)

The separate `budgeted_science.claim_verification_qoi` package adds peak height,
peak time, and cumulative population at two tolerances each, with configurable
Euler/RK2 integration and output grids. It has an 8-credit work-proxy budget,
not the previous flat-check prices. There is no model adapter for this revision.

The [810-episode CPU pilot](../../docs/claim_verification_qoi_results.md) generated
54 development and 108 fresh claims. Fixed RK2 scored 106/108 fresh, randomized
checks 105/108, fixed Euler 99/108, and the adaptive heuristic 96/108. It remains
too easy to demonstrate an adaptive-auditing advantage. No paid calls were made.

~~~powershell
.\.venv\Scripts\python.exe -B -m budgeted_science.claim_verification_qoi run
.\.venv\Scripts\python.exe -B -m budgeted_science.claim_verification_qoi render PATH_TO_QOI_RUN
~~~

See the [complete revised protocol](../../docs/claim_verification_qoi_protocol.md).
The versions and commands below remain unchanged.

The [small budget sweep](../../docs/claim_verification_low_budget_results.md)
reuses 12 balanced development claims at four and two credits. Its affordable
fixed RK2 checks score 12/12 and 11/12 respectively; four methods produce 96
CPU episodes, with no model calls or fresh-system evaluation.

~~~powershell
.\.venv\Scripts\python.exe -B -m budgeted_science.claim_verification_qoi.budget_sweep run
.\.venv\Scripts\python.exe -B -m budgeted_science.claim_verification_qoi.budget_sweep render PATH_TO_SWEEP
~~~

## Preserved original versions

Audit a **completed computational study**, not an unknown physical system.
Every report claims that the maximum of species A on [0,8] is accurate within
5%. This is numerical solution verification, not experimental validation.

The completed CPU milestone provides 30 development studies on six systems,
three report formats, two paid checks, objective verdict scoring, and durable
scripted episodes. The scientific package has no credential access or LLM judge.
An optional [logged agent runner](../../docs/claim_verification_agent_protocol.md)
connects these tools to an explicitly selected model; paid calls require
`--live` and authorization. No arbitrary-code workspace is available.

See the [measured commissioning report](../../docs/claim_verification_toy_results.md).

A [fixed two-check numerical baseline](../../docs/claim_verification_baseline_results.md)
now scores 30/30 on this development catalog at 5 credits per study. Its
verdicts are calculated from purchased results, not predetermined fixtures.

The [first live Terra/high episode](../../docs/claim_verification_terra_first_result.md)
correctly accepted the first catalog study after sampling then integration
refinement, using 5 credits and an API cost upper bound of USD 0.044409.
The subsequent [Luna/high catalog evaluation](../../docs/claim_verification_luna_catalog_results.md)
scored 30/30 at 5 credits each, matching the fixed verifier. It correctly
accepted all 18 valid claims and rejected all 12 invalid claims, with no
abstentions, incomplete episodes or retries. Terra remains a one-case result.

## Run

### Separate incremental-check CPU calibration

The [incremental pilot](../../docs/claim_verification_incremental_results.md)
keeps the peak claim and 5% tolerance but uses 30 new all-Euler studies and
8 credits. Integration checks halve the current timestep (3 credits);
sampling checks bisect current output intervals (2 credits). It does not
replace the original task described below. Four numerical policies scored
29/30 each, and same-evidence extrapolation gave 30/30: this is a retained
development finding, not a successful difficulty increase.

~~~powershell
.\.venv\Scripts\python.exe -B -m budgeted_science.claim_verification_incremental run
.\.venv\Scripts\python.exe -B -m budgeted_science.claim_verification_incremental render PATH_TO_INCREMENTAL_RUN
~~~

These commands require no OpenAI SDK, credentials or paid calls. The existing
model adapter still implements the original five-credit instant refinements;
it has not been connected to the incremental environment.

The [severity-recalibrated follow-up](../../docs/claim_verification_recalibrated_results.md)
selects valid/invalid integration, sampling and mixed-error studies. It retains
36 development studies and 35 fresh studies, with one explicit commissioning
failure. With extrapolation as their actual submitted estimator, all four
classical policies score 35/35 fresh. The code remains CPU-only:

~~~powershell
.\.venv\Scripts\python.exe -B -m budgeted_science.claim_verification_incremental.recalibrated run
.\.venv\Scripts\python.exe -B -m budgeted_science.claim_verification_incremental.recalibrated render PATH_TO_RECALIBRATED_RUN
~~~

Each run freezes its rules and creates a unique ignored directory. Earlier
catalogs, raw results and default commands retain their original behavior.

For model evaluation of this revised task, use the separate
[incremental Luna protocol](../../docs/claim_verification_incremental_agent_protocol.md).
The [completed live batch](../../docs/claim_verification_incremental_luna_results.md)
scored 35/35, matching all four saved CPU policies. It used eight scientific
credits per case at most and $0.143–$0.396 in total API accounting bounds, below
the new $2 whole-batch cap. Complete local transcripts and artifacts are linked
from the results report. Standalone resume is blocked for batch-funded episodes
until their shared allowance is reconciled. The older model commands below
still use the original five-credit task.

### Original five-credit task

The optional model runner supports `--inspect`, `--dry-run`, `--live`,
`--render PATH`, and explicit `--resume PATH` with live/dry mode preserved.
Its defaults are GPT-5.6 Terra, high reasoning, 5 audit credits, and a cumulative
USD 3 API ceiling. Resume preserves prior purchases, messages, limits and
uncertain API reservations; it does not create a new evaluation sample.
See the [agent protocol](../../docs/claim_verification_agent_protocol.md) for commands.

From the repository root, using the existing editable installation:

~~~powershell
.\.venv\Scripts\python.exe -m budgeted_science.claim_verification validate
.\.venv\Scripts\python.exe -m budgeted_science.claim_verification calibrate
~~~

Calibration prints a unique catalog directory. Substitute that path below.
The accepted development catalog has these stable example IDs:

~~~powershell
$catalog = 'demos/claim_verification/data/20260911T222704Z-catalog-791b1692dd'
.\.venv\Scripts\python.exe -m budgeted_science.claim_verification dry-run --catalog $catalog --case study-13cc000ca7a7e1 --fixture accept
.\.venv\Scripts\python.exe -m budgeted_science.claim_verification dry-run --catalog $catalog --case study-34e51260260c36 --fixture reject
.\.venv\Scripts\python.exe -m budgeted_science.claim_verification dry-run --catalog $catalog --case study-dd1a07dbc0bc77 --fixture abstain
.\.venv\Scripts\python.exe -m budgeted_science.claim_verification dry-run --catalog $catalog --case study-b4566d6d99ce6b --fixture interrupted
~~~

The convenience entry point is `python demos/claim_verification/src/run_verification.py`
with the same arguments. A fresh checkout must generate its own catalog first;
raw catalog/run directories are deliberately not tracked.

Regenerate a saved catalog report or episode transcript without executing tools:

~~~powershell
.\.venv\Scripts\python.exe -m budgeted_science.claim_verification render PATH_TO_CATALOG_OR_EPISODE
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_claim_verification.py -v
~~~

## What the auditor receives

The public package contains four artifact roles: report, solver log, trajectory,
and analysis record. The report takes one of three forms (research report,
notebook, memo) while preserving facts. It states the claimed maximum and
tolerance, initial conditions, interval, numerical configuration, and extraction
method. The initial model message describes the task and tools; the script
retrieves the report through the artifact interface.

Only pass `Episode(...).tools` to an auditor. The episode, study dictionary,
reference data, generation labels, physical parameters, and evaluation are
private harness material. This is trusted-process separation, not a security
sandbox against Python introspection. No unknown-parameter fitting is required.

| Action | New charge | Contract |
|---|---:|---|
| `list_artifacts()` | 0 | Names and IDs for existing or purchased public artifacts. |
| `read_artifact(id, offset=0, limit=200)` | 0 | Return up to 200 lines; follow `next_offset`. |
| `recompute_peak(run_id)` | 0 | Maximum of existing stored x samples only. |
| `refine_integration(run_id)` | 3 | DOP853 at 1e-10/1e-12, preserving output times. |
| `refine_sampling(run_id)` | 2 | Same integration configuration, output every 0.0025. |
| `compare_runs(run_ids)` | 0 | Numerical differences, not certified error bounds. |
| `budget()` | 0 | Total, remaining, ledger, prices, and original run ID. |
| `submit(verdict, diagnosis, evidence_ids, justification)` | 0 | ACCEPT, REJECT, or ABSTAIN; end immediately. |

Both checks fit the 5-credit budget and may be chained in either order.
Submitting early is allowed but not rewarded. A repeated purchased numerical
configuration is free, including a no-op refinement. A backend cache hit still
costs the normal price for a new episode. Invalid and unaffordable requests do
not execute; executed failures are charged and cached. A failure to log before
execution closes the episode without charging unperformed computation.

Successful purchases return compact peak/configuration data and artifact IDs;
full trajectories remain retrievable. Sampling refinement reruns the same
numerical integrator and samples its retained interpolant; it does not infer
missing peaks by interpolation of sparse published samples.

## Scripted fixtures, not a classical general verifier

The named fixtures have **predetermined verdicts**. They test tool interactions,
charges, logging, and termination, not scientific reasoning. ACCEPT and REJECT
use the same two-check script; ABSTAIN inspects the report and submits; the
interrupted fixture stops after the integration purchase.

The separate fixed baseline reads the structured public analysis result,
buys integration then sampling refinement, and compares the reported peak with
the combined run using the 5% threshold. Run it independently of the fixtures:

~~~powershell
.\.venv\Scripts\python.exe -m budgeted_science.claim_verification.fixed_baseline --catalog $catalog
.\.venv\Scripts\python.exe -m budgeted_science.claim_verification.fixed_baseline --render PATH_TO_BASELINE_RUN
~~~

It uses only public audit tools, not private labels or references, and has an
independent five-credit ledger per study. It is a task-specific baseline, not
a general classical verifier for arbitrary scientific reports.

An optional `--script FILE.json` supplies a JSON list of message or tool-call
objects. Tool steps accept `tool`, `arguments`, `call_id`, and optional `save_as`.
An argument such as `$integration.run_id` reuses a previous result saved as
`integration`. `{"interrupt": true}` exercises partial-run preservation.
Duplicate call IDs replay the original response without repeating a purchase.
Scripted episodes stop at the first valid submission, 30 tool requests, five
minutes, or interruption. That offline script runner has no crash-resume or
automatic retry. The separate model runner has the limits and explicit
checkpoint/resume support described in its linked protocol.

Private scoring compares the **original printed claim**, not an improved run,
with the reference. A binary verdict is correct iff it matches the 5% label;
ABSTAIN is a valid submission but not a correct binary answer. Report coverage,
false acceptance/rejection with their class denominators, incomplete outcomes,
and spending separately. Explanations are not semantically scored.

Optional literal citations of the form `run-ID Q=number` are checked against
available run peaks with 1e-9 relative / 1e-12 absolute arithmetic tolerance.
Other prose and numbers are explicitly ungraded; this does not establish
diagnosis correctness or evidential sufficiency.

## Manufactured-solution CPU pilot

The separate 2-D `budgeted_science.mms_verification` toy has six development
studies and three diagnostic families. It scores the original point-value claim
and a finite-grid near-second-order claim separately. The study-aware CPU rule
gets 6/6 at 10 credits; the full fixed checklist gets 6/6 at 20 credits. This is
an executable verification illustration, not a demonstrated difficult benchmark.

```powershell
python -m budgeted_science.mms_verification.experiment validate
python -m budgeted_science.mms_verification.experiment cpu
python -m budgeted_science.mms_verification.experiment render <saved-run-directory>
```

See the [protocol](../../docs/mms_verification_protocol.md) and
[results](../../docs/mms_verification_results.md). Runs are unique, local and
ignored under this demo's `runs/` directory. No API/credential access or changes
to previous catalogs are included.

The optional [Luna/high runner](../../docs/mms_luna_protocol.md) uses the same six
MMS studies and ten-credit interface, with a shared $2 batch API ceiling:

```powershell
python -m budgeted_science.agents.mms_catalog --dry-run
python -m budgeted_science.agents.mms_catalog --live
python -m budgeted_science.agents.mms_catalog --render <saved-batch-directory>
```

It imports verified saved CPU comparisons and never reruns them during a model
episode. Raw transcripts, responses and numerical records remain local/untracked.
The [six-case live results](../../docs/mms_luna_results.md) are 6/6 both-correct,
with a $0.136 conservative total API bound. CPU study-aware rules also solve all
six using fewer scientific credits; no performance advantage is claimed.

## Three-stage transport study pilot (previous experiment)

The independent `budgeted_science.study_verification` package audits input
normalization, simulation and exposure analysis. It uses 12 development claims
across two systems, not the older predator-prey catalog. See the
[protocol and commands](../../docs/study_verification_protocol.md). All claims
are scored by final numerical error; diagnoses are not semantically graded.
The optional `budgeted_science.agents.study_catalog` runner uses Luna/high and
a $2 whole-batch ceiling. Tests/dry-runs never access credentials or paid APIs.

## Records and limits

### Hosted Python analysis (independent extension)

The heat-workflow counterpart uses `budgeted_science.agents.heat_workflow_agent`
with `prepare`, `dry-run <prepared>`, explicit `live <prepared>`, and
`render <campaign>` commands. Four isolated Luna/high episodes share a $2 total
model/hosting ceiling, with no scientific-credit cap. The
[first attempt and complete logs](../../docs/heat_workflow_luna_results.md) record
three abstentions and one tool-limit interruption. The
[separately authorized revised run](../../docs/heat_workflow_luna_continuation_results.md)
uses two Python calls per response and `continue_audit` to preserve the session
across responses. It completed all four claims correctly, with a $0.394 total
upper bound. Old attempts are preserved and are not evidence of task difficulty.

See the [protocol](../../docs/verification_python_protocol.md). The
`budgeted_science.agents.verification_python` entry point supports `--prepare`,
`--dry-run --prepared <directory>`, explicit `--live --prepared <directory>`,
and `--render <episode-directory>`. One Luna/high development case retains five
scientific credits with a $2 combined model/hosting ceiling. The model writes
Python in an isolated hosted container; local simulation functions return raw
files, not precomputed audit results. Existing tools and catalogs are unchanged.
All API-visible code/output is saved in `python.md` and the raw event archive.
The [integration-test report](../../docs/verification_python_results.md) preserves
the first incomplete attempt and the separately authorized successful fresh run.
Luna/high wrote its own analysis and correctly rejected the claim, using three
Python executions and one five-credit simulation purchase. The CPU verifier is
also correct; the coding interface has not made this case demonstrably harder.

For the newer finite-grid forecast-support toy, use the separate
`budgeted_science.agents.ambiguity_agent` runner. See its
[protocol and results](../../docs/ambiguity_luna_results.md): two claims at
32/256 credits, Luna/high, $2 total API cap, and sequential agent-selected batches
of candidate checks. This does not alter the older catalogs below.
The separate [report-style condition](../../docs/ambiguity_report_luna_results.md)
uses the same cases and budgets without the audit-strategy instructions or a
dedicated witness field. Its new runner is `budgeted_science.agents.ambiguity_report_catalog`.

Generated studies are under ignored `data/`; scripted logs are under ignored
`runs/`. Manifests pin source hashes, numerical versions, budget, and limits.
Public artifacts are separate from private study/reference/evaluation records.
The saved catalog has integrity hashes; loading an altered catalog fails.
Requests, exact returned results, messages, numerical artifacts, charges,
failures, and available partial logs are retained. Offline rendering does not
rerun science or contact an API.

The 30 variants share only six development systems, inspected during planning.
There are 18 within-tolerance and 12 outside-tolerance claims. Templates are
balanced, but this small fixed claim family may admit metadata shortcuts.
It does not establish general report understanding, adaptive-policy value,
confidence, early-stopping efficiency, or physical validity. No general
classical verifier is required or claimed.
