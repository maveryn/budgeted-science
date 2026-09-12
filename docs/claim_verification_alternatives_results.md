# Predator-prey: original versus expanded audit tools

Executed on 12 September 2026. **Luna/high scored 5/5 with each menu**, using
five scientific credits in every episode. Ten fresh model episodes completed,
with no abstentions, incorrect verdicts, incomplete outcomes or retries.
Adding these plausible alternatives did not make this small task harder for
Luna. The unchanged fixed numerical verifier also gets 5/5 with either menu.

## What changed

The [frozen protocol](claim_verification_alternatives_protocol.md) keeps the
original predator-prey numerical model, original reports, peak-accuracy claim,
5% tolerance, hidden reference and five-credit budget. Five existing studies
were selected by category index `i` at seed `7100+i`, before this experiment's
checks. These are five development systems, not new held-out systems.

Both conditions have the same scientific prompt and original tool definitions.
The expanded menu additionally offers:

- `tighten_integration`: halve an Euler step or reduce adaptive tolerances by
  a factor of ten, keeping output times; **1 credit**.
- `bisect_output`: insert one midpoint per output interval, keeping integration
  settings; **1 credit**.
- `crosscheck_integrator`: use Radau with tight tolerances at the same output
  times; **3 credits**.

These perform genuine computations. They are not secretly faulty tools and
are not labelled as distractors. Their relevance depends on the calculation.
The original complete verification route remains affordable. Prices are
illustrative flat resource credits, not measured runtime or money.

## Paired live results

Each menu/case starts with its own conversation, scientific ledger and API
history. Menu execution order alternates across cases. Both columns below
contain correct verdicts; every episode spent exactly five credits.

| Development category | Seed | Original menu | Expanded menu |
|---|---:|---|---|
| Sound study | 7100 | ACCEPT | ACCEPT |
| Harmless integration degradation | 7101 | ACCEPT | ACCEPT |
| Consequential integration degradation | 7102 | REJECT | REJECT |
| Harmless sampling degradation | 7103 | ACCEPT | ACCEPT |
| Consequential sampling degradation | 7104 | REJECT | REJECT |

Luna used added tools on **three of the five expanded-menu cases**, making
five paid extra-tool calls in total: Radau three times, integration tightening
once, and output bisection once. It did not simply ignore all alternatives.

| Expanded-menu case | Paid calculation sequence |
|---|---|
| Sound | Dense sampling, then Radau on that sampled run |
| Harmless integration | Original integration refinement, then dense sampling |
| Consequential integration | Radau on the original run; separately tighten original integration, then bisect that run's output |
| Harmless sampling | Dense sampling, then original integration refinement |
| Consequential sampling | Dense sampling, then Radau on that sampled run |

The Radau-plus-dense-sampling combinations are legitimate alternative routes.
An extra-tool call is not automatically wasted effort. The comparison provides
no evidence of lower accuracy or a harder budget-allocation problem here.
Explanations were retained, not semantically graded.

## CPU checks

The fixed two-check procedure is unchanged: purchase high-accuracy integration,
then dense sampling; compare the original reported value with that purchased
result at the 5% threshold. It receives only public tools and uses independent
budgets in each condition.

| CPU procedure | Correct | Mean credits |
|---|---:|---:|
| Fixed two-check, original menu | 5/5 | 5 |
| Fixed two-check, expanded menu | 5/5 | 5 |
| Only integration tightening | 3/5 | 1 |
| Only output bisection | 4/5 | 1 |
| Only Radau at existing output times | 4/5 | 3 |

The last three are deliberately limited diagnostic controls, not complete
competitive verifiers. They show why a check cannot always settle the claim.
For example, Radau at the original sparse output times retains about 10.01%
peak error on the consequential-sampling case. Output bisection preserves
about 6.45% integration error on the consequential-integration case. Genuine
calculations can therefore provide insufficient evidence without being broken.

There were 25 CPU policy/check episodes on the five studies, not 25 independent
scientific problems. CPU expenditure on the model API was zero.

## API accounting and runtime

| Menu | Input tokens | Output tokens | Mean episode seconds | API lower estimate | API upper bound |
|---|---:|---:|---:|---:|---:|
| Original | 127,714 | 6,786 | 33.67 | $0.01575962 | $0.04007170 |
| Expanded | 101,667 | 6,059 | 24.82 | $0.01290954 | $0.03268755 |

Output counts include reasoning. The total accounting interval is
**$0.02866916-$0.07275925**, below the **$2 whole-batch ceiling**; it is not an
invoice. No uncertain billing or outstanding reservation remained. Runtime
includes API waiting and logging and is not a controlled latency comparison.
No conclusion about speed or token efficiency follows from five pairs.

## Records, compatibility and verification

- [Live aggregate report and all ten transcripts](../demos/claim_verification/runs/20260912T200438Z-prey-menu-live-1496fbbbfa/report.md).
- [Complete local live records](../demos/claim_verification/runs/20260912T200438Z-prey-menu-live-1496fbbbfa/).
- [Frozen live manifest](../demos/claim_verification/runs/20260912T200438Z-prey-menu-live-1496fbbbfa/manifest.json) and [machine-readable results](../demos/claim_verification/runs/20260912T200438Z-prey-menu-live-1496fbbbfa/summary.json).
- [CPU report and diagnostic traces](../demos/claim_verification/runs/20260912T200004Z-prey-menu-cpu-dfb0a07fb5/report.md).
- [Saved offline rehearsal](../demos/claim_verification/runs/20260912T200035Z-prey-menu-dry-run-b77a96c79c/report.md).
- [Post-run CPU compatibility replay](../tmp/prey_menu_compatibility/20260912T201045Z-cpu-replay-d7ad19d977/results.json).

The live source freeze remained unchanged through all ten slots. A regression
check detected that an initial shared-class refactor changed an older
experiment's expected source hash. After the live run, the original environment
was restored byte-for-byte and extension dispatch/pricing moved into the new
module. Replaying all ten saved scientific action sequences then matched
**all 83 tool responses exactly**, including numerical outputs and charges.
This was CPU-only compatibility verification, not new model samples.

Saved live hashes correctly identify the pre-isolation implementation; they
were not rewritten. To run another campaign with the final isolated source,
prepare a new CPU directory first. Existing raw results remain immutable.
Offline rendering of the saved experiment does not depend on current source
hash equality and still verifies its recorded artifact/event consistency.

The 14 new targeted tests passed after isolation. The full shared suite then
passed **689 tests**, and all **14 planning-pilot tests** passed: **703 total**.
Coverage includes numerical settings, original-tool equivalence, paid cache
behavior, charged failures, chained checks, identical prompts, hidden-data
separation, archived source integrity and full offline campaign replay.

Rebuild only the saved aggregate report, without API calls or solver execution:

```powershell
python -m budgeted_science.agents.verification_alternatives_catalog --render demos/claim_verification/runs/20260912T200438Z-prey-menu-live-1496fbbbfa
```

## Interpretation

This is a small tool-menu robustness experiment. The alternatives changed some
workflows, but neither accuracy nor scientific expenditure changed. It does
not demonstrate general robustness to irrelevant tools, superiority over a
classical verifier, or a need for adaptive auditing. The original successful
route remains obvious and affordable, and some added actions offer other
successful routes. Merely adding this menu did not create the missing
investigation difficulty.
