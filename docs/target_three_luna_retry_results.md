# Luna: authorized retry of incomplete study 4

On 2026-09-13, the user authorized **one fresh retry** of case `255c174d83fd`.
The retry submitted successfully: **2 correct, 1 wrong, no abstentions**, using
all **32 scientific credits**. The original incomplete attempt is preserved.

## Same task, separate attempt

The retry used the exact original prompt, schemas, study report, target and
reproducible observation noise. Settings remained `gpt-5.6-luna`, **high**
reasoning, **$1 API ceiling**, 30 responses, 32,768 output tokens per response,
60 tool requests and a 20-minute deadline. It began with a fresh conversation
and a new 32-credit ledger, not the original conversation or purchased evidence.
The original failed attempt's credits and API usage were not refunded.

No other Luna study, CPU policy, Sol episode or Terra episode was rerun.
The driver imports and checks the frozen study and CPU snapshot. A separate
exclusive attempt marker prevents accidental additional live retries.

## Retry result

| Claim | Luna verdict | Reference truth | Outcome |
|---|---|---|---|
| All reported parameters within 5% | REJECT | REJECT: largest relative error 33.33% | Correct |
| Recovery x(8)/x(6)-1 >=0.05 | REJECT | REJECT: reference -0.0749480 | Correct |
| Target trapezoidal prey integral >=142 | ACCEPT | REJECT: reference 138.94835 | Wrong |

Luna bought **x(6) and x(8)** for 24 credits and **eight low-fidelity
trajectories** for 8 credits. It bought no high-fidelity trajectory. Its initial
request for the report's original Euler calculation was free reuse.

For the incorrect integral verdict, Luna relied on its best-matching purchased
Euler trajectory, whose integral was about **147.25**, above 142. The target
reference integral is about **138.95**, below 142. This is a recorded numerical
inference error, not a runner failure; the explanation receives no extra score.

There were **14 model responses**, **162,618 input tokens** and **13,159 output
tokens**, including reasoning, over **147.5 seconds**. All usage settled.
The API cost upper bound was **$0.05644530**; the standard-price lower estimate
was **$0.02383098**. These are usage estimates, not invoices, and remain below
the original $1 cap. No limit was increased and no further retry was attempted.

## Original versus retry-inclusive views

| Luna view | Correct | Wrong | Abstain | Unsubmitted claims | Completion |
|---|---:|---:|---:|---:|---|
| Original six first attempts | 8 | 5 | 2 | 3 | 5/6 episodes |
| Five original completed episodes plus this retry | 10 | 6 | 2 | 0 | Six studies have submissions |
| All seven attempts, including original failure | 10 | 6 | 2 | 3 | 6/7 attempts |

The retry-inclusive six-study view is **10/18 correct**, with utility -2 under
+1 correct / -2 wrong / 0 abstain. It is not a revised first-attempt completion
rate. Obtaining the six submitted studies took **seven live attempts**, spending
**224 scientific credits** and an API upper bound of **$0.30913955** in total.
The selected six submitted episodes used 192 credits, but that does not erase
the additional failed attempt's expenditure.

For reference, the unchanged [Sol/Terra/CPU comparison](target_three_models_results.md)
has Terra 16/18 correct, Sol 14/18 and CPU 12/18. Luna's retry-inclusive 10/18
must be labelled as allowing an additional attempt. These are six reused
development worlds, not a general model ranking or a matched retry-policy study.

## Verification and local records

The scripted offline rehearsal verified exact settings, empty initial purchase
history, identical prompt, offline regeneration and duplicate-live protection.
Post-run checks verified preserved original artifacts, exact retry inputs,
complete usage, untorn chronological logs, score totals and byte-identical
report/transcript regeneration. The shared science and API runner were unchanged.

- [Complete readable retry transcript](../demos/paired_claim_audit/runs/20260913T105527Z-target-three-luna-case4-retry-live-90354c03ce/episodes/20260913T105527Z-live-805dc3fe67/transcript.md)
- [Retry episode evaluation](../demos/paired_claim_audit/runs/20260913T105527Z-target-three-luna-case4-retry-live-90354c03ce/episodes/20260913T105527Z-live-805dc3fe67/report.md)
- [Retry result and original case mapping](../demos/paired_claim_audit/runs/20260913T105527Z-target-three-luna-case4-retry-live-90354c03ce/retry_result.json)
- [Retry manifest and original-attempt link](../demos/paired_claim_audit/runs/20260913T105527Z-target-three-luna-case4-retry-live-90354c03ce/manifest.json)
- [Labelled retry-inclusive six-study view](../demos/paired_claim_audit/runs/20260913T105527Z-target-three-luna-case4-retry-live-90354c03ce/retry_inclusive_six_case_view.json)
- [Unchanged original Luna result report](target_three_claims_results.md)
- [Single-case driver](../demos/paired_claim_audit/retry_luna_case.py)

All detailed records remain in the ignored run directory
`demos/paired_claim_audit/runs/20260913T105527Z-target-three-luna-case4-retry-live-90354c03ce`.
The manifest records original hashes, driver hash, source provenance and software
versions. The driver supports `--dry-run`; its authorized `--live` attempt has
already been consumed. Do not remove the marker to repeat it. Existing
`target_three_claims render-episode <episode-directory>` regenerates the
readable episode records offline, without API or solver calls.
