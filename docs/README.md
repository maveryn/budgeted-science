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
and its [protocol](resource_planning_toy_protocol.md), the [Burgers foundation validation](burgers_foundation_results.md)
and the preserved [allocation/OCBA pilot](ocba_pilot_results.md), with its
[protocol](ocba_pilot_protocol.md). The foundation validates numerical and tool
contracts, not agents or adaptive policies.

Do not copy credentials, hidden test instances, personal application materials,
or internal reviewer discussions into this folder. Detailed evaluator-only
validation output stays in ignored `tmp/burgers_foundation/`.
