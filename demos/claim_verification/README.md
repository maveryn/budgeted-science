# Scientific claim verification: predator-prey toy

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

## Records and limits

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
