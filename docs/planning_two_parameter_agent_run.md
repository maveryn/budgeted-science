# First completed two-parameter planning agent episode

## Outcome

One authorized GPT-5.6 Sol episode completed with a valid 16-value forecast
submission. No retry or additional paid closing response was made.

| Run | Normalized forecast RMSE | Scientific credits |
| --- | ---: | ---: |
| GPT-5.6 Sol, high reasoning | 0.01834035886 | 19.80232558 |
| Fixed numerical policy | 0.01812008958 | 17.87596899 |

Lower error is better. The agent's error was about 1.22% higher on this single
instance while spending more scientific credits. This is not evidence of a
general ranking, a statistically significant difference, or an adaptive-planning
advantage. The comparison recipe was selected during development on this same
instance, not tuned on held-out tasks, and is not claimed to be optimal.

## Frozen configuration

- Task: joint viscosity/amplitude inference followed by an actual forecast.
  Calibration initial condition `A*sin(x)`; forecast `1.5*A*sin(x)`.
- Public ranges: `nu in [0.1,0.3]`, `A in [0.8,1.2]`; candidate grids 32/64/128.
- Private harness instance: `nu=0.23`, `A=1.1`, observation seed 0. These were
  omitted from agent prompts and tool definitions.
- Scientific budget: 20 shared credits; two credits per five-time sensor record;
  observation noise standard deviation 0.01. The work normalizer and score scale
  remain 16,512 RHS-grid work units per credit and 1.5 respectively.
- API: exact model `gpt-5.6-sol`, high reasoning, standard service tier, streaming,
  `store=false`, reasoning summaries and opaque encrypted reasoning retained.
- User-approved response cap: 32,768 output tokens, raised explicitly from 8,192.
  Other limits unchanged: $2 ceiling, 30 responses and 1,200 seconds per episode.
- Tool-only environment: no Python workspace, browser or exact-candidate solver.
  Candidate amplitude is supplied to `simulate`; `fit` estimates both parameters.
- Code checkpoint: `c8fd9fb`; detailed source hashes are in the run manifest.

The model supports these settings; rates were checked against the
[official model documentation](https://developers.openai.com/api/docs/models/gpt-5.6-sol).
The larger token cap is opt-in; legacy/default runs retain 8,192.

## Observed workflow and costs

The agent acquired two records at each of the three sensors (12 credits),
requested an N=32 joint fit capped at 20 predictor calls, then an N=64 joint fit
capped at four calls. It computed three forecasts: one at N=64 and two at N=32.
Fitting/calibration cost 6.56589147 credits; forecasting cost 1.23643411 credits.
It submitted a 16-value profile with 0.19767442 scientific credits remaining.
The score uses this actual submitted profile, without replacing it with a
reference prediction at an estimated parameter.

The fixed policy bought one record per sensor, ran an N=64 joint fit capped at
12 predictor calls, and submitted its N=64 forecast. Its fit reached its
evaluation limit; the resulting forecast was complete and scoreable. It had an
independent ledger with matching target and sensor/replicate noise, and its
results were never shown to the agent.

The episode used 13 model responses and 435.77 seconds (about 7.3 minutes).
Total API usage was 52,723 input tokens and 21,972 output tokens, of which
21,459 were reasoning tokens. The last response alone used 18,334 output tokens,
including 18,237 reasoning tokens, and contained the valid submission.

Accounting estimates range from $0.492868 to the conservative upper bound
$0.703055; these are not an invoice. No uncertain reservation remained after
completion. Each generation was reserved at its maximum permitted cost before
sending, including the larger output allowance.

## Logs and verification

Local ignored directory:
`demos/planning/runs/20260911T031739Z-live-4cf7462531/`.

It contains the readable transcript and report, all request bodies and returned
responses, streaming events, complete numerical artifacts, acquired records,
private evaluation and manifest. Returned summaries are preserved; raw internal
reasoning is not exposed, and encrypted reasoning is kept as opaque data.

Before the live call, all 117 offline tests passed (103 shared/runner tests plus
14 planning-demo tests). After completion, an independent NumPy calculation
reproduced the submitted-profile score. The audit checked all 13 request/response
pairs, exactly one successful submission, model/effort/output-cap settings,
matching source hashes and paired observations. Offline report regeneration
left all 103 checked authoritative files byte-for-byte unchanged.

Offline inspection only:

```powershell
python demos/planning/src/run_agent.py --render demos/planning/runs/20260911T031739Z-live-4cf7462531
```

The original one-parameter attempts and CPU trial remain preserved. No extra
agent run, proposal edits, credential tracking or remote push was performed.
