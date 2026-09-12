# Heat-workflow Luna/high: continuation fix and fresh rerun

## Result

**Luna/high completed all four cases with correct binary verdicts: 4/4.**
There were no abstentions, incomplete episodes, automatic retries, or tool-limit
violations. These are four fresh episodes, not continuations or retrospective
rescoring of the [earlier failed interaction](heat_workflow_luna_results.md).

| Development study | Luna verdict | Correct | Completed Python calls | Responses | Explicit continuations | Time (s) |
|---|---|---|---:|---:|---:|---:|
| Sound (`study-b116ba51e1`) | ACCEPT | Yes | 4 | 2 | 1 | 37.84 |
| Premature stopping (`study-86d7c8982e`) | REJECT | Yes | 6 | 3 | 2 | 39.80 |
| Spatial extraction (`study-8ef5b4e4cd`) | REJECT | Yes | 6 | 3 | 2 | 31.23 |
| Boundary mismatch (`study-e11e3c30ec`) | REJECT | Yes | 4 | 2 | 1 | 42.21 |

The unchanged CPU controls score **2/4** for refinement-only and **4/4** for
independent reconstruction. Their saved results were imported, not rerun. Always
REJECT would score 3/4. These studies still share **one physical problem**, and
there is no scientific-credit cap. This demonstrates working agent-written
analysis and objective verdict scoring, not a difficult budgeted benchmark or
general superiority over classical methods.

## What changed

- The heat adapter now requests **two hosted Python calls per response** and
  exposes `continue_audit()`. The latter starts a new response while preserving
  the same container, files, Python variables, and conversation history.
- The prompt explicitly distinguishes response-level limits from finishing an
  investigation. It provides no scientific solution or prescribed audit recipe.
  A genuine final ABSTAIN remains allowed and is never automatically overridden.
- API reservations and the tool-count guard use the same configured allowance.
  Three returned terminal executions would still stop this two-call protocol.
  Returned calls are archived and counted before that guard, so an interrupted
  response no longer misleadingly reports zero already-executed calls.
- The prior predator-prey runner retains its default one-call configuration.
  This opt-in heat interaction is version `heat-python-2`; old prepared runs
  cannot silently execute under the revised protocol.

The public study bundles were compared with the previous preparation and are
unchanged: report, intended PDE, executed configuration, solver log, analysis
source/result, and full x/y/T arrays. Private truth, reference answers, and CPU
outcomes remain outside the agent's inputs. No solver, case, scoring rule,
proposal document, or earlier saved result was changed.

## What Luna actually did

Every episode used `continue_audit` successfully. Across ten model responses,
there were twenty completed Python executions and six explicit continuations.
Luna inspected the public artifacts and implemented its own series-based
calculation for the intended Laplace boundary-value problem.

For the first three studies its calculation produced a patch mean near
**0.31202913598**, agreeing with the private independently checked reference.
Comparing this with the original printed value gave the correct verdicts. In
the boundary-mismatch case it also checked the actual boundary values in the
exported temperature field and identified the left boundary discrepancy.

**Correct verdicts do not mean every supporting calculation was correct.**
In the fourth episode the written sine-series integration used a difference of
`sinh` values for the vertical integral, where the antiderivative requires
`cosh`. It obtained **0.31921516709**, approximately **2.303% too high**. The
reported study value was 0.590588893, so the REJECT verdict remained correct
despite that supporting error. Its claimed 85.0% discrepancy differs from the
reference-based 89.27%. This numerical issue is disclosed, not silently repaired
or substituted with evaluator output. Explanations are not semantically scored.

Some additional within-response Python attempts were returned as nonterminal
`interpreting` items without outputs. They remain in the archive and are not
counted as executed. For example, the fourth episode's proposed sparse-solver
cross-check was not executed, so we do not credit it as an independent check.
The first episode also produced overflow warnings at excessive series orders;
its smaller finite truncations already agreed on the correct patch mean.

## Model settings and spending

Exact model `gpt-5.6-luna`, reasoning `high`, streaming Responses API, standard
service tier, `store=false`, requested reasoning summaries and opaque encrypted
reasoning replay. Every study had a fresh network-disabled 1 GB container.
Limits remained 30 responses, 30 custom-function requests, 32,768 output tokens
per response, and 20 minutes per episode. No model substitution was permitted.

The **new batch's $2 total ceiling**, including hosting, was not increased.
To cover two built-in executions and their subsequent model passes, each request
reserves up to **$1.4419824** before generation. This uses three maximum-size
input passes and the full output allowance at conservative long-context/cache-
write prices. Unused reservation is released only after validated usage arrives;
unknown usage retains its reservation and halts further work.

| Component | Conservative upper accounting |
|---|---:|
| Model tokens: 46,254 input; 6,153 output including reasoning | $0.0342024 |
| Four container allowances ($0.09 each) | $0.3600000 |
| New batch total | **$0.3942024** |

These bounds are **not an invoice**. All request usage settled. All four
containers were archived and deleted. The earlier batch's $0.3799683 remains a
separate recorded attempt; the two batch upper bounds sum to $0.7741707.
Model capabilities, tool-limit semantics, and rates were checked against
[Luna documentation](https://developers.openai.com/api/docs/models/gpt-5.6-luna),
the [Responses reference](https://developers.openai.com/api/reference/resources/responses/websocket-events#response.create),
and [official pricing](https://developers.openai.com/api/docs/pricing).

## Records and reproduction

- [New live report and all transcript links](../demos/claim_verification/runs/20260912T230337Z-heat-luna-live-7d3a5ca74c/report.md)
- [Complete new live directory](../demos/claim_verification/runs/20260912T230337Z-heat-luna-live-7d3a5ca74c/)
- [Frozen revised preparation](../demos/claim_verification/runs/20260912T230230Z-heat-python-prepared-183e70462d/)
- [Zero-cost continuation rehearsal](../demos/claim_verification/runs/20260912T230315Z-heat-luna-dry-run-ed9cf0459b/report.md)
- [Original CPU setup and results](heat_workflow_results.md)

```powershell
python -m budgeted_science.agents.heat_workflow_agent prepare
python -m budgeted_science.agents.heat_workflow_agent dry-run <prepared-directory>
# Paid; only after explicit authorization of a fresh evaluation:
python -m budgeted_science.agents.heat_workflow_agent live <prepared-directory>
python -m budgeted_science.agents.heat_workflow_agent render <saved-campaign-directory>
python -m unittest discover -s tests -p test_heat_workflow_agent.py -v
python -m unittest discover -s tests -p test_verification_python.py -v
```

Before live execution, **60 relevant tests passed**: 21 heat numerical/workflow,
17 heat-agent adapter, and 22 prior hosted-Python tests. The four-case scripted
rehearsal explicitly exercised two calls, continuation, then a third call in
another response. The actual captured fourth response from the previous run
also passed an offline two-call/replay/schema check without executing code or
changing that earlier outcome. The 14 planning-pilot tests passed separately.

The full shared regression suite passed **761 tests** (286.8 seconds), for
**775 passing tests including the planning pilot**. Offline regeneration of all
four episode transcripts, Python listings, reports, and evaluation JSON, plus
the campaign summary/report, reproduced identical hashes. All ten generation
requests used the frozen Luna/high settings and two-call allowance; each episode
retained its container across responses and confirmed deletion at completion.
The original CPU experiment's artifact hashes still match its completion record.

Complete logs, code, outputs, prompts, schemas, source hashes, usage, and private
evaluations remain local and ignored by Git. Available reasoning summaries are
preserved; raw internal reasoning is unavailable. No credentials or raw runs
are committed, and no changes are pushed.
