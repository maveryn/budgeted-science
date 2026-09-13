# Paired predator–prey claim audit (CPU only)

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
