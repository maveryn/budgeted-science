# Mixed-claim predator-prey study: frozen 32-credit protocol

One development study with six heterogeneous claims and shared evidence.
This version is separate from the earlier six point-value claims. It reuses
the planning environment, target seed 6000, noise seed 60000, parameter
bounds, initial state (10,5), horizon 8 and half-unit output grid. Prior
studies and results are unchanged. This is a commissioning example, not a
held-out test or proof of an adaptive-planning advantage.

## Claims and definitions

Baseline parameters: (1, 0.08, 1.4). Intervention: (1, 0.088, 1.4), changing
only predation by +10%. Euler uses dt=0.1. All printed estimates are derived
from actually executed Euler pipelines and rounded to ten significant digits.
The target-recovery assertion uses a fixed 20% threshold, not a claimed output
of the baseline model. Report parameters are not asserted to match the target.

The six types are shuffled once with seed 731 and then assigned C1-C6 in
presentation order. Report, structured claim list and schema ID order agree;
all methods receive the same order. No label or resource-dependency table is
provided to the agent.

| ID | Assertion | Criterion |
|---|---|---|
| C1 | Reported baseline x(4) predicts the fixed target's x(4) | Relative error at most 5% |
| C2 | Reported baseline x(0.5) is numerically accurate | Relative error at most 5% |
| C3 | Reported cumulative prey index is numerically accurate | Relative error at most 5% |
| C4 | +10% predation reduces grid-sampled peak prey by at least 14% | Reduction fraction at least 0.14 |
| C5 | Reported predator/prey ratio at t=6 matches the target | Relative error at most 10% |
| C6 | Target prey recovers by at least 20% from t=4 to t=6 | x(6)/x(4)-1 at least 0.20 |

Cumulative prey is **trapezoidal integration on 0,0.5,...,8**, not a claim
about the exact continuous-time integral. Peaks are maxima on that same
grid, not continuous-time maxima. Both include the known initial state.
Intervention reduction is (baseline peak - intervention peak)/baseline peak.
The 14% lower bound is the actual Euler reduction percentage rounded down
to a whole percentage point; it is generated without consulting its label.
CPU commissioning found about 14.6% using Euler and 11.7% using accurate
integration. No threshold is retuned after the agent run.

## Evidence, tools and costs

The full original baseline Euler table is supplied free, as is a summary of
the intervention Euler calculation (peaks and percentage effect). The full
intervention trajectory is not supplied; acquiring it costs the same as any
other new full-trajectory simulation. Full original numerical artifacts are
retained privately for provenance. Free noisy target x(1),y(1) and known
initial conditions are unchanged from planning.

- New low-fidelity trajectory: **1 credit**.
- New high-fidelity trajectory: **8 credits**.
- New target scalar measurement: **12 credits**.
- Evidence/status/cached comparisons, exact purchased repeats and submission:
  **free**. The supplied baseline low trajectory is also free to retrieve.

Simulations return both populations at all 16 output times. Measurements have
independent additive Gaussian noise, standard deviation 0.1 for x or 0.05 for
y. Repeating a location retrieves its existing value, not another noisy trial.
No tool reveals hidden parameters, equations, labels or reference quantities.
Invalid/unaffordable requests are uncharged; executed failures retain charges.
No Python execution, fitting helper, additional acquisition service or new
measurement replicate action is introduced.

Shared evidence includes a baseline simulation for C2/C3 and the baseline part
of C4, target x(4) for C1/C6, and target x(6) for C6/C5. This mapping is design
documentation only; the model must work out useful reuse from the study.

## Classical baseline and CPU diagnostic

Use one simple fixed, presentation-order-independent policy. It requests:

1. High simulation at baseline parameters (8).
2. Target x(4) (12).
3. Target x(6) (12).
4. High simulation at intervention parameters (8), if affordable.
5. Target y(6) (12), if affordable.

At **32 credits**, the first three purchases exhaust the allowance. The last
two are refused without execution or charge. The baseline computes C1/C2/C3/C6
from purchased evidence and abstains on C4/C5. Arithmetic uses the same claim
definitions as the evaluator, but no private reference or unpaid simulation.
It treats measurements as plug-in estimates, not certified noise-free values.
It is not an optimal allocation policy or a general free-text verifier.

At **52 credits**, the same policy buys all five resources. This is a
CPU-only complete-evidence diagnostic, not a matched competitor to the
32-credit agent. Having all these observations does not generally guarantee
correct verdicts because observations remain noisy.

## Scoring and model run

Each claim is independently labelled using its specified criterion and an
accurately computed, noise-free reference. Reference trajectories use tighter
DOP853 checked against Radau; maximum grid disagreement must be below 1e-7.
The paid high solver must agree within 1e-6. These are independently checked
numerical references, not mathematical certificates or physical validation.

Return ACCEPT/REJECT/ABSTAIN for all six IDs. Report correct out of six,
wrong, abstained, coverage, false acceptances/rejections and credits spent.
Abstention is completed but is not a correct binary verdict. No spending
penalty, full-budget rule, early-stopping bonus or confidence score. Preserve
numerical explanations without an LLM judge. Correct labels need not imply
correct explanation or adequate evidence; inspect concrete contradictions
separately without changing the frozen score.

Exactly one authorized **gpt-5.6-luna/high** episode at **32 credits**, with
the previous **$1 API ceiling**, 30 responses, 32,768 output tokens/response,
60 function requests and 20-minute deadline. Responses streaming, store=false,
standard service tier, reasoning summaries/encrypted replay, sequential tools,
conservative token reservations and no automatic retries are unchanged.
Reservations use up to $0.25/M input and $1.20/M output, verified against
[official pricing](https://developers.openai.com/api/docs/pricing) and
[Luna settings](https://developers.openai.com/api/docs/models/gpt-5.6-luna).

Freeze configuration, study, prompts, schemas, sources and baseline before
live execution. Keep all available requests, responses, stream events,
tool activity, observations, complete numerical artifacts and evaluations
in unique ignored directories. API-visible reasoning summaries are retained;
raw internal reasoning is not available. Credentials are opened only by the
live runner and never logged or committed. Offline report regeneration does
not run solvers or make API calls. A second live launch from one preparation
is refused; this milestone has no automatic retry or live crash-resume.
