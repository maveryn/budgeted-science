# Finalized predator-prey demonstrations

This is the portable entry point for the two pilots reported in the proposal.
It does not combine earlier variants into additional samples. No agent was rerun
to prepare this release. Results are from the saved September 2026 experiments,
not claims about current model availability or API prices.

## Scientific setup

Both tasks use

~~~text
x' = theta1*x - theta2*x*y - 0.01*x*x
y' = 0.9*theta2*x*y - theta3*y
~~~

The initial state is (10,5), the horizon is [0,8], and parameter bounds are
[0.6,1.4], [0.04,0.12], and [0.8,2.0]. Low fidelity uses explicit Euler with
step 0.1; high fidelity uses DOP853 with rtol=1e-10, atol=1e-12. The hidden
target uses the high model, not a real physical experiment. This pilot
has numerical error but no structural model-target discrepancy.

Each episode starts with 32 shared credits. A new low/high trajectory costs
1/8 credits; a target scalar observation costs 12. Outputs use the time grid
0.5,1,...,8. Candidate simulations accept the agent's parameter vector; target
observations query one fixed hidden system. Free evidence includes exact initial
conditions and noisy time-1 observations. Independent Gaussian noise has standard
deviations 0.10 (prey) and 0.05 (predator). Repeating a purchased observation
returns the same reading, not a new noise draw. Reusing any purchased trajectory
is free. These tariffs are controlled proxies, not measured time or money.

The equation, private parameters, reference outputs, and noise seed are not sent
to the agent. They are published here for reproducibility, under evaluator-only
fields. This is trusted-process separation, not an arbitrary-code security sandbox.

## Tasks and interfaces

**Planning:** infer three parameters; success means
max_i |theta_hat_i-theta_true_i|/|theta_true_i| <= 0.05.
The continuous metric is this maximum error, reported as mean/median over five
systems, in percent. Valid submission requires all 32 credits to be used.
Tools expose low/high simulation, target measurement, status/evidence retrieval,
cached-candidate comparison, a free GP fitting helper, and submission.
The fitting helper uses only purchased evidence; it is not the new adaptive policy.

**Verification:** a fitted report supplies three shuffled unknown-target claims:
joint parameter accuracy (5%); trapezoidal prey abundance on 0,0.5,...,8;
and recovery x(8)/x(6)-1 against a stated threshold. Abundance is a grid-defined
statistic, not a continuous integral. The author fit fixes theta2=0.08 and
discloses this restriction. The report's original Euler trajectory is free.
An investigator returns ACCEPT, REJECT, or ABSTAIN for every claim. There is no
fitting-helper tool or full-budget submission requirement in this interface.
Private references score verdicts without an LLM judge; explanations are not
semantically graded. Utility is +1 correct, -2 wrong, 0 abstain. The main table
reports raw counts, with abstentions not counted as correct.

| Claim type | True | False |
|---|---:|---:|
| Joint parameter accuracy | 3 | 3 |
| Accumulated prey abundance | 2 | 4 |
| Late recovery | 4 | 2 |
| Total | 9 | 9 |

Always ACCEPT or always REJECT obtains 9/18 at zero additional scientific cost.
A post-hoc majority verdict per claim type obtains 11/18, but is not a
prospectively evaluated policy. Class balance alone does not exclude shortcuts.

Exact recorded messages and schemas are in
[prompts.json](../results/predator_prey/prompts.json) and
[tools.json](../results/predator_prey/tools.json).
These contain task inputs, not raw internal model reasoning or provider logs.

## Shared numerical baseline

The adaptive multifidelity policy fits a low-plus-discrepancy GP using available
trajectories, normalized parameters, and log(population/initial_population)/time
outputs. It uses a bounded multistart approximate likelihood fit, including
measurement noise and GP uncertainty, to estimate continuous parameters.
Local sensitivities of the fitted GP define an approximate parameter covariance.
Affordable measurements and simulations are scored by estimated covariance
reduction per credit, with refitting after each actual acquisition. Before four
affinely independent locations support that fit, it uses forward-variance
reduction as a bootstrap criterion.

This is a greedy fixed-Jacobian approximation, not a reproduction of MR-SUR,
an optimal policy, or calibrated confidence. Planning submits its fitted
parameters. The verification adapter uses those estimates and GP-predicted
trajectories to apply structured claim inequalities, without an unpaid final
physical solve. It is not a general free-form claim verifier.

All evaluated baseline episodes purchased 12 low trajectories, one high
trajectory, and one target measurement. These counts were observed, not
prescribed: their locations and ordering were adaptive. They do not demonstrate
that the policy adapted its total counts across resource classes.

## Results and provenance

The [root table](../README.md#recorded-results) summarizes the same four methods
as the proposal. The machine-readable
[results](../results/predator_prey/results.json) retain every method-case row,
planning estimates/errors, verification verdicts/truth, and purchases.
[Provenance](../results/predator_prey/provenance.json) records source archive hashes,
the export source commit, numerical versions, algorithm settings, and bundle hashes.
Archive paths identify local source records; following them is not necessary to
run the portable demo.

Planning uses seeds 6000 and 6020-6023 with noise replicate 0. The first case
was exploratory; the latter four were selected prospectively for the Sol/Luna
campaign. Terra and the stronger numerical baseline were added later on the same
systems. These are reused pilot systems, not a new held-out benchmark.
Verification uses six existing development worlds forming three related pairs.
Their results are correlated and not six independent random systems.

All models used high reasoning. The planning row for each model has five valid
submissions. Verification has six submitted studies per displayed row, but
Luna's row uses five original completions plus one explicitly authorized retry
of the incomplete fourth study: seven attempts in total. Its original result
was 8 correct, 5 wrong, 2 abstentions, and 3 unsubmitted claims. The retry added
2 correct and 1 wrong. Both views remain documented in
[the retry report](target_three_luna_retry_results.md).

Further detail: [planning](adaptive_multifidelity_design_results.md) and
[verification](adaptive_target_three_results.md). Their raw-run links are local
archive pointers, not files included in a clone.

## Offline reproduction

From a clone, create/activate a virtual environment and install the editable
package. The results command uses only JSON and the Python standard library:

~~~bash
python -m pip install -e .
python -m budgeted_science.demo_release results
python -m budgeted_science.demo_release cpu
# Or reproduce just one task:
python -m budgeted_science.demo_release cpu --task planning
python -m budgeted_science.demo_release cpu --task verification
python -m unittest discover -s tests -p test_demo_release.py
~~~

The CPU command reuses the existing policies and episode implementations directly;
it does not load historical preparations or imported agent comparisons from
ignored folders. Each invocation creates a unique ignored directory under
tmp/released_pilots, with per-episode events, numerical artifacts, and a summary.
It records current numerical versions, has a five-minute limit per episode,
checks spending and recorded outcomes, and exits nonzero if they differ.
Interrupted or differing results are retained; no automatic retry occurs.

The recorded stack is Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1. Other supported
versions may differ numerically. Exact reproduction of these old model responses
is not promised, even if API access remains available.

The bundle deliberately publishes the development cases, including ground truth.
It is unsuitable as an unseen evaluation set. Numerical routines keep evaluator
state out of the agent-facing tool responses; future coding-agent evaluation
requires a genuinely isolated environment.

## Release verification

On 27 September 2026, the shared regression suite completed 952 tests with no
failures and one skip (an optional historical unresumed-run archive was absent).
All 14 planning-pilot tests passed. The shared count includes six new portable
release tests. All 11 CPU baseline episodes matched the recorded outcomes,
resource purchases, and spending on the recorded numerical stack.

The six release tests and all 11 CPU episodes also passed from a fresh staged
source export without historical run archives or credentials, with API SDK
imports and network connections blocked. This verifies offline reproducibility
with the tested dependencies, not portability across every numerical version.
No paid model evaluation was performed for this release.

## Optional live evaluation

Installation, tests, result inspection, and CPU reproduction do not start paid
calls. The OpenAI SDK is optional: install with pip install -e '.[agents]'
only when intentionally using a live runner. Consult the
[planning runner instructions](../demos/planning/README.md) and
[verification protocol](target_three_models_protocol.md) before live use.
Historical campaign commands may require undistributed local preparations;
the portable release does not launch or reconstruct those paid campaigns.
Model access and prices must be rechecked before any new live run.

Do not put API keys in Git. openaiapi.txt, .env files, environments, caches,
and raw run directories stay ignored. Only selected numerical data and frozen
task inputs are distributed. No repository license is selected by this change.

## Development history

Earlier Burgers, allocation, heat, MMS, and verification variants remain intact.
The [historical README](development_history.md) records those iterations
separately. Do not pool their scores with these finalized pilots.
