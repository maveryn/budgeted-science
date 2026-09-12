# Heat-workflow Luna/high run: interface failure

## Outcome

The four authorized live episodes were attempted once each. **Three ended in
ABSTAIN and one ended without a submission after a hosted-tool guard fired.**
There were no harness-accepted binary verdicts and no scored ACCEPT/REJECT coverage. This is
not evidence that Luna cannot solve the heat problem or that this benchmark is
difficult: the first three did not complete an audit, and the fourth response
actually proposed a correct REJECT that the tool-limit guard did not accept.

| Development study | Reference verdict | Luna outcome | Returned completed Python executions | API responses |
|---|---|---|---:|---:|
| Sound (`study-b116ba51e1`) | ACCEPT | ABSTAIN | 1 | 1 |
| Premature stopping (`study-86d7c8982e`) | REJECT | ABSTAIN | 1 | 1 |
| Spatial extraction (`study-8ef5b4e4cd`) | REJECT | ABSTAIN | 1 | 1 |
| Boundary mismatch (`study-e11e3c30ec`) | REJECT | Correct raw REJECT; guard stopped processing | 2 | 1 |

The last row's raw response contains two completed executions even though
`max_tool_calls=1` was requested. The guard rejected that response before its
accepted-execution counter was updated, so the original episode's `code_calls`
field is **0**, not the number of executions visible in its raw response. Both
returned code blocks and outputs remain in its `python.md` and API archive.
Nonterminal `interpreting` items are not counted as completed executions.

## What went wrong

The first execution in each episode loaded the JSON bundle and displayed its
keys. In the first three cases, subsequent within-response Python attempts had
nonterminal status and no output. Luna then submitted ABSTAIN, explaining that
it could not inspect the actual files after exhausting the available execution.
The prompt explicitly allowed Python use across responses, but the combination
of the per-response tool limit and the final-submit action did not produce that
continuation. The submitted abstentions ended their episodes as required.

The fourth response returned a second completed Python call. It displayed the
report, configuration, and other artifacts. Luna then proposed REJECT, identifying
left=0.5 in the executed setup versus left=0 in the intended setup, and giving an
intended mean of approximately 0.312 from a separation-of-variables calculation.
The response was rejected by the existing one-completed-call guard before that
submission could be processed. The raw verdict agrees with the private reference,
but we do not silently waive the frozen guard or replace the incomplete recorded
outcome. This is a different failure from an incorrect scientific verdict. The logs establish the
returned statuses; they do not establish why the service returned two completed
calls despite the requested limit.

No episode exhausted its dollar allowance or 20-minute deadline. No model was
substituted and no attempt was automatically retried. The frozen scientific
cases, numerical criteria, and original CPU results were not changed.

Before another scientific comparison, the hosted interaction needs a tested
way to continue analysis across requests. One candidate is an explicit free
`continue_audit` action, so the model can yield a request without submitting a
verdict. Tool-limit handling and conservative billing bounds also need to be
checked against this captured response. **Neither correction nor another paid
evaluation is claimed here.** Increasing physical complexity is not the next
step suggested by this run.

## Inputs and protocol

These are the same four development studies from the
[CPU heat-workflow prototype](heat_workflow_results.md), sharing one mathematical
target: steady Laplace heat flow on a unit square, with a claim about the mean
temperature over x=[0.1,0.3], y=[0.6,0.8], accurate within 5%.

Every fresh, network-disabled 1 GB Python container received only a public JSON
bundle: report, intended problem, executed configuration, solver log, literal
analysis source, analysis result, and a lossless export of the saved x/y/T arrays.
Private labels, reference answers, and CPU outcomes were not uploaded. Luna could
write Python and use available numerical libraries; there were no local solver
or ready-made verification tools. Its sole custom function was `submit`.

Exact model: `gpt-5.6-luna`; reasoning: `high`; streaming Responses API;
standard service tier; `store=false`; requested summaries and opaque encrypted
reasoning replay. Each episode had 30 responses, 32,768 output tokens per
response, one requested hosted Python call per response, and a 20-minute limit.
There was **no scientific-credit cap** or spending bonus. Model settings and
hosting support were checked against the [official Luna documentation](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
and [Code Interpreter documentation](https://developers.openai.com/api/docs/guides/tools-code-interpreter).

The $2 ceiling applied to the **entire four-case batch**, including hosting.
The runner carried earlier committed upper bounds forward and retained full
reservations on uncertain usage. It made four generation requests in total,
using 17,829 input tokens and 6,141 output tokens (including reasoning).
All usage settled; all four containers were archived and deleted afterward.

| Component | Conservative upper accounting |
|---|---:|
| Model tokens, all four episodes | $0.0199683 |
| Four container allowances ($0.09 each) | $0.3600000 |
| Combined | **$0.3799683** |

These are conservative accounting bounds, **not an invoice**. The container
allowance exceeds the documented $0.03 per 20-minute 1 GB session; model usage
is bounded using long-context/cache-write rates. See [official pricing](https://developers.openai.com/api/docs/pricing).

Unchanged CPU controls scored 2/4 for refinement-only and 4/4 for independent
reconstruction. Always REJECT would score 3/4. The failed agent interface makes
this batch unsuitable for a scientific method comparison, irrespective of
these CPU results. Explanations and evidence references are retained, not
semantically graded; no LLM judge is used.

## Saved records and commands

- [Live report and transcript links](../demos/claim_verification/runs/20260912T224219Z-heat-luna-live-dd90084626/report.md)
- [Complete live directory](../demos/claim_verification/runs/20260912T224219Z-heat-luna-live-dd90084626/)
- [Frozen preparation](../demos/claim_verification/runs/20260912T224138Z-heat-python-prepared-b6438afc3b/)
- [Zero-cost scripted rehearsal](../demos/claim_verification/runs/20260912T224204Z-heat-luna-dry-run-a5c6fc0989/report.md)

The live directory retains chronological streaming events, requests, responses,
source hashes and versions, public uploads, private evaluations, transcripts,
and downloaded container artifacts as inert bytes. Available reasoning summaries
are retained; raw internal reasoning is not available. Raw runs remain ignored
by Git. No proposal document or previous experiment is modified.

```powershell
python -m budgeted_science.agents.heat_workflow_agent prepare
python -m budgeted_science.agents.heat_workflow_agent dry-run <prepared-directory>
# Paid; requires fresh explicit authorization. A prepared batch is live-attemptable once.
python -m budgeted_science.agents.heat_workflow_agent live <prepared-directory>
python -m budgeted_science.agents.heat_workflow_agent render <saved-campaign-directory>
python -m unittest discover -s tests -p test_heat_workflow_agent.py -v
python -m unittest discover -s tests -p test_verification_python.py -v
```

Offline rendering reads saved records and never reruns a solver or calls the API.
Preparation validates the original CPU artifact hashes. Execution validates
frozen source, prompt, tool, and study hashes. After source changes, create a new
preparation for any separately authorized evaluation; do not bypass old guards.

Before live execution, all **54 relevant tests** passed: 21 heat numerical and
workflow tests, 11 new adapter tests, and 22 existing hosted-Python tests. The
four-case dry run passed without credentials. The preserved planning-pilot's
14 tests also passed. These checks validate implemented contracts and synthetic
fixtures; they did not predict this live tool-limit interaction.

All four transcripts regenerated identically offline, original CPU artifact
hashes remained unchanged, and the saved requests confirmed the exact Luna/high
settings. Credentials and raw logs were checked to remain ignored by Git.

With sources frozen, the complete shared regression suite passed **755/755**
tests in 582 seconds; together with the 14 planning-pilot tests, **769 tests
passed**. No regression guard was disabled and no live API call was made by tests.
