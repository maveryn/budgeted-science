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

## Matched 20-credit follow-up

Prepare each requested model explicitly, then use the printed preparation
directory for its dry-run/live commands:

```powershell
.\.venv\Scripts\python.exe -m budgeted_science.agents.multi_claim_audit prepare --budget 20 --model gpt-5.6-luna
.\.venv\Scripts\python.exe -m budgeted_science.agents.multi_claim_audit prepare --budget 20 --model gpt-5.6-sol
```

Each model keeps high reasoning and its own $1 API ceiling. Prompts and tools
are identical across models; only the scientific allowance changes from the
original study. Model and budget cannot be overridden after preparation.
The fixed control retains its acquisition order, so the unaffordable second
target measurement is not executed or charged, and its C6 verdict is ABSTAIN.
Default commands still prepare the original Luna/32 configuration. Previously
saved results and logs are not overwritten.

The [completed 20-credit comparison](../../docs/multi_claim_twenty_results.md)
reports purchases, verdicts, abstentions, API usage, and the important
qualification to Luna's C6 explanation.

## Matched 12-credit follow-up

```powershell
.\.venv\Scripts\python.exe -m budgeted_science.agents.multi_claim_audit prepare --budget 12 --model gpt-5.6-luna
.\.venv\Scripts\python.exe -m budgeted_science.agents.multi_claim_audit prepare --budget 12 --model gpt-5.6-sol
```

Use the printed preparation directory with `dry-run` and, only when explicitly
authorized, `live`. Model, high reasoning, $1 API ceiling, tools, study and
pricing follow the same safeguards as above. The fixed control buys one
high simulation, cannot afford either target measurement, and abstains on
C5/C6 with four credits unused. No fallback or forced expenditure is added.

The [completed 12-credit comparison](../../docs/multi_claim_twelve_results.md)
records both models at 6/6 using one high plus four low simulations, but
both have the wrong error direction in their C6 explanation. The fixed
control gets four correct and two abstentions. The report preserves that
qualification, all purchases, API accounting and links to full transcripts.
