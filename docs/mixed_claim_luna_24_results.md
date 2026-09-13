# Mixed-claim audit: Luna/high at 24 credits

Executed September 12, 2026 local time (September 13 UTC). The owner requested
one fresh Luna episode with 24 scientific credits on the existing mixed-claim
study. Only the cap and its accounting fields changed; the six claims,
presentation order, target, observation noise stream, tools, 1/8/12 prices,
scoring and all other operational settings were preserved.

## Results

| Investigator | Cap | Spent | Correct / 6 | Wrong | Abstained |
|---|---:|---:|---:|---:|---:|
| Luna/high, new episode | 24 | 23 | 5 | 1 | 0 |
| Fixed shared-evidence control, new matched run | 24 | 20 | 3 | 0 | 3 |
| Luna/high, previous episode | 32 | 27 | 5 | 1 | 0 |
| Fixed shared-evidence control, previous run | 32 | 32 | 4 | 0 | 2 |

The new Luna verdicts exactly match its earlier 32-credit verdicts. The single
wrong answer is **C6**, which asserts at least 20% target prey recovery between
t=4 and t=6. Actual recovery is **31.63049%**, so ACCEPT is correct. Luna
returned REJECT, estimating a 38.14% decline from a fitted low-fidelity candidate.

| Claim | Truth | Luna at 24 | CPU at 24 |
|---|---|---|---|
| C1: target x(4) agreement | REJECT | REJECT | REJECT |
| C2: numerical x(0.5) accuracy | ACCEPT | ACCEPT | ACCEPT |
| C3: cumulative abundance | ACCEPT | ACCEPT | ACCEPT |
| C4: intervention peak reduction | REJECT | REJECT | ABSTAIN |
| C5: target population-ratio agreement | REJECT | REJECT | ABSTAIN |
| C6: target recovery | ACCEPT | REJECT | ABSTAIN |

This is one fresh stochastic model episode on the same exploratory scientific
system, not a new independent system or a multi-sample budget study. The same
accuracy at 24 and 32 credits does not establish that budget has no effect.

## Investigation and resource use

Luna purchased the baseline and intervention high-fidelity trajectories first:
2 x 8 = 16 credits. It then purchased seven low-fidelity candidate trajectories:
7 x 1 = 7 credits. It used free comparisons and evidence retrieval before
submitting with one credit remaining. No paid target measurements were acquired.
The only target evidence used was the initially supplied noisy x(1),y(1).

It selected low-fidelity candidate (0.95, 0.085, 1.0), whose early predictions
x(1)=15.22267 and y(1)=4.66804 were close to the observed 15.19527 and 4.69940.
It extrapolated that candidate's x(4)=12.35445, x(6)=7.64070 and y(6)=8.30743
to classify the target claims. The implied recovery is -0.3814, whereas the
actual target recovery is +0.3163. Matching those sparse early measurements
did not provide a reliable later trajectory in this investigation.

C5 was correctly rejected, but the predicted ratio was about 1.0873 (above
the report's 0.6892), while the actual ratio is 0.4412 (below it). Therefore
five correct verdicts do not imply five correct numerical explanations.
No semantic judge or justified-confidence score was introduced.

The unchanged fixed policy bought a high baseline trajectory (8) and target
x(4) (12), then could not afford its remaining planned acquisitions. It
answered C1/C2/C3 and abstained on C4/C5/C6. Its four unused credits reflect
this fixed policy, not an optimality claim or an inability to spend more.

## Execution and verification

- Exact model `gpt-5.6-luna`, high reasoning; one live episode, no retry/resume.
- 24 scientific credits; unchanged $1 API ceiling; 30 responses, 60 tool
  requests, 32,768 output tokens per response and a 20-minute deadline.
- **12 responses / 12 tool requests**, **128.296 seconds**.
- **135,568 input tokens / 11,021 output tokens**, including reasoning.
- Conservative API-cost upper bound: **$0.04711720**; no uncertain reservations.
  This is not an invoice. [Official pricing](https://developers.openai.com/api/docs/pricing)
  was checked: $0.25/M cache-write-inclusive input bound and $1.20/M output.
  [Official Luna documentation](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
  confirms high reasoning, streaming and function calling.
- 73 targeted tests passed, with one optional historical-parent migration
  check skipped because that parent already has a completed continuation.
  Coverage included cap enforcement, unchanged study/evidence, exact prompts
  after normalizing budget fields, frozen launches, CPU accounting, logging,
  offline regeneration, model selection and reused API safeguards.
- A separate local dry run completed before the live run. No credentials or
  API calls were used in tests or dry-run execution. Previous runs are preserved.

Frozen source-manifest SHA-256:
`f83d8947dbc96b96fe0e8aa74a9e3c3da94c7b218ae10c2e6cb103db3f037856`.
Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1, OpenAI SDK 2.54.0, HTTPX 0.28.1.
Full configuration, per-file hashes, API-visible history, trajectories and
private evaluation are retained in the ignored local run directory.

## Artifacts and commands

- [Luna transcript](../demos/mixed_claim_audit/runs/20260913T032043Z-live-1d69b50ff7/transcript.md)
- [Generated comparison report](../demos/mixed_claim_audit/runs/20260913T032043Z-live-1d69b50ff7/report.md)
- [Complete event log](../demos/mixed_claim_audit/runs/20260913T032043Z-live-1d69b50ff7/events.jsonl)
- [Frozen preparation](../demos/mixed_claim_audit/runs/20260913T032001Z-mixed-prepared-5dd98f3f07/manifest.json)
- [Matched CPU transcript](../demos/mixed_claim_audit/runs/20260913T032001Z-mixed-prepared-5dd98f3f07/cpu/20260913T032002Z-fixed-cpu-9efc897cda/transcript.md)
- [Earlier Luna result](mixed_claim_audit_results.md)
- [Earlier completed Sol result](mixed_claim_sol_resumed_results.md)

```powershell
.\.venv\Scripts\python.exe -m budgeted_science.agents.mixed_claim_audit prepare --model gpt-5.6-luna --budget 24
.\.venv\Scripts\python.exe -m budgeted_science.agents.mixed_claim_audit dry-run <prepared-directory>
# A new paid episode requires fresh owner authorization:
.\.venv\Scripts\python.exe -m budgeted_science.agents.mixed_claim_audit live <prepared-directory>
.\.venv\Scripts\python.exe -m budgeted_science.agents.mixed_claim_audit render <episode-directory>
```

Raw logs and credentials remain ignored. No proposal documents were changed,
and nothing was pushed.
