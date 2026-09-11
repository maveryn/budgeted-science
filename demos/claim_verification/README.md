# Scientific claim verification: offline predator-prey toy

Audit a **completed computational study**, not an unknown physical system.
Every report claims that the maximum of species A on [0,8] is accurate within
5%. This is numerical solution verification, not experimental validation.

The completed CPU milestone provides 30 development studies on six systems,
three report formats, two paid checks, objective verdict scoring, and durable
scripted episodes. It has **no live mode, model transport, credential access,
LLM judge, or arbitrary-code workspace**.

See the [measured commissioning report](../../docs/claim_verification_toy_results.md).

## Run

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

An optional `--script FILE.json` supplies a JSON list of message or tool-call
objects. Tool steps accept `tool`, `arguments`, `call_id`, and optional `save_as`.
An argument such as `$integration.run_id` reuses a previous result saved as
`integration`. `{"interrupt": true}` exercises partial-run preservation.
Duplicate call IDs replay the original response without repeating a purchase.
Episodes stop at the first valid submission, 30 tool requests, five minutes,
or interruption. There is no crash-resume or automatic retry.

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
