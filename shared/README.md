# Shared utilities

Reserved for small helpers that demonstrably benefit multiple demos: budget
ledgers, structured-action dispatch, agent adapters, reproducible run records,
and reusable numerical generators or learner code.

No shared framework is implemented yet. Add only what the first working demos
need; do not require a central service or a root-level orchestrator.

- Shared code must never import a demo.
- Each demo owns its scientific contract, score, configuration, and entry point.
- Shared utilities carry no global episode state. Reusing code does not share
  acquired evidence, private seeds, fitted artifacts, or scores between episodes.
- If a helper becomes a required dependency, declare it explicitly in that demo's
  setup instructions; do not rely on an undocumented working-directory import.
- Keep agent-visible observations separate from evaluator-only records. A Git
  ignore rule is not an access-control or execution-isolation mechanism.
