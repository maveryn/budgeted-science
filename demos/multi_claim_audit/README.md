# Predator-prey multi-claim audit

One short study, six related claims, 32 credits per investigator. The existing
predator-prey environment and 1/8/12-credit resource prices are reused from
resource planning. Four claims concern numerical accuracy; two concern the
simulated target. See the [protocol](../../docs/multi_claim_audit_protocol.md)
and [completed comparison](../../docs/multi_claim_audit_results.md): both the
fixed CPU control and Luna/high score 6/6 using 32 credits.

From the repository root, with the optional `agents` dependency installed:

```powershell
.\.venv\Scripts\python.exe -m budgeted_science.agents.multi_claim_audit prepare
.\.venv\Scripts\python.exe -m budgeted_science.agents.multi_claim_audit dry-run <prepared-directory>
.\.venv\Scripts\python.exe -m budgeted_science.agents.multi_claim_audit live <prepared-directory>
.\.venv\Scripts\python.exe -m budgeted_science.agents.multi_claim_audit render <episode-directory>
```

`prepare` runs numerical checks and the fixed CPU control without API calls.
`dry-run` uses a scripted fake, not a model evaluation. `live` executes one
Luna/high attempt with a $1 API ceiling, privately loading the existing root
credential file. Only invoke it with the repository owner's authorization.
A second launch from the same preparation is refused. No automatic retries or
limit increases. Prompts, schemas, sources and study must match preparation.

Unique ignored `runs/` directories contain complete logs, numerical artifacts,
transcripts and reports. Rendering uses saved logs only. Inspection checkpoints
are not crash-resume support. No arbitrary Python, hosted sandbox or physical
experiments are included. Earlier demos and results are preserved.
