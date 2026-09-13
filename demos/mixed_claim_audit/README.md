# Mixed scientific claims with shared evidence

Six claims about numerical accuracy, target agreement, cumulative abundance,
intervention effects, recovery and population composition. Reuses the existing
predator-prey environment with **32 credits and 1/8/12-credit prices**. The
older point-claim study and all previous results are preserved.

See the [frozen protocol](../../docs/mixed_claim_audit_protocol.md).

The [completed comparison](../../docs/mixed_claim_audit_results.md) reports
Luna/high at 5/6 correct, one wrong and 27 credits; the fixed classical
baseline gets four correct and two abstentions at 32 credits. Full
transcripts, resource purchases, the 52-credit CPU-only diagnostic and
the explanation/error qualifications are linked there.

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m budgeted_science.agents.mixed_claim_audit validate
.\.venv\Scripts\python.exe -m budgeted_science.agents.mixed_claim_audit prepare
.\.venv\Scripts\python.exe -m budgeted_science.agents.mixed_claim_audit dry-run <prepared-directory>
.\.venv\Scripts\python.exe -m budgeted_science.agents.mixed_claim_audit live <prepared-directory>
.\.venv\Scripts\python.exe -m budgeted_science.agents.mixed_claim_audit render <episode-directory>
```

`validate` runs CPU references and the fixed policy at 32 and 52 credits; the
latter is a complete-evidence diagnostic, not a matched agent comparison.
`prepare` reruns the independent 32-credit control and freezes the study,
sources, prompts, schemas and configuration. `dry-run` is a fake-model test
with zero real API spending. Only `live` accesses credentials or the API;
invoke it only after explicit owner authorization. It is locked to one
Luna/high attempt, 32 scientific credits and a $1 API ceiling.

Full logs and artifacts are saved in unique ignored `runs/` directories.
No auto-retries, model substitutions or limit increases. Source/input
mismatches prevent launch. Inspection checkpoints are not crash-resume
support. Rendering uses saved logs only. No arbitrary Python or extra
scientific tools are exposed to the model.
