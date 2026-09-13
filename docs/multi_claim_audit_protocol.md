# Predator-prey multi-claim audit: small demonstration

## Purpose

Count how many claims an investigator correctly accepts or rejects under a
shared budget. Several claims may share one purchased trajectory. The toy
does not require adaptation to beat a fixed strategy, or prevent one accurate
solve from settling several claims.

One short report contains six related claims from one exploratory system,
not six independent test cases. A simple classical control and one Luna/high
episode receive identical artifacts, tools, prices, and noisy observations.

## Environment reused from resource planning

The existing v2 implementation is unchanged:

\[
x'=\theta_1x-\theta_2xy-0.01x^2,\qquad
y'=0.9\theta_2xy-\theta_3y.
\]

- Initial state `(10,5)`, horizon `[0,8]`, output grid `0.5,1,...,8`.
- Parameter bounds `[0.6,1.4]`, `[0.04,0.12]`, `[0.8,2.0]`.
- Low fidelity: Euler, step 0.1, linear interpolation.
- High fidelity: DOP853, `rtol=1e-10`, `atol=1e-12`.
- Target: high-fidelity member of the same model family. No structural
  discrepancy; low fidelity is not a trained surrogate.
- Target seed 6000, noise replicate 0 / noise seed 60000, reused from the earlier
  exploratory planning comparison. Identifiers, true parameters, equations,
  and reference trajectories remain harness-side, as in the prior restricted
  planning interface. There is no screening or replacement of targets.
- Independent additive Gaussian observation noise has standard deviation 0.1
  for x and 0.05 for y: 1% of initial populations, **not** of the current value.
  Exact initial conditions and noisy x(1),y(1) are free evidence.

## Study and claims

Generate an actual Euler trajectory at report parameters `(1.0,0.08,1.4)`.
Give both investigators its short report, six structured claim records, full
16-time output table, numerical settings, and initial target evidence. The
report parameters are a proposed model, not an assertion of target parameters.
Printed values are rounded to ten significant digits.

| Claim | Quantity | Accuracy referent |
|---|---|---|
| C1 | x(0.5) | Accurate model solution at report parameters |
| C2 | y(0.5) | Same |
| C3 | x(6) | Same |
| C4 | y(6) | Same |
| C5 | x(4) | Noise-free fixed target |
| C6 | y(6) | Noise-free fixed target |

Each claim asserts at most 5% relative error. C4 and C6 concern the same printed
number but different referents. Labels are calculated, not assigned by defect
name. Early/late outputs were chosen as an illustrative development report
before the model run. This is not a held-out evaluation.

Private references use tighter DOP853 and independent Radau integrations
(`rtol=1e-11`, `atol=1e-13`). Maximum disagreement must be below `1e-7` on the
working grid; the paid high service must agree within `1e-6`. These are checked
numerical references, not mathematical certificates. Target labels use
noise-free reference values, not the noisy purchased readings.

## Tools and matching

| Action | Credits | Result |
|---|---:|---|
| `simulate_low(theta)` | 1, new trajectory | Both populations, all working times |
| `simulate_high(theta)` | 8, new trajectory | Both populations, all working times |
| `measure_target(variable,time)` | 12, new scalar location | Fixed target, known noise |
| `evidence`, `get_status`, `compare_cached_candidates` | 0 | Existing evidence and numerical comparisons |
| `submit` | 0 | Six ACCEPT/REJECT/ABSTAIN verdicts and explanation |

Independent **32-credit** ledgers. Existing artifacts, the original low
trajectory, and exact purchased repeats are free. Re-requesting a target
location retrieves the same noisy reading, not an independent replicate.
Valid executed failures retain their charge; invalid/unaffordable requests do
not execute or charge. Credits are declared resource prices, not runtime or
currency. No tool returns a private reference, true error, or verdict.

The fixed CPU control purchases one high trajectory at the report parameters
and target x(4),y(6): **8+12+12=32 credits**. It compares printed values against
this evidence using the 5% criterion. No hidden reference, free solver, or
optimizer informs its decisions. Measurements are plug-in estimates, not
certified bounds. Missing/failed evidence leads to abstention. This is a
structured-claim control, not a general natural-language verifier.

Luna starts with all 32 credits and chooses its own purchases. There is no
prescribed acquisition sequence. It may reuse evidence, choose other
parameters/measurement times, or abstain. Unlike planning, its output is a set
of verdicts rather than a parameter estimate, it does not need the fitting
helper, and there is no full-budget submission requirement. Science settings
and prices are otherwise preserved. There is no arbitrary-code execution.

## Evaluation, logging, and limits

Report correct verdicts out of six, wrong verdicts, false acceptances/rejections,
coverage, abstentions/incomplete claims, credits and purchase traces. Abstention
is completed but not a correct binary verdict. No spending penalty, stopping
bonus, confidence score, or automated semantic grading. Evidence IDs are
checked mechanically; that does not establish sound reasoning.

One `gpt-5.6-luna` episode, high reasoning, $1 API ceiling, 30 responses,
32,768 output tokens/response, 60 tool requests, 20-minute deadline. Standard
Responses streaming, `store=false`, reasoning summaries/encrypted replay,
no automatic retries. Conservative reservations: $0.25/M input, $1.20/M
output (reasoning included). Settings and prices checked against the
[official Luna documentation](https://developers.openai.com/api/docs/models/gpt-5.6-luna).

Freeze study, sources, prompts, schemas, and comparison before live execution.
Keep every API-visible request, response, event, tool output, budget update,
numerical artifact and returned reasoning summary. Raw internal reasoning is
not exposed. Credentials and raw runs stay local and ignored. Offline report
regeneration executes no solver/tool/API calls. No automatic crash-resume.

## Interpretation

One high solve can resolve all four numerical claims; two target measurements
also fit the budget. That is intentional. A successful run demonstrates the
audit mechanics, not benchmark hardness, an allocation advantage, or reliable
uncertainty estimates. Six correlated claims do not establish performance
across six systems. Target checking is synthetic validation-like checking,
not validation against physical experiments. Earlier prototypes are unchanged.
