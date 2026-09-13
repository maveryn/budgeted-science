# Paired predator–prey claim audit

The corrected follow-up now has a separate
[logged Luna/high adapter](../../docs/paired_claim_followup_luna_protocol.md).
It imports the six frozen v2 studies and CPU comparisons, gives the model all
32 credits with no forced initialization, and preserves every episode's
transcript, numerical artifacts and API records. The CPU-only commands below
retain their original behavior; paid execution requires an explicit `live`
command. No older results are replaced or pooled with the new evaluation.

The [completed six-study Luna run](../../docs/paired_claim_followup_luna_results.md)
returned **29/36 correct, four wrong and three abstentions**, using an average
of 30.17/32 credits. All specified-model claims were correct; target inference
accounted for the errors and abstentions. Total API upper bound was $0.18630.

A separate [matched Sol/high adapter](../../docs/paired_claim_followup_sol_protocol.md)
is offline-verified and ready. It preserves Luna's frozen science and records;
the proposed larger API-dollar cap needs approval before paid execution.

The opt-in [follow-up variant](../../docs/paired_claim_followup_results.md)
changes the target quantities and claim thresholds to test evidence-conditioned
computation. Its measurement-first adaptive policy gets 33/36 correct with no
wrong verdicts at 32 credits, versus 30/36 and no wrong verdicts for the best
uncertainty-aware fixed policy. A fixed intervention-label guess instead gets
34 correct and two wrong: the adaptive advantage is under the wrong-answer
penalty, not raw correct count. The corrected v2 report preserves the cheap
bypass that invalidated intermediate v1 and its subsequent construction fix.
The original variant below is preserved.

Run the new CPU variant with:

```powershell
.venv\Scripts\python.exe -m budgeted_science.paired_claim_audit.followup prepare
.venv\Scripts\python.exe -m budgeted_science.paired_claim_audit.followup run <prepared-directory>
.venv\Scripts\python.exe -m budgeted_science.paired_claim_audit.followup render <pilot-directory>
```

It compares two adaptive policies, 98 fixed acquisition/estimation policies,
and three blanket controls on the same six development studies. Logs remain
local and ignored. There is no API transport, credential access or automatic
agent run. The fixed measurement/follow-up search is restricted to the stated
menu, and all methods use the same approximate two-fit estimator.

Six development studies, arranged as three pairs, reuse the planning toy's
predator–prey dynamics and **1/8/12-credit** simulation/measurement prices.
Within each pair the report and free early evidence are identical, but three
target-related claim verdicts reverse. An investigator needs target evidence
to distinguish the paired worlds; candidate simulations alone cannot do that.

The [completed CPU comparison](../../docs/paired_claim_audit_results.md) tests
24 and 32 credits. All three measurement-first controls and the adaptive
heuristic get **36/36** correct at both budgets. Simulation-first gets 18
correct and abstains on 18. **This establishes useful evidence acquisition,
not an accuracy advantage for adaptive allocation.** No agent/API run was made.

## Run

From the repository root, using the existing numerical environment:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_paired_claim_audit.py -v
.venv\Scripts\python.exe -m budgeted_science.paired_claim_audit prepare
.venv\Scripts\python.exe -m budgeted_science.paired_claim_audit pilot <prepared-directory>
.venv\Scripts\python.exe -m budgeted_science.paired_claim_audit render <pilot-directory>
```

`prepare` freezes the six studies, policy settings, seeds and source hashes.
`pilot` runs eight CPU methods on both budgets with independent ledgers:
96 episodes, **not 96 different studies**. `render` uses only saved records.
Commands create unique ignored directories under `runs/`, never overwrite
earlier experiments, require no credentials, and contain no model transport.

Each episode retains public inputs, private reference/label data, full
trajectories, chronological tool calls and charges, policy diagnostics,
verdicts and a readable transcript. The campaign has a manifest, per-case
results and an aggregate report. Interrupted episodes are explicit; there is
no automatic retry or crash-resume in this CPU milestone.

## Interpretation

The report supplies two competing parameter fits. The policy assumes these
cover the target; they do cover these designed development worlds, although
the public task does not guarantee this. This is a restricted hypothesis
comparison, not open-ended parameter discovery. Low-model uncertainty and
verdict probabilities are heuristic, not validated confidence estimates.

Raw correct/wrong/abstain counts are retained alongside the proposed
**+1 / −2 / 0** utility. There is no spending penalty, savings bonus or
full-budget submission requirement. Earlier agent episodes had different
inputs and scoring and are not pooled or rescored here. Existing demos and
proposal documents are unchanged.
