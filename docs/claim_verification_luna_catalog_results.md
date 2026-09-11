# Luna: all 30 claim-verification development studies

Completed September 11, 2026. Exactly 30 new live episodes with
`gpt-5.6-luna`, high reasoning, on the unchanged development catalog.
Every episode submitted successfully; there were no retries or resumes.

## Results

| Study category | Luna correct | Fixed verifier correct | Expected verdict |
|---|---:|---:|---|
| Sound numerical study | 6/6 | 6/6 | ACCEPT |
| Harmless integration degradation | 6/6 | 6/6 | ACCEPT |
| Consequential integration degradation | 6/6 | 6/6 | REJECT |
| Harmless output-sampling degradation | 6/6 | 6/6 | ACCEPT |
| Consequential output-sampling degradation | 6/6 | 6/6 | REJECT |
| **Total** | **30/30** | **30/30** | |

Luna correctly accepted all 18 valid claims and rejected all 12 invalid claims.
False acceptance: 0/12; false rejection: 0/18; coverage: 30/30; abstentions: 0;
incomplete outcomes: 0. Each of the three report formats scored 10/10, and each
of the six underlying systems scored 5/5. These are related development variants,
not 30 independent physical systems or held-out scientific tasks.

Every episode used **5/5 audit credits**: 150 in total. The fixed verifier had
an independent ledger per case and also spent 5 each. Its earlier 30-case run
and Terra's earlier single-case run remain preserved and are not added to
Luna's sample count.

## Frozen task and execution

The task remains an audit of a completed predator-prey numerical study. The
claim concerns the maximum prey population on [0,8], accurate within 5%.
The original printed claim is scored against the private independently checked
reference. This is numerical verification, not physical validation.

The six systems are the existing development seeds 7100-7105. Each has a sound
study plus harmless/consequential integration and sampling variants. All 30
were evaluated in existing catalog order, without filtering, replacement,
retuning or changes to reports, prices, prompts, tools or numerical settings.

Each episode starts a fresh conversation and its own purchase ledger.
Inputs include the report, public artifact inventory, audit instructions and
tool schemas. Neither target parameters/equations nor references, labels,
case-generation categories or comparison results are supplied to the model.

- Model: exact `gpt-5.6-luna`; reasoning: high; standard service tier.
- Streaming Responses API; store=false; sequential function execution;
  requested reasoning summaries and opaque encrypted reasoning replay.
- Audit credits: 5; integration refinement costs 3, sampling refinement 2.
- API ceiling: USD 3 per episode, at most USD 90 across 30 slots. No transfer
  of unused allowances, automatic retry, substitution or limit increase.
- Limits per episode: 30 responses, 30 tool requests, 32,768 output tokens
  per response and 20 minutes of active agent time.
- No full-budget requirement, savings bonus, spending penalty, arbitrary-code
  execution or LLM-based judge.

The ordinary fixed numerical verifier was run independently on each case
using only public audit tools. It reads the structured analysis value, buys
integration then sampling refinement, and compares against the original claim.
It is not a general free-form report-understanding baseline.

## Observable actions and usage

All episodes bought both check types. Integration preceded sampling in 20;
sampling preceded integration in 10. In 20 episodes the second check used the
first purchased run; in 10 the two checks operated separately on the original
run. No tool-argument or tool-execution errors were returned. These are observed
action counts, not a semantic diagnosis or reasoning-quality score.

There were **249 model responses**, 649,884 input tokens and 37,591 output
tokens, including 21,681 reasoning tokens. Input usage includes repeated/cached
conversation material. Total recorded agent time was **793.371 seconds**
(13.22 minutes), mean **26.446 seconds per episode**, excluding the independent
CPU comparisons.

The recorded API cost lower/upper bounds are **USD 0.08196750 to USD 0.20758020**.
These are usage-based bounds, not an invoice. The conservative upper bound
prices inputs at the cache-write rate. No uncertain reservations remained.
Luna's standard rates were checked against the
[official pricing documentation](https://developers.openai.com/api/docs/pricing).

All 50 mechanically recognized run-ID numeric citations matched their purchased
records. Other prose and numbers were not semantically graded. Returned
reasoning summaries and encrypted reasoning are retained, not raw internal
reasoning.

## Records, checks and reproduction

- [All 30 results and transcript links](../demos/claim_verification/runs/20260911T234013Z-luna-catalog-live-996a55abe9/report.md)
- [Machine-readable aggregates](../demos/claim_verification/runs/20260911T234013Z-luna-catalog-live-996a55abe9/summary.json)
- [Frozen manifest, case identities and source hashes](../demos/claim_verification/runs/20260911T234013Z-luna-catalog-live-996a55abe9/manifest.json)
- [Sound-study transcript](../demos/claim_verification/runs/20260911T234013Z-live-d6bc2e7d97/transcript.md)
- [Integration-error transcript](../demos/claim_verification/runs/20260911T234105Z-live-8a82a91be6/transcript.md)
- [Sampling-error transcript](../demos/claim_verification/runs/20260911T234152Z-live-c6e3f13daf/transcript.md)

Raw directories remain local and untracked. Every episode retains requests,
stream events, full responses, exact tool results, numerical artifacts, private
evaluation and a readable transcript. The campaign keeps durable launch markers
and per-case result records. No credentials are committed.

Before launch, **376 tests passed** (362 root tests plus 14 planning-pilot tests),
and all 30 slots completed a separate no-API scripted rehearsal. The rehearsal
was not model performance. Four new tests cover batch independence, preserved
uncertain attempts without retry, aggregate denominators and catalog validation.

Post-run checks verified exactly 30 launched/completed slots, all 249 complete
request/response pairs from Luna, unchanged settings/source/catalog, fresh
histories and absence of evaluator fields in generation inputs. Every episode
report/transcript/evaluation and the aggregate report regenerated byte-for-byte
without solver execution or credential access.

Frozen source-manifest hash:
`1d5b6a551af3ba6bd51618cf71656d91a0c4de8a0856177b9b64053a1f759748`.
Catalog digest:
`a761b84be95282af425dee18949d718f17866dd094224f9826f82b9b0d0c7d19`.
Tool-schema hash:
`53f9b3341e56cea5fd1faef3445b00ac804ee48842268b3bad2c7b1cd14ee0b9`.
The launch used the new batch wrapper atop checkpoint `0227605`; exact source
bytes are pinned in the manifest. Software: Python 3.13.5, NumPy 2.3.4,
SciPy 1.16.1, OpenAI SDK 2.54.0, HTTPX 0.28.1, budgeted-science 0.1.0.

Regenerate the aggregate offline from the repository root:

~~~powershell
.\.venv\Scripts\python.exe -B -m budgeted_science.agents.verification_catalog --render demos/claim_verification/runs/20260911T234013Z-luna-catalog-live-996a55abe9
~~~

New paid evaluations require separate authorization. See the
[runner and batch protocol](claim_verification_agent_protocol.md) for commands.

## Interpretation

The pipeline is operational across both error mechanisms and harmless controls.
However, **this configuration does not separate Luna from a fixed two-check
verifier**. Both checks fit the budget, the claim family is fixed, and cases
have clear margins around the threshold. The results do not demonstrate an
adaptive-allocation advantage, calibrated confidence, general scientific
verification ability or robustness to arbitrary reports. A general ranking of
Luna versus Terra is not justified by 30 cases versus one earlier sound case.
