# Mixed-claim audit: completed Sol/high continuation

Executed September 12, 2026 local time (September 13 UTC). The owner explicitly
authorized adding continuation and raising the **cumulative** Sol API ceiling
from $1 to $1.50. This continued the [earlier incomplete episode](mixed_claim_sol_results.md),
not a new sample. Its original logs and historical report are preserved.

## Result on the same six claims

| Investigator | Correct / 6 | Wrong | Abstained | Scientific credits |
|---|---:|---:|---:|---:|
| Fixed shared-evidence CPU control | 4 | 0 | 2 | 32/32 |
| Luna/high, saved completed episode | 5 | 1 | 0 | 27/32 |
| Sol/high, same episode after explicit continuation | 5 | 1 | 0 | 32/32 |

| Claim | Noise-free reference | Truth | Sol | Luna | CPU |
|---|---:|---|---|---|---|
| C1: target x(4) agreement | 9.4542422702 | REJECT | REJECT | REJECT | REJECT |
| C2: numerical x(0.5) accuracy | 13.1069028276 | ACCEPT | ACCEPT | ACCEPT | ACCEPT |
| C3: cumulative abundance on the stated grid | 159.0036512677 | ACCEPT | ACCEPT | ACCEPT | ACCEPT |
| C4: intervention reduces sampled peak by at least 14% | 11.743554% | REJECT | REJECT | REJECT | ABSTAIN |
| C5: target population-ratio agreement at t=6 | 0.4412051184 | REJECT | REJECT | REJECT | ABSTAIN |
| C6: target prey recovery from t=4 to t=6 is at least 20% | 31.630490% | ACCEPT | REJECT | REJECT | ACCEPT |

Both agents missed **C6**, while the fixed control answered it correctly using
its two direct prey measurements. Equal 5/6 totals do not mean identical
investigations, or demonstrate an advantage in resource allocation. This is
one exploratory system, not a held-out multi-system performance estimate.

Sol's numerical checks for C2/C3/C4 reproduced the accurate purchased values.
For target claims, Sol extrapolated from early observations, one later prey
reading and low-fidelity candidate trajectories. Its final explanation estimated
x(4) near 13, x(6) near 7.5 and recovery near -42%. The reference instead has
positive 31.6% recovery. Sol explicitly described these as reconstruction values,
not direct target measurements. The reconstruction was inaccurate.

For C5, Sol estimated y(6)/x(6) near 0.9, above the reported 0.6892; the actual
ratio is 0.4412, below it. Its REJECT verdict was correct but its estimated
direction of discrepancy was wrong. As with [Luna](mixed_claim_audit_results.md),
five correct verdicts must not be described as five sound numerical audits.
Explanations are retained without semantic judge scoring.

## Resources and continuation

Before the interruption, Sol had purchased two high simulations (baseline and
intervention), x(4.5), and three low simulations: **31 credits**. The resumed
segment made three model responses:

1. `compare_cached_candidates()` — free; existing simulations versus observations.
2. `simulate_low([0.8, 0.08, 0.96])` — 1 credit, `simulation-6`.
3. `submit(...)` — free; all six verdicts supplied.

Complete scientific spending: **4 low x 1 + 2 high x 8 + 1 measurement x 12 = 32**.
No previous purchase was repeated or recharged. All six simulation trajectories
and five observation records, including the four initially available records,
remain accessible in the local archive. No requirement to use every credit was
added: Sol chose to spend the final credit before submitting.

| API accounting | Conservative upper bound |
|---|---:|
| Earlier segment | $0.346635 |
| Resumed segment | $0.454525 |
| Cumulative known usage | **$0.801160** |
| Approved cumulative ceiling | $1.50 |
| Uncertain reservations after completion | $0 |

These are conservative model-usage bounds, not invoices. Sol retained high
reasoning, 32,768 output tokens per response, standard tier, streaming,
store=false, 30 cumulative responses, 60 cumulative tool requests and a
20-minute cumulative active-time limit. Scientific credits and API dollars
remain separate. Luna had its original $1 API ceiling; the models' operational
API allowances are therefore not identical after this explicitly approved
continuation, although scientific resources and task were unchanged.

Cumulative totals: **10 model responses / 10 tool requests**, **102,588 input
tokens**, **14,411 output tokens** including reasoning, and **285.270 seconds**
active runtime. The resumed segment used 223.087 seconds. Generation index 008
was token-counted but never sent in the earlier segment; the continuation
starts at index 009 to preserve immutable filenames. It is not an extra
response or missing paid generation.

## Verification and implementation boundary

- **100 targeted tests passed**: 29 mixed-claim/resume tests, 42 shared API
  safety/logging tests and 29 older point-claim regressions. No live credentials
  or paid calls were used in those tests. The full legacy suite was not rerun.
- Offline fixtures tested full history replay, encrypted reasoning retention,
  duplicate-call protection, cumulative cost and count accounting, original
  file preservation, refused duplicate child launches, legacy-state migration,
  read-only preflight and solver-free restoration. Invalid or ambiguous state
  fails closed; no automatic retry, fresh sample or limit increase occurs.
- The real preflight recovered exactly 31 spent credits, seven prior responses,
  the prior cost ledger, acquired readings and all five earlier trajectories.
- Parent reports/checkpoint/manifest were verified against archived copies in
  the child. Original prompt, tools, study and numerical artifacts matched.
  Offline regeneration reproduced the child's transcript, report and evaluation
  byte-for-byte while preserving raw events.
- Numerical environment, prices, claims, tools and scoring were unchanged.
  Only an operational continuation notice was appended. The new adapter uses
  the existing durable journal, API transport, spending ledger and JSON-based
  scientific restoration. Raw internal model reasoning is not exposed.

Frozen continuation source-manifest SHA-256:
`3e325800b9c85605dd7f3ba8736b4ac9dde4bbfb288be4e1bb3199f53b98c151`.
Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1, OpenAI SDK 2.54.0, HTTPX 0.28.1.
The manifest retains source hashes and the parent provenance. The reviewed
legacy migration permits only the checkpoint/restore adapter change; other
previous shared implementation hashes must match.

## Local artifacts

- [Cumulative Sol transcript](../demos/mixed_claim_audit/runs/20260913T030454Z-live-d69c3dd968/transcript.md)
- [Cumulative generated report](../demos/mixed_claim_audit/runs/20260913T030454Z-live-d69c3dd968/report.md)
- [Complete local event log](../demos/mixed_claim_audit/runs/20260913T030454Z-live-d69c3dd968/events.jsonl)
- [Continuation manifest](../demos/mixed_claim_audit/runs/20260913T030454Z-live-d69c3dd968/manifest.json)
- [Original incomplete transcript](../demos/mixed_claim_audit/runs/20260913T024618Z-live-7c755f7e8c/transcript.md)
- [Luna and classical comparison details](mixed_claim_audit_results.md)
- [Continuation and offline-render commands](../demos/mixed_claim_audit/README.md#explicit-continuation-of-the-same-sol-episode)

All raw logs and credentials remain ignored and local. No proposal documents
were edited, and nothing was pushed.
