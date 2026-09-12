# Protocol notes and proposal appendices

Keep short, reviewed material that explains each demo without requiring a reader
to inspect its implementation. Detailed scientific contracts remain demo-specific.

An appendix for a completed pilot should cover:

1. Task, hidden quantities, supplied evidence, legal actions, and resource limits.
2. Exact submission/scoring rules and classical baselines.
3. A short annotated interaction illustrating the decision loop.
4. Reproducible experiment settings and results, including failures and costs.
5. What the toy establishes, limitations, and the next scientific application.

Distinguish planned experiments from completed runs. Record configuration,
code revision, model version, and evaluation conditions for reported results.
Current curated results include the [two-baseline resource-planning pilot](resource_planning_toy_results.md)
and its [protocol](resource_planning_toy_protocol.md), the
[resource-planning agent protocol and audit](resource_planning_agent_run.md), the [Burgers foundation validation](burgers_foundation_results.md)
and the preserved [allocation/OCBA pilot](ocba_pilot_results.md), with its
[protocol](ocba_pilot_protocol.md). The foundation validates numerical and tool
contracts, not agents or adaptive policies.

The [claim-verification commissioning report](claim_verification_toy_results.md)
adds a completed-study audit toy with three report formats, 30 development
variants, numerical check effects, and scripted logging fixtures. It reports
no LLM performance and does not require a general classical verifier.
Subsequently, the [fixed two-check verifier](claim_verification_baseline_results.md)
scored 30/30 on the development catalog. The [first Terra/high smoke test](claim_verification_terra_first_result.md)
correctly accepted one sound study at 5 credits. Its
[agent protocol](claim_verification_agent_protocol.md) documents logs, spending
limits, offline inspection and explicit same-episode resume.
The subsequent [Luna/high evaluation](claim_verification_luna_catalog_results.md)
completed all 30 studies with 30/30 correct verdicts, matching the fixed
numerical verifier at the same 5-credit budget. All raw transcripts remain local.

The separate [incremental-check CPU calibration](claim_verification_incremental_results.md)
retains a negative design result: four policies each scored 29/30 on 30 new
all-Euler studies at 8 credits, and numerical extrapolation gave 30/30.
Incremental tools alone did not create a challenging allocation problem.
The original model evaluations and five-credit task are unchanged.

The [severity-recalibrated follow-up](claim_verification_recalibrated_results.md)
adds balanced integration/sampling/mixed cases and makes extrapolation the
submitted estimator. All four CPU policies score 35/35 on fresh systems;
one requested mixed-invalid study remains an explicit commissioning failure.
No new model evaluation or adaptive-allocation advantage is claimed.

The [incremental Luna results](claim_verification_incremental_luna_results.md)
record 35/35 correct, matching all four CPU policies, with $0.143–$0.396 total
API accounting bounds. The [runner protocol](claim_verification_incremental_agent_protocol.md)
documents the eight-credit adapter, complete logging, hard $2 whole-batch ceiling,
and batch-funded resume restrictions. All 417 regression tests passed.

The [MMS verification CPU pilot](mms_verification_results.md) introduces a separate
2-D manufactured-solution suite with six development studies, two independently
scored claims and five CPU controls. The study-aware rule solves all six at
10 credits; no difficult-agent-benchmark claim is made. The
[protocol](mms_verification_protocol.md) defines numerical assumptions, budgets,
tools, reproducible commands and records.

Do not copy credentials, hidden test instances, personal application materials,
or internal reviewer discussions into this folder. Detailed evaluator-only
validation output stays in ignored `tmp/burgers_foundation/`.
