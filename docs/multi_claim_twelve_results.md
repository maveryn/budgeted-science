# Multi-claim audit at 12 credits: Luna, Sol, and fixed control

Executed September 12, 2026 (September 13 UTC). Exactly one live episode per
model, Luna first and Sol second, both with high reasoning. This follow-up
changes only the scientific allowance from the [20-credit comparison](multi_claim_twenty_results.md).
The six claims, original study, target, reproducible noisy observations,
prices, tools, and scoring are unchanged. Both models received identical
frozen scientific prompts and schemas. No retries, model substitutions,
budget increases, or changes between live episodes were made.

## Results

| Investigator | Correct / 6 | Wrong | Abstained | Credits spent / available | Paid resources |
|---|---:|---:|---:|---:|---|
| Fixed control | 4 | 0 | 2 | 8 / 12 | 1 high simulation |
| GPT-5.6 Luna / high | 6 | 0 | 0 | 12 / 12 | 1 high + 4 low simulations |
| GPT-5.6 Sol / high | 6 | 0 | 0 | 12 / 12 | 1 high + 4 low simulations |

| Claim | Truth | Fixed control | Luna | Sol |
|---|---|---|---|---|
| C1: numerical x(0.5) accuracy | ACCEPT | ACCEPT | ACCEPT | ACCEPT |
| C2: numerical y(0.5) accuracy | ACCEPT | ACCEPT | ACCEPT | ACCEPT |
| C3: numerical x(6) accuracy | REJECT | REJECT | REJECT | REJECT |
| C4: numerical y(6) accuracy | REJECT | REJECT | REJECT | REJECT |
| C5: target x(4) agreement | REJECT | ABSTAIN | REJECT | REJECT |
| C6: target y(6) agreement | REJECT | ABSTAIN | REJECT | REJECT |

All three methods completed. Abstention is separate from a wrong verdict,
but does not count as a correct binary verdict. There is no full-budget
requirement, spending penalty, savings reward, or confidence score.

## Resource use

The unchanged prices are 1 credit per low-fidelity trajectory, 8 per
high-fidelity trajectory, and 12 per new target scalar measurement. Both
populations at all 16 output times are included in each simulation purchase.
Already purchased data, the supplied original low trajectory, free noisy
time-1 observations, and cached-candidate comparisons remain free.

**Fixed control:** purchased the high trajectory at report parameters
(1, 0.08, 1.4), which supports all four numerical claims. Its following
requests for target x(4) and y(6) were unaffordable and not executed or
charged. It abstained on both target claims with four credits unused. Its
fixed policy has no cheap-fitting fallback; this is the same simple control,
not an optimized 12-credit baseline. Independent preparations produced
identical CPU verdicts and charges; these duplicate checks are not additional
scientific samples.

**Both models:** purchased that same high trajectory, four low trajectories
at candidate target parameters, and a free cached-candidate comparison.
Neither purchased new target evidence. Each made seven tool requests,
including comparison and submission. Their low-parameter sequences were:

| Purchase | Luna (theta1, theta2, theta3) | Sol (theta1, theta2, theta3) |
|---|---|---|
| Low 1 | (0.90, 0.080, 1.10) | (0.80, 0.080, 1.05) |
| Low 2 | (0.90, 0.080, 0.90) | (0.90, 0.080, 0.92) |
| Low 3 | (0.92, 0.080, 0.95) | (0.90, 0.080, 0.95) |
| Low 4 | (0.90, 0.080, 0.95) | (0.84, 0.068, 0.80) |

The agents used agreement with the two free early observations to select
candidate trajectories and extrapolate to the two later target claims.
This was their chosen procedure, not an imposed fitting or acquisition plan.

## Important qualification: correct rejection, wrong error direction

Both agents justified rejecting C6 by predicting target y(6) **above** the
reported 7.335429119. Luna cited candidate values about 9.57-9.75; Sol cited
about 9.75-13.57. The independently checked target y(6) is actually
**5.49065010**, below the reported value and below the 5% acceptance region.

Their C6 verdicts are therefore correct, but the stated direction of the
discrepancy is wrong. Matching two early noisy observations with a few cheap
trajectories did not establish the true later response. This concrete
numerical contradiction is recorded separately; it does not retroactively
change the predeclared verdict score or introduce an LLM judge. Explanations
otherwise remain ungraded.

Consequently, these results do **not** demonstrate six scientifically
justified audits or a reliable verification advantage over abstention.
Reducing the allowance to 12 did not reduce binary verdict accuracy on this
instance. Sol's score rose from five correct plus an abstention at 20 to six
correct at 12, with a different strategy; one episode at each budget is not
evidence that reducing resources improves performance. See the previous
report for the similar caveat to Luna's 20-credit C6 explanation.

## API accounting and runtime

| Model | Responses | Input tokens across requests | Output tokens incl. reasoning | Seconds | Conservative API upper bound |
|---|---:|---:|---:|---:|---:|
| Luna | 7 | 47,528 | 3,658 | 58.877 | $0.01627160 |
| Sol | 7 | 46,485 | 5,091 | 105.087 | $0.33424500 |

Each episode retained its own $1 API ceiling, 30-response limit, 32,768
output tokens per response, 60-tool-request limit, and 20-minute deadline.
Both ended with a valid submission and no unsettled usage. Scientific
credits and API dollars are separate ledgers; token totals include repeated
context, and these conservative bounds are not invoices.

High reasoning support and standard prices were checked against the
[Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna),
[Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol), and
[pricing](https://developers.openai.com/api/docs/pricing) documentation.
Reservations remain up to $0.25/$1.20 per million Luna input/output tokens
and $5/$20 for Sol, covering cache-write rates and reasoning output.

## Verification and reproduction

**85 targeted tests passed:** 29 multi-claim tests, 42 reused API-runner
tests, and 14 planning-pilot tests. New checks cover exact 12-credit
enforcement, unchanged noisy observations, high-plus-four-low and single
measurement allocations, free reuse, the unchanged fixed control,
matched frozen prompts, and offline fake-model rehearsals. Earlier 20/32
tests remain passing. The entire slower legacy suite was not rerun for
this small configuration extension.

Both saved live prompts/schemas match preparation; all seven generation
requests per model specify the requested model, high reasoning, sequential
tools, 32,768 output tokens, and store=false. Both chronological event logs
are complete. Offline regeneration reproduced transcripts, reports, and
evaluations byte for byte without changing raw events or running tools/API
calls. Credentials and raw logs remain untracked.

See [demo commands](../demos/multi_claim_audit/README.md#matched-12-credit-follow-up).
Select model and budget during preparation; neither can be overridden at
launch. Default commands still select the original Luna/32 configuration.
Earlier results and proposal documents are preserved.

Frozen source-manifest SHA-256:
`02e45833776db6a7f41bae499be7e1d6c666ee0c30f459fb5fc098b887ae6617`.
Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1, OpenAI SDK 2.54.0, HTTPX 0.28.1,
budgeted-science 0.1.0. Full hashes and configuration are saved in manifests.

- [Luna transcript](../demos/multi_claim_audit/runs/20260913T015802Z-live-34246c5731/transcript.md)
- [Luna generated report](../demos/multi_claim_audit/runs/20260913T015802Z-live-34246c5731/report.md)
- [Luna preparation](../demos/multi_claim_audit/runs/20260913T015707Z-multi-claim-prepared-0fefb35cdd/manifest.json)
- [Luna paired CPU trace](../demos/multi_claim_audit/runs/20260913T015707Z-multi-claim-prepared-0fefb35cdd/cpu/20260913T015707Z-fixed-cpu-da1095845b/transcript.md)
- [Sol transcript](../demos/multi_claim_audit/runs/20260913T015923Z-live-6a0aad6d83/transcript.md)
- [Sol generated report](../demos/multi_claim_audit/runs/20260913T015923Z-live-6a0aad6d83/report.md)
- [Sol preparation](../demos/multi_claim_audit/runs/20260913T015712Z-multi-claim-prepared-fbc4cce533/manifest.json)
- [Sol paired CPU trace](../demos/multi_claim_audit/runs/20260913T015712Z-multi-claim-prepared-fbc4cce533/cpu/20260913T015712Z-fixed-cpu-5428e3b91a/transcript.md)

These are six related claims on one exploratory system, not six independent
systems. The target is synthetic and shares the high-fidelity model family;
this is not a physical validation experiment or a general model ranking.
