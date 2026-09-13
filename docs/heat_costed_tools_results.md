# Costed heat tools: Luna/high and Sol/high results

## Outcome

Both models returned **4/4 correct verdicts**, with no abstentions or incomplete
episodes, on the same four heat studies. Each episode had **8 scientific
credits**. Scientific credits are synthetic numerical-service prices, separate
from API dollars. There was no hosted Python in this evaluation.

| Method | Correct verdicts | Total scientific credits (four cases) | Mean credits per case | Paid numerical jobs | API cost upper bound |
|---|---:|---:|---:|---:|---:|
| GPT-5.6 Luna, high | 4/4 | 19.184573 | 4.796143 | 7 | $0.05660355 |
| GPT-5.6 Sol, high | 4/4 | 20.246097 | 5.061524 | 8 | $0.82697500 |
| Fixed independent reconstruction | 4/4 | 20.246097 | 5.061524 | 8 | $0 |
| Fixed refinement-only | 2/4 | 16 | 4 | 4 | $0 |

All paid model purchases were **`solve_matrix`**. Neither model bought
`iterate`, `remesh`, or `perturb_boundary`, despite all four services being
available with disclosed costs. Most episodes used two grids, 17 and 33 nodes.
Luna omitted the coarse-grid check in the spatial-extraction case, using one
33-node solve instead. This accounts for the entire scientific-cost difference.
The comparison does not establish that either model is generally more efficient.

The combined API upper bound was **$0.88357855**, below the frozen $6 maximum
($3 per model batch). Bounds include conservative token pricing, not an invoice.
No model was substituted, no episode was automatically retried, and no limit was
increased. All request usage settled; there were no uncertain reservations.

## Individual outcomes and tool costs

| Study | Truth | Luna verdict | Luna credits | Luna paid jobs | Sol verdict | Sol credits | Sol paid jobs |
|---|---|---|---:|---:|---|---:|---:|
| Sound (`study-b116ba51e1`) | ACCEPT | ACCEPT | 5.061524 | 2 | ACCEPT | 5.061524 | 2 |
| Premature stopping (`study-86d7c8982e`) | REJECT | REJECT | 5.061524 | 2 | REJECT | 5.061524 | 2 |
| Spatial extraction (`study-8ef5b4e4cd`) | REJECT | REJECT | 4.000000 | 1 | REJECT | 5.061524 | 2 |
| Boundary mismatch (`study-e11e3c30ec`) | REJECT | REJECT | 5.061524 | 2 | REJECT | 5.061524 | 2 |

| Model | `iterate` credits | `remesh` credits | `solve_matrix` credits | `perturb_boundary` credits | All function requests, including free/invalid |
|---|---:|---:|---:|---:|---:|
| Luna | 0 | 0 | 19.184573 | 0 | 45 |
| Sol | 0 | 0 | 20.246097 | 0 | 43 |

Luna made two invalid requests to read the trajectory through `read_artifact`;
the service returned an instruction to use paginated `record`. Those invalid
calls incurred no scientific charge and did not interrupt the investigations.
Sol made no invalid function requests. Free reads and integrations still add
conversation tokens and therefore can contribute to API cost.

## What the agents did

Both models inspected configurations, solver logs, analysis source and reported
values, then chose explicit-boundary matrix solves and integrated the resulting
fields over the requested rectangle. Typical 17-node and 33-node values were
0.31277021040 and 0.31222308899. Several explanations used a second-order
extrapolation near 0.31204. This was the agents' analysis of returned numbers,
not an exact-reference answer supplied by a tool.

For the transposed-extraction study, both models reproduced the incorrect
reported value with transposition and computed the requested quantity without
transposition. Luna checked it with one matrix solve; Sol also used the coarser
grid. Explanations and diagnostic estimates are archived but are not semantically
scored. Correct binary verdicts do not certify every supporting calculation or
establish justified confidence.

## The larger menu did not remove the simple route

The matched reconstruction control remains 4/4 using the same two-grid route as
most model episodes. Moreover, before live execution we inspected its already
purchased **17-node-only** outputs: comparing 0.31277021040 with each original
claim would also give 4/4 correct verdicts. That single numerical job costs
**1.061524 credits**, followed by free integration.

This coarse-only result is a diagnostic extracted from saved CPU traces, not an
additional set of model or CPU-policy episodes. It establishes that a cheap
one-solve path remains for these four labels; it does not certify the adequacy
of one grid for arbitrary studies. No lower-budget agent episodes were run.

Consequently, this experiment demonstrates functioning, objectively scored
**tool-cost accounting and model-driven tool selection**, but not a challenging
budget-allocation task. More available numerical tools did not force their use
or make a fixed one-solver approach fail. There is no savings objective or
early-stopping reward, so unused credits and spending beyond the cheapest
successful path should not be interpreted as a separate scored failure.

These four deliberately constructed development studies share one physical
problem. Their three large invalid-claim errors and single sound control do not
establish performance on subtle flaws, harmless modifications, diverse systems,
or natural scientific reports. Always REJECT would score 3/4 here.

## Reproducibility, logs and verification

- [Frozen protocol and numerical prices](heat_costed_tools_protocol.md)
- [Live comparison and links to all eight transcripts](../demos/claim_verification/runs/20260913T000401Z-heat-costed-live-ed05368352/report.md)
- [Complete live logs and numerical artifacts](../demos/claim_verification/runs/20260913T000401Z-heat-costed-live-ed05368352/)
- [Frozen preparation, case payloads and CPU traces](../demos/claim_verification/runs/20260912T235400Z-heat-costed-prepared-802ce58a4e/)
- [Eight-slot offline rehearsal](../demos/claim_verification/runs/20260912T235442Z-heat-costed-dry-run-d27c4c0784/report.md)
- [Prior hosted-Python evaluation, preserved separately](heat_workflow_luna_continuation_results.md)

The 22 new tests and full eight-slot offline rehearsal passed before paid
execution. The full regression suite passed **783 tests** in 581.2 seconds;
the separate planning pilot passed **14**, totaling **797 passing tests**.
Coverage includes tariffs, independent budgets, free reuse, paid failures,
duplicate calls, invalid arguments, reference isolation, prompt matching,
nullable submissions, frozen provenance, campaign launch protection, uncertain
usage reservations, and offline regeneration. Older code behavior was retained.

Post-run checks verified all **88 generation requests** used the requested
model, high reasoning, standard service tier, `store=false`, sequential function
calls, and 32,768-token output limits. Every scientific ledger stayed within
eight credits. All eight episode transcripts, reports and evaluation JSON, plus
the campaign summary/report, regenerated byte-identically from saved events.
The original CPU artifact hashes and the frozen new source hashes remained
intact. No numerical tools or model calls were rerun during report regeneration.

| Model | Input tokens (all responses) | Output tokens, including reasoning | Included reasoning tokens | Sum of episode elapsed seconds |
|---|---:|---:|---:|---:|
| Luna | 202,683 | 4,944 | 2,971 | 122.29 |
| Sol | 148,763 | 4,158 | 1,847 | 138.01 |

Timings include model/network and local orchestration, not just numerical work.
The runs retain full API-visible messages, returned reasoning summaries,
encrypted reasoning replay, tool arguments/results, fields and ledgers. Raw
internal reasoning is unavailable. Credentials and raw runs remain local and
ignored by Git. No proposal documents or older experiments were changed, and
no changes were pushed.
