# Multi-claim audit at 20 credits: Luna, Sol, and fixed control

Executed September 12, 2026 (September 13 UTC). Exactly one new live episode
per model, Luna first and Sol second. Both used high reasoning, the same six
claims, target and noise stream as the [32-credit demonstration](multi_claim_audit_results.md).
The scientific allowance was reduced to 20; resource prices remained 1/8/12.
Prompts and tool schemas were identical across the two models. No cases or
claims were replaced, and no outcome was used to retune the subsequent run.

## Results

| Investigator | Correct / 6 | Wrong | Abstained | Credits | Paid resources |
|---|---:|---:|---:|---:|---|
| Fixed control | 5 | 0 | 1 | 20 | 1 high simulation + 1 target measurement |
| GPT-5.6 Luna / high | 6 | 0 | 0 | 18 | 1 high + 10 low simulations; no new measurement |
| GPT-5.6 Sol / high | 5 | 0 | 1 | 20 | 1 high simulation + 1 target measurement |

| Claim | Truth | Fixed control | Luna | Sol |
|---|---|---|---|---|
| C1: numerical x(0.5) accuracy | ACCEPT | ACCEPT | ACCEPT | ACCEPT |
| C2: numerical y(0.5) accuracy | ACCEPT | ACCEPT | ACCEPT | ACCEPT |
| C3: numerical x(6) accuracy | REJECT | REJECT | REJECT | REJECT |
| C4: numerical y(6) accuracy | REJECT | REJECT | REJECT | REJECT |
| C5: target x(4) agreement | REJECT | REJECT | REJECT | REJECT |
| C6: target y(6) agreement | REJECT | ABSTAIN | REJECT | ABSTAIN |

All three runs completed. Abstention is not counted as a correct binary
verdict, but is reported separately from an incorrect verdict. There is no
savings reward, spending penalty, confidence score, or full-budget requirement.

## What they did

**Fixed control:** preserved its previous order. A high-fidelity trajectory at
the report parameters costs 8 credits and informs C1-C4. Target x(4) costs 12
and informs C5. Its subsequent y(6) request is unaffordable, so no calculation
or charge occurs; it abstains on C6. The preparation for each model independently
re-executes this CPU control, with identical results. They are duplicate checks
of one deterministic control, not independent scientific samples.

**Luna:** bought the report-parameter high trajectory, then ten distinct low
trajectories at candidate target parameters. It used the free noisy x(1),y(1)
observations and the free cached-candidate comparison to inform the target
claims. It purchased no target measurement and submitted with two credits
remaining. It made 14 tool requests including free inspection and submission.

**Sol:** bought the high trajectory, then measured target x(4.5), not x(4).
It used that reading (8.7462, noise standard deviation 0.1), the free time-1
observations, and the report trajectory to reject C5. It explicitly abstained
on C6 because neither target y(6) nor a sufficiently identified target
trajectory was available. Four tool requests include free evidence retrieval
and submission. Its C5 argument is indirect; this result is not a certificate
that a nearby measurement proves the claim's error.

## Important qualification to Luna's 6/6

Luna's final explanation argues that the accurately integrated target y(6)
lies **above** its stated C6 acceptance interval, after transferring an
Euler-to-high correction from the report parameters to candidate parameters.
The independently checked target y(6) is actually **5.49065010**, **below**
the reported value 7.335429119 and below the acceptance region.

Consequently its C6 **REJECT verdict is correct but its stated error direction
is wrong**. This is a concrete numerical inconsistency in its explanation,
not an LLM-judge score. The primary verdict metric remains 6/6, as specified;
we do not retrospectively change the scoring rule. However, this result should
not be presented as six scientifically justified verifications or evidence
that Luna's audit is more reliable than Sol's abstention. Neither explanation
is otherwise given an automated semantic grade.

## Runtime and API accounting

| Model | Responses | Input tokens across requests | Output tokens incl. reasoning | Seconds | Conservative API cost upper bound |
|---|---:|---:|---:|---:|---:|
| Luna | 14 | 155,236 | 8,329 | 126.861 | $0.04880380 |
| Sol | 4 | 22,102 | 11,440 | 208.357 | $0.33931000 |

Each episode had its own **$1 API ceiling**, 30-response limit, 32,768 output
tokens per response, 60-tool limit, and 20-minute deadline. No automatic retries,
substitutions, cap increases, or closing narrative calls were made. Both ended
by valid submission with no unsettled usage. Token totals include repeated
context; these conservative costs are not invoices. Scientific credits and
API dollars are separate ledgers.

Standard model pricing and high reasoning support were checked against the
[official pricing table](https://developers.openai.com/api/docs/pricing),
[Luna model documentation](https://developers.openai.com/api/docs/models/gpt-5.6-luna),
and [Sol model documentation](https://developers.openai.com/api/docs/models/gpt-5.6-sol).
Reservations used up to $0.25/$1.20 per million Luna input/output tokens and
$5/$20 for Sol, covering cache writes and reasoning output.

## Reproduction, verification, and local artifacts

See the [demo commands](../demos/multi_claim_audit/README.md#matched-20-credit-follow-up).
Model and budget are chosen by `prepare`, then frozen for `dry-run` and `live`.
Historical 32-credit commands retain their defaults. Previously completed
logs/results were not overwritten; recreating an old preparation after a code
update intentionally requires a fresh preparation rather than bypassing source
hash checks. Offline rendering needs no model or numerical execution.

**80 targeted checks passed:** 24 audit/budget tests, 42 reused API-runner tests,
and 14 planning-pilot tests. The added tests cover 20-credit enforcement,
identical observations, identical Luna/Sol prompts, the five-verdict fixed
control, frozen configuration, fake-model rehearsals for both models, and
byte-identical historical 32-credit prompt content. The entire slower legacy
suite was not rerun for this small configuration extension; its previous
passing result is documented in the 32-credit report.

Frozen source-manifest SHA-256:
`a8b12dcd9fdfac3d42e8cc42e87dcffdb982cf4b13a6cd47afa9953204e529be`.
Full per-file hashes, software versions, prompts/schemas, requests/responses,
stream events, reasoning summaries, trajectories, purchase logs and private
evaluations are retained locally:

- [Luna transcript](../demos/multi_claim_audit/runs/20260913T013647Z-live-0e840f58e4/transcript.md)
- [Luna generated report](../demos/multi_claim_audit/runs/20260913T013647Z-live-0e840f58e4/report.md)
- [Luna preparation and CPU control](../demos/multi_claim_audit/runs/20260913T013547Z-multi-claim-prepared-43b7258bfb/manifest.json)
- [Sol transcript](../demos/multi_claim_audit/runs/20260913T013934Z-live-6d177f24ff/transcript.md)
- [Sol generated report](../demos/multi_claim_audit/runs/20260913T013934Z-live-6d177f24ff/report.md)
- [Sol preparation and CPU control](../demos/multi_claim_audit/runs/20260913T013548Z-multi-claim-prepared-49f2c73b94/manifest.json)

These remain six related claims from one exploratory system, not a multi-system
comparison. The target is simulated, not a physical validation experiment.
