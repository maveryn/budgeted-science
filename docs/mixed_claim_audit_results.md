# Mixed-claim audit: Luna/high and classical baseline at 32 credits

Executed September 12, 2026 (September 13 UTC). One new six-claim development
study and exactly one live Luna/high episode. Both investigators had **32
scientific credits** and the planning toy's unchanged **1/8/12-credit prices**.
The [frozen protocol](mixed_claim_audit_protocol.md) specifies the shuffled
claims, numerical definitions, target, observations and scoring. All earlier
point-claim studies and proposal documents are preserved.

## Main matched comparison

| Investigator | Correct / 6 | Wrong | Abstained | Credits spent / cap | Purchases |
|---|---:|---:|---:|---:|---|
| Fixed shared-evidence CPU baseline | 4 | 0 | 2 | 32 / 32 | 1 high simulation + 2 target measurements |
| GPT-5.6 Luna / high | 5 | 1 | 0 | 27 / 32 | 3 high + 3 low simulations; no new measurements |

Both episodes completed. The baseline's abstentions are not incorrect
assertions, but they do not earn correct-verdict credit. Luna made one false
rejection. There is no savings reward, full-budget requirement or confidence
score. This is not evidence that Luna is generally superior or more reliable.

## Six claims and outcomes

The shuffle was fixed before the live run. IDs here match the actual report
and tools; they do not match the earlier point-claim study's IDs.

| ID | Assertion | Accurate reference | Truth | CPU | Luna |
|---|---|---:|---|---|---|
| C1 | Reported x(4)=21.13462896 predicts the target within 5% | 9.45424227 | REJECT | REJECT | REJECT |
| C2 | Baseline x(0.5)=12.99098574 is numerically accurate within 5% | 13.10690283 | ACCEPT | ACCEPT | ACCEPT |
| C3 | Cumulative prey index 157.1865625 is numerically accurate within 5% | 159.00365127 | ACCEPT | ACCEPT | ACCEPT |
| C4 | +10% predation reduces grid peak prey by at least 14% | 11.743554% reduction | REJECT | ABSTAIN | REJECT |
| C5 | Reported predator/prey ratio 0.6892267192 matches the target at t=6 within 10% | 0.44120512 | REJECT | ABSTAIN | REJECT |
| C6 | Target prey recovers by at least 20% from t=4 to t=6 | 31.630490% recovery | ACCEPT | ACCEPT | REJECT |

C3 uses trapezoidal integration on the existing half-unit grid including
the initial state, not the exact continuous-time integral. C4 uses maxima
on that same grid, not continuous-time peaks. Its 14% claim rounds the actual
Euler-estimated reduction (about 14.6%) down to a whole percentage point;
the accurate reduction is about 11.7%. Labels come from independently checked
numerical references, not report wording, defect names, or an LLM judge.

The target is the same synthetic system used in the earlier planning/audit
demo, with the same deterministic noisy observation stream. Target labels
use noise-free values. This does not establish validation against reality.

## Resource allocation and evidence reuse

**Classical baseline:** fixed acquisition, independent of observed values and
claim presentation order. It bought the high baseline trajectory (8), target
x(4) (12), and target x(6) (12). It reused the trajectory for C2/C3, x(4) for
C1/C6, and x(6) for C6. It lacked the intervention trajectory for C4 and target
y(6) for C5, so it abstained on those. Its later requests for those resources
were unaffordable and caused no execution or charge. This is a simple
structured-claim, plug-in numerical control, not an optimized allocation
method or general free-text verifier.

**Luna:** used the following paid sequence, without a prescribed plan:

| Purchase | Parameters | Cost | Remaining |
|---|---|---:|---:|
| High baseline | (1, 0.08, 1.4) | 8 | 24 |
| High intervention | (1, 0.088, 1.4) | 8 | 16 |
| Low candidate | (0.9, 0.06, 1.1) | 1 | 15 |
| Low candidate | (0.9, 0.08, 1.0) | 1 | 14 |
| High candidate | (0.9, 0.08, 1.0) | 8 | 6 |
| Low candidate | (0.92, 0.08, 0.95) | 1 | 5 |

It then used free cached comparisons and evidence retrieval. It purchased no
target measurement, instead extrapolating from candidates compared with the
two free noisy time-1 observations. It submitted with five credits remaining;
spending less is permitted and does not receive a score bonus. Five credits
could buy low solves but not a new high solve or target measurement.

The first submission cited an invalid evidence ID, `comparison_cached_candidates`.
The runner rejected it without charge or ending the episode. Luna corrected
the citations on the next response, keeping identical verdicts. This was
ordinary recoverable tool feedback within the same episode, not an automatic
retry, a second sample or a changed scientific result.

## Scientific error and qualification to the five correct verdicts

Luna's numerical checks were accurate: baseline point error about 0.88%,
cumulative-index error about 1.14%, and intervention peak reduction about
11.74%. It correctly accepted C2/C3 and rejected C4.

For the target, its selected low candidate predicted x(4)=13.88204 and
x(6)=7.47967, implying approximately **46.1% decline**. Luna consequently
rejected C6's assertion of at least 20% recovery. The actual target values
are x(4)=9.45424227 and x(6)=12.44466546: **31.6% recovery**. This is a real
prediction/verdict error, not a runner failure. A candidate agreeing fairly
closely with the early observations did not reproduce the later trajectory.

For C5, Luna predicted a ratio around **1.280**, above the report's 0.68923.
The true ratio is **0.44121**, below the report. Its REJECT label is correct,
but its stated discrepancy direction is wrong, as in earlier point-claim
experiments. C1's rejection has the correct direction, but Luna's candidate
value is still not an accurate reconstruction of the target.

These concrete numerical inconsistencies are documented separately; the
predeclared score is not changed retrospectively. Five correct labels do not
mean five independently justified verifications. The new recovery claim
exposes the extrapolation error as an incorrect verdict, rather than only
an explanation problem. One case cannot establish a general difficulty or
performance ranking.

## CPU complete-evidence diagnostic (different budget)

The same fixed policy at **52 credits** additionally bought the intervention
high trajectory and target y(6), obtaining **6/6 correct, no errors or
abstentions**. This is a commissioning diagnostic, **not** a matched baseline
in the 32-credit comparison. Its success shows these direct checks work for
this particular study and noise realization; noisy readings do not generally
certify labels. There was no 52-credit model run.

## Runtime, logging and verification

- Luna: **10 model responses / 10 tool requests**, 83.572 seconds.
- Aggregate API input: **95,948 tokens**; output including reasoning: **7,022**.
- Conservative API cost upper bound: **$0.03241340**, within the unchanged
  **$1 ceiling**. No unsettled usage, retries, model substitutions or cap raises.
- Matched CPU baseline runtime: 0.139 seconds (local timing, not scientific cost).
- **104 targeted tests passed:** 19 new mixed-claim tests, 29 original audit
  tests, 42 reused API safety/logging tests and 14 planning-pilot tests.
  The entire slower legacy suite was not rerun; existing implementations were
  reused without modification.

The numerical tests check actual report generation, reference agreement,
hand-computed aggregates/ratios, operator boundaries, observation matching,
independent ledgers, failed/duplicate purchases, zero-budget retrieval,
presentation-order-independent baseline behavior, private-state exclusion,
malformed submissions, no unpaid solver calls, frozen settings and offline
rehearsals. Both 32- and 52-credit CPU outcomes were checked before the model.

Saved live prompts and schemas exactly match preparation. All ten generation
requests specify gpt-5.6-luna, high reasoning, store=false, sequential tools
and 32,768 output tokens. The chronological log is complete. Offline rendering
reproduced report, transcript and evaluation byte-for-byte and preserved raw
events without running solvers or making API calls.

Frozen source-manifest SHA-256:
`236a22e35ecf24eaaa5ef25f7531dba6dbece87c34802ebd159dda730931b3bb`.
Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1, OpenAI SDK 2.54.0, HTTPX 0.28.1,
budgeted-science 0.1.0. Full per-file hashes and software versions are in the
saved manifests. [Reproduction commands](../demos/mixed_claim_audit/README.md).

Local artifacts (ignored by Git):

- [Luna transcript](../demos/mixed_claim_audit/runs/20260913T023328Z-live-7ba21f148c/transcript.md)
- [Luna generated comparison report](../demos/mixed_claim_audit/runs/20260913T023328Z-live-7ba21f148c/report.md)
- [Luna complete chronological log](../demos/mixed_claim_audit/runs/20260913T023328Z-live-7ba21f148c/events.jsonl)
- [Frozen preparation](../demos/mixed_claim_audit/runs/20260913T023121Z-mixed-prepared-4df55c3128/manifest.json)
- [Matched classical transcript](../demos/mixed_claim_audit/runs/20260913T023121Z-mixed-prepared-4df55c3128/cpu/20260913T023121Z-fixed-cpu-0f4c4b117c/transcript.md)
- [CPU validation and 52-credit diagnostic](../demos/mixed_claim_audit/runs/20260913T022753Z-mixed-validation-24bb5629bf/results.json)

This remains six correlated claims from one exploratory system. The claims
are more heterogeneous than the previous point-only packet, but several
share a trajectory or observation by design. There is no claim that optimal
allocation, reliable confidence, or broad scientific verification is solved.
