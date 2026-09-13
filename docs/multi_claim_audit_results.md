# Predator-prey multi-claim audit: CPU and Luna results

Executed September 12, 2026 (September 13 UTC). One exploratory system, one
six-claim report, one fixed CPU episode, and **one live Luna/high episode**.
Both investigators had independent 32-credit ledgers and identical evidence.
See the [frozen protocol](multi_claim_audit_protocol.md).

## Main result

| Investigator | Correct / 6 | Wrong | Abstained | Coverage | Credits | Paid actions |
|---|---:|---:|---:|---:|---:|---:|
| Fixed recompute-and-measure control | 6 | 0 | 0 | 100% | 32 | 3 |
| GPT-5.6 Luna, high reasoning | 6 | 0 | 0 | 100% | 32 | 3 |

Both independently used the same acquisition sequence:

1. High-fidelity simulation at the report parameters `(1.0,0.08,1.4)`: 8 credits.
   Its trajectory supports the four numerical-accuracy checks.
2. Noisy target x(4): 12 credits.
3. Noisy target y(6): 12 credits.
4. Submit all six verdicts: free.

Luna had the low-fidelity service and other candidate parameters/measurement
locations available but did not purchase them. There was no requirement to
spend the full budget and no savings reward. The CPU workflow was not revealed
to Luna. Both used the same reproducible target readings: x(4)=9.35146041,
y(6)=5.41129820, with noise standard deviations 0.1 and 0.05 respectively.

## Claim-level outcomes

Every claim asserts relative error at most 5%. Values below are displayed at
reduced precision; scoring uses the ten-significant-digit printed report values
and full private numerical references.

| Claim | Referent | Reported | Reference | Actual relative error | CPU | Luna |
|---|---|---:|---:|---:|---|---|
| C1: x(0.5) | Model at report parameters | 12.99098574 | 13.10690283 | 0.8844% | ACCEPT | ACCEPT |
| C2: y(0.5) | Model at report parameters | 3.667241103 | 3.749687864 | 2.1988% | ACCEPT | ACCEPT |
| C3: x(6) | Model at report parameters | 10.64298425 | 12.71680405 | 16.3077% | REJECT | REJECT |
| C4: y(6) | Model at report parameters | 7.335429119 | 8.036795007 | 8.7269% | REJECT | REJECT |
| C5: x(4) | Fixed target | 21.13462896 | 9.454242270 | 123.5465% | REJECT | REJECT |
| C6: y(6) | Fixed target | 7.335429119 | 5.490650099 | 33.5986% | REJECT | REJECT |

Thus the study contains two supported and four unsupported claims. An
always-reject rule would score 4/6 on this report; always-accept would score 2/6.
These are transparent label-frequency controls, not additional live episodes.

The same printed y(6) appears in C4 and C6, but the accuracy referent differs.
Numerical accuracy at the report parameters and target prediction accuracy
were evaluated separately. Target labels do not use the noisy measurements.

## Runtime, API and records

- Luna: 4 model responses, 4 function requests (3 paid purchases plus submit),
  20.137 seconds to completion. No refusal, truncation, retry or missing usage.
- CPU control: 0.206 seconds including local episode setup and durable logging;
  zero API calls or expenditure. Actual CPU time is not the scientific tariff.
- Luna's conservative model-cost upper bound: **$0.00517730**, below its $1 cap.
  All reservations settled; no uncertain usage remains. This is accounting,
  not an invoice. Reasoning tokens are included in output usage.
- The entire source manifest, dependency versions, frozen prompt and schemas,
  all requests/responses/stream events, returned reasoning summaries, numerical
  trajectories, tool results and private scoring are stored locally.

Local artifacts (ignored, not included in Git):

- [Complete Luna transcript](../demos/multi_claim_audit/runs/20260913T012059Z-live-e173e9aa7b/transcript.md)
- [Generated comparison report](../demos/multi_claim_audit/runs/20260913T012059Z-live-e173e9aa7b/report.md)
- [Authoritative episode events](../demos/multi_claim_audit/runs/20260913T012059Z-live-e173e9aa7b/events.jsonl)
- [CPU acquisition trace](../demos/multi_claim_audit/runs/20260913T011332Z-multi-claim-prepared-299ed54a02/cpu/20260913T011332Z-fixed-cpu-78d52a9a23/transcript.md)
- [Frozen preparation](../demos/multi_claim_audit/runs/20260913T011332Z-multi-claim-prepared-299ed54a02/manifest.json)
- [Final offline rehearsal](../demos/multi_claim_audit/runs/20260913T011404Z-dry-run-02140cedf8/report.md)

An earlier CPU-only preparation and rehearsal were retained after the CPU
transcript presentation was clarified. Neither made a real API call. Test
fixtures sometimes exercise the live launch guard with an injected fake
transport; these are not additional model evaluations.

## Numerical and software verification

| Check | Model reference | Target reference |
|---|---:|---:|
| Maximum DOP853/Radau absolute disagreement | 6.229e-10 | 9.060e-11 |
| Maximum paid-high-service/reference disagreement | 6.541e-9 | 8.819e-10 |

All **801 shared tests plus 14 planning-pilot tests passed**. This includes
18 new tests covering literal report construction, independent numerical
checks, identical target/noise, prices, caching, independent ledgers, failure
charging, invalid requests, duplicate-call protection, private-data isolation,
no unpaid solves in free comparison, correct/incorrect/abstained scoring,
complete logging, offline regeneration, frozen limits, and no second launch.

Dependencies: Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1, OpenAI SDK 2.54.0,
HTTPX 0.28.1, budgeted-science 0.1.0.

Frozen source-manifest SHA-256:
`41ced250813dfa148603ac3ed0e9ea4faf97225d5743fa538fa0f16b538bac58`.
Per-file hashes are available in the manifests. The original planning code,
prior verification experiments, saved results and proposal documents were
not changed.

## Reproduction and interpretation

The [demo README](../demos/multi_claim_audit/README.md) gives prepare/dry-run/live
commands. Running `prepare` reproduces the CPU study and comparison. Running
`render` on the saved episode regenerates its report without tools or API calls:

```powershell
.\.venv\Scripts\python.exe -m budgeted_science.agents.multi_claim_audit render demos/multi_claim_audit/runs/20260913T012059Z-live-e173e9aa7b
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_multi_claim_audit.py -v
```

The demonstration now runs end to end: multiple claims, shared evidence,
different resource types, matched accounting, and objective verdict scoring.
It does **not** show an advantage from adaptive allocation; both investigators
use the same straightforward route. There is no claim of difficulty or
general superiority. These six correlated claims share one exploratory system.
Explanations are preserved, not scientifically certified or semantically
scored. Target checks use simulated data, not a physical validation experiment.
