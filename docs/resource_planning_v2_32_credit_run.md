# GPT-5.6 Sol at 32 scientific credits

A later [matched Luna/high evaluation](resource_planning_v2_luna_run.md) used
the identical scientific prompt and instance; this page preserves the Sol run.

## Result: 2026-09-11

One new GPT-5.6 Sol/high episode completed **32/32 scientific credits** and
passed the 5% parameter requirement. Its largest relative parameter error was
**3.0347%**, versus **0.5461%** in the earlier 40-credit episode on this same
target and noise realization. This was a fresh investigation, not a resume:
the earlier conversation, purchases, and estimates were not given to the model.

| Method | Largest relative error, 32 credits | Pass at 32? | Largest relative error, 40 credits |
|---|---:|---|---:|
| GPT-5.6 Sol, high | 3.0347% | Yes | 0.5461% |
| Local-fitting baseline | 4.7000% | Yes | 0.8771% |
| Randomized GP baseline | 29.6749% | No | 20.1288% |
| Adaptive GP baseline | 17.5129% | No | 19.5484% |

All four methods used 32 credits in the new comparison, purchasing 12 low
simulations, one high simulation, and one target measurement each. Locations
and analysis differed. GPT purchased x at time 3.5, called the GP fitter twice,
and compared cached candidates once. All tool calls succeeded.

GPT submitted `[1.077, 0.115, 1.345]`, with relative errors
`[1.57690%, 3.03472%, 2.14584%]`. Its worst error normalized by the 5% tolerance
was **0.60694490**; passing requires at most 1. Its actual submission was scored,
not replaced by the helper's estimate.

Both GPT and the local baseline still passed, with smaller margins than at 40.
These are single-instance results, not success rates. The lower budget was
requested after viewing the 40-credit result; this is an exploratory paired
comparison, not a preregistered budget sweep. One model rollout per budget
cannot separate a systematic budget effect from model-run variability.
Identical purchase counts do not establish that one resource-allocation policy
is better; query locations and fitting also affect the result.

## Configuration and records

The target remains the first v2 evaluation target, seed 6000, with noise
replicate 0 (private noise seed 60000). All parameters and seeds remained outside
agent inputs. The frozen prompt is identical to the 40-credit prompt except
for budget amounts, including remaining-credit fields in free evidence. Tool
schemas, prices, bounds, noise, 5% tolerance, and fitting settings are unchanged.

High reasoning, 32,768 maximum output tokens per response, 30 responses,
1,200-second deadline, full-budget submission requirement, and the $3 API
ceiling were retained. No retry, substitution, interruption, or continuation
was needed. Complete API-visible logs, including returned reasoning summaries
and opaque encrypted replay items, are retained; raw internal reasoning is not
available.

The run took **254.855 seconds**, with **18 completed responses**, 132,475 input
tokens and 9,748 output tokens (9,243 reasoning tokens). The conservative API
cost upper bound was **$0.857335**, with zero unsettled reservations. This is
not an invoice. Scientific credits and API spending remain separate ledgers.

The matched local, random, and adaptive CPU baselines took approximately 0.140,
0.182, and 2.153 seconds respectively. They used independent budgets. The
existing lower-budget random policy was reused (one high, one measurement,
remaining credits on space-filling low simulations); local and adaptive
policies retained their existing algorithms and settings. No scientific
environment or policy implementation was changed or retuned.

- [Complete transcript](../demos/planning/runs/resource_agent_v2/20260911T134140Z-live-084f45e206/transcript.md)
- [Four-way comparison report](../demos/planning/runs/resource_agent_v2/20260911T134140Z-live-084f45e206/report.md)
- [Raw local run directory](../demos/planning/runs/resource_agent_v2/20260911T134140Z-live-084f45e206/)
- [Earlier 40-credit audit](resource_planning_v2_agent_run.md)

Raw logs and credentials remain untracked. Review private artifacts before sharing.

## Implementation and verification

The agent configuration now accepts scientific budgets 24, 32, or 40 for v2;
40 remains the default and the only supported v1 budget. Prompts, full-budget
gating, comparisons, reports, scripted fixtures, and resume messages all use
the configured amount. Resume restores the original budget and cannot override
it. No 24-credit live agent evaluation was run.

**265 tests passed** (251 shared, 14 planning-pilot), including five additional
lower-budget tests. The 32-credit offline CLI rehearsal also completed.
Post-run audits verified 52 source hashes, 1,930 contiguous events, all 18 exact
request-history replays, 13 purchased trajectories, scoring, and the completed
checkpoint. Shared observations match across methods. Transcript, report,
evaluation JSON, and event log remained byte-identical after regeneration.

- Source-manifest hash: `dd0f3c6bd1eb3f225121f47bdef155073b1eb3c8b4f4e733c431abe6ca692a34`
- Prompt hash: `7512cb102c2f556e795d794a96ff2ed60ac5e33ed405b8b9163f747a2da07109`
- Tool-schema hash: `e78d3daa1f2829965f2123ea6ca9eee17f253eb4cdc24a00bb52056ad301197f`
- Software: Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1, OpenAI SDK 2.54.0,
  httpx 0.28.1, budgeted-science 0.1.0.

Offline commands from the repository root:

```powershell
.\.venv\Scripts\python.exe demos/planning/src/run_resource_agent.py --dry-run --harder --scientific-budget 32 --api-ceiling-usd 3.00 --require-full-budget
.\.venv\Scripts\python.exe demos/planning/src/run_resource_agent.py --render demos/planning/runs/resource_agent_v2/20260911T134140Z-live-084f45e206
```

The executed live command was the first command above with `--live` instead of
`--dry-run`. Running it again would create another paid episode and requires
fresh authorization. Do not pass a budget override when using `--resume`.
