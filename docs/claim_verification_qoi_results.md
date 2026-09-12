# Claim-specific verification: CPU pilot results

Completed 2026-09-12. This revision adds peak height, peak time, and cumulative
prey population claims, configurable Euler/RK2 checks, and work-based prices.
The predator-prey system and earlier experiments are preserved. See the
[complete protocol](claim_verification_qoi_protocol.md).

## Outcome

The revised task has objective labels and more claim-specific variation, but
**remains easy for a fixed RK2 check**. It does not demonstrate an adaptive
auditing advantage. No LLM/API calls were made; API expenditure was zero.

| Policy | Development (54 claims) | Fresh (108 claims) | Fresh accuracy | False accept / reject | Mean fresh credits |
|---|---:|---:|---:|---:|---:|
| Fixed RK2, dt=.04 / output=.04 | 53/54 | 106/108 | 98.15% | 2 / 0 | 6.010 |
| Fixed RK2, dt=.08 / output=.02 | 54/54 | 106/108 | 98.15% | 2 / 0 | 6.010 |
| Fixed Euler, dt=.02 / output=.04 | 48/54 | 99/108 | 91.67% | 6 / 3 | 6.010 |
| Randomized checks | 51/54 | 105/108 | 97.22% | 2 / 1 | 7.840 |
| Adaptive discrepancy/cost heuristic | 49/54 | 96/108 | 88.89% | 6 / 6 | 7.861 |

All **810 episodes completed**, with full coverage, no abstentions, no duplicate
slots, no unknown accounting, and no budget overrun. Maximum expenditure was
8 credits. Fifty purchased numerical checks failed across the episodes; their
performed work was charged and their failures retained. No failed episode was
replaced or excluded. A failed numerical check is not an incomplete episode.

### Fresh claims by quantity

| Policy | Peak height | Peak time | Cumulative population |
|---|---:|---:|---:|
| Fixed RK2, dt=.04 / output=.04 | 36/36 | 34/36 | 36/36 |
| Fixed RK2, dt=.08 / output=.02 | 36/36 | 34/36 | 36/36 |
| Fixed Euler | 31/36 | 34/36 | 34/36 |
| Randomized | 36/36 | 34/36 | 35/36 |
| Adaptive | 35/36 | 26/36 | 35/36 |

The fresh catalog contains 61 valid and 47 invalid claims. Their valid/invalid
counts are 22/14 for height, 9/27 for time, and 30/6 for the integral. These were
not balanced by label selection. Both tolerances are included in each row;
the full saved report also separates them.

## What the pilot establishes—and does not

All 27 fixed original numerical studies were generated: nine systems times
three profiles, yielding six claims each. There were no original-pipeline
failures or timing exclusions. Each of the three report formats contains
54 claims. The 162 claims share only nine physical systems; the 108 fresh
claims share six. They are not 108 independent scientific systems.

**Claim dependence is real:** 17 of the 18 fresh original studies have both
valid and invalid claims among their six quantity/tolerance variants. For
example, the first profile on seed 7400 has 7.724% peak-height error and 0.333
time-unit peak-location error, but only 0.00447% integral error. Its height and
timing claims are invalid at both stated tolerances; its integral claims are
valid. Labeling the whole pipeline simply "bad" would be wrong.

**The remaining fixed-RK2 errors are narrow boundary cases.** For seed 7402,
the reported peak time is 4.6, the reference is 4.43138809, and tolerance is
0.16. The check returns 4.44 and incorrectly accepts a difference of 0.16;
the actual error is 0.16861191. For seed 7403, the reported value is 2.8 with
tolerance 0.04, versus reference 2.75371831. The check returns 2.76 and again
accepts at the boundary, although the actual error is 0.04628169. The numeric
boundary handling is intentional and inclusive; these are approximation errors,
not floating-point scoring accidents.

**The adaptive baseline is not a strong verifier.** It sometimes spends money
on probes and then makes a poor resolution-based estimate selection. In one
seed-7400 1%-height claim, the report says 25.5755973 and the reference is
25.13919082. The heuristic chooses a purchased estimate of 25.61214702 and
accepts, despite another purchased estimate of 25.31705200. This exposes a
limitation of the shared unvalidated ranking rule, not evidence that adaptive
auditing intrinsically performs worse. No policy was retuned after evaluation.

These results do not establish reliable confidence, explanation correctness,
general scientific verification, or difficulty for LLMs. The two fixed RK2
checks each solve almost everything with 1.99 credits left. Merely adding
quantities has not removed that shortcut. This retained finding should guide
the next design discussion rather than justify another paid model batch yet.

## Numerical and software verification

The largest disagreements over all nine systems were:

| Independent-reference check | Observed maximum | Required bound |
|---|---:|---:|
| Peak height, relative | 8.731e-12 | 1e-7 |
| Peak time, absolute | 3.561e-11 | 1e-6 |
| Cumulative population, relative | 1.503e-12 | 1e-7 |

All systems had one or two interior prey maxima and a well-separated global
maximum. This is finite-horizon transient behavior, not a demonstration of
arbitrary oscillatory regimes. The reference combines DOP853/Radau agreement,
two root-search grids, and augmented-integral/dense-quadrature agreement.

**507 tests pass:** 493 repository tests, including 90 new revision tests, plus
14 preserved planning-pilot tests. Tests cover solver convergence, actual-work
charges and failures, independent references, matched claims, reference privacy,
duplicate calls, independently contributed estimates, interrupted logs, deadline
scoring, null-aware accounting, and solver-free report regeneration.

Python 3.13.5; NumPy 2.3.4; SciPy 1.16.1. The manifest was frozen before case
generation; all source hashes still matched at completion. Reported per-episode
runtime is saved but is not a fair cold-solver speed comparison: backend cache
reuse and execution order affect wall time. Scientific charges remain independent.

## Saved artifacts and reproduction

Run: `20260912T043026Z-qoi-cpu-e6c9d30dd9`.

- [Full per-claim results](../demos/claim_verification/runs/20260912T043026Z-qoi-cpu-e6c9d30dd9/report.md)
- [Frozen manifest and source hashes](../demos/claim_verification/runs/20260912T043026Z-qoi-cpu-e6c9d30dd9/manifest.json)
- [Aggregate JSON](../demos/claim_verification/runs/20260912T043026Z-qoi-cpu-e6c9d30dd9/summary.json)
- [Private case catalog and numerical checks](../demos/claim_verification/runs/20260912T043026Z-qoi-cpu-e6c9d30dd9/catalog.json)
- [Peak-time boundary error transcript](../demos/claim_verification/runs/20260912T043026Z-qoi-cpu-e6c9d30dd9/episodes/20260912T043145Z-fixed_rk2-179e628090/transcript.md)
- [Adaptive estimate-selection error transcript](../demos/claim_verification/runs/20260912T043026Z-qoi-cpu-e6c9d30dd9/episodes/20260912T043113Z-adaptive-cc79fd26e0/transcript.md)

Raw artifacts remain local and ignored. The full report links every transcript;
episode JSONL retains complete purchased numerical runs and all public tool
requests/responses. No credentials or raw runs are included in the checkpoint.

```powershell
.\.venv\Scripts\python.exe -B -m budgeted_science.claim_verification_qoi run
.\.venv\Scripts\python.exe -B -m budgeted_science.claim_verification_qoi render demos\claim_verification\runs\20260912T043026Z-qoi-cpu-e6c9d30dd9
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -B -m unittest discover -s demos\planning\tests -q
```

As-run core source SHA-256 (retained in the immutable manifest):

```text
numerics.py    1866bd1bfe783cc4d5737e362df1a6ad4803a4d377bdebc38da239b83ab755c0
policies.py    e8173dd792d065ac1269e2799c4bc62625e8a026c64f4703504f1f89c796eda1
environment.py e9a19d012317fc9a1da8c6e9e67cea2983f7d50325e77e9c89510014f7075e03
pilot.py       85081cd47dd46be8a6d6c959378657eb132548e16176dd12094bb69a4a7fc490
```

After the frozen evaluation, a report-only fix normalized relative run paths
before linking absolute episode paths; a regression test covers it. No solver,
policy, study, scoring, or recorded result changed. `pilot.py` in the delivered
checkpoint therefore differs from its as-run hash above. Offline regeneration
was checked against the saved summaries and full report.
