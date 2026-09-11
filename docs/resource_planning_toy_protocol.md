# Fixed-budget resource-planning toy

This CPU-only planning environment is independent of Burgers. It is a prototype
of allocation between imperfect computation, accurate computation, and target
evidence, not a demonstrated agent benchmark. It neither uses an API key nor
runs an LLM. The existing Burgers and allocation-pilot workflows are unchanged.

## Task and tools

The private harness solves a modified predator-prey system:

```
x' = theta1*x - theta2*x*y - 0.01*x*x
y' = 0.9*theta2*x*y - theta3*y
x(0)=10, y(0)=5, final time=8
```

The public parameter ranges are `[0.8,1.2]`, `[0.06,0.10]`, and `[1.1,1.7]`.
The high-fidelity simulator and target use the same dynamics: this toy has no
simulator-to-target structural discrepancy. Low fidelity is Euler with step
0.1 and linear interpolation. High fidelity is DOP853 with rtol `1e-10`, atol
`1e-12`, and dense output. Target measurements have no added noise.

Only public settings and purchased evidence are passed to a policy. The policy
cannot call the RHS, hidden target, or evaluator through its facade. This is
trusted in-process separation, not security against arbitrary Python code.

| Action | New purchase | Reuse |
|---|---:|---|
| `simulate_low(theta, times)` | 1 credit | Full trajectory at the exact candidate/fidelity is purchased; additional times are free. |
| `simulate_high(theta, times)` | 8 credits | Same full-trajectory reuse rule. |
| `measure_target(variable, time)` | 12 credits per scalar | Exact purchased variable/time is free; it accepts no candidate theta. |
| `get_status`, `evidence`, `compare_cached_candidates` | Free | No new simulation or target evidence is obtained. |
| `submit(theta_hat)` | Free | Terminal, with private subsequent scoring. |

Each episode starts with the known initial state, free `x(1),y(1)`, and a shared
40-credit ledger. Prices are represented scientific resources, not dollars,
measured FLOPs, or runtime. Rejected invalid/unaffordable requests do not run;
executed failures are charged and cached. Purchase histories reset each episode.
Charges are logged before numerical execution to retain interrupted work.

The score is the worst of the three errors `abs(estimate-truth)/(0.1*truth)`.
Success requires all three to be at most one. No saving-credit bonus, confidence
assessment, or cost-accuracy composite score is used. In particular, a component
error above one cannot be compensated by better estimates of other components.

## Baselines and common estimator

Both methods pay 12 credits for four low-fidelity runs (midpoint plus three
scrambled Sobol points) and one high-fidelity midpoint run. This warm start is
a baseline choice, not free evidence or a prescribed future agent workflow.

The random nonadaptive policy predetermines eight further low-fidelity points,
one further high-fidelity point chosen among the non-midpoint low-fidelity
locations, one random unpurchased observation, and the ordering, before reading
target evidence. Its totals are 12 low, 2 high, and 1 paid measurement: 40 credits.
This particular fixed recipe requires the default budget and prices.

Both methods fit the same paid-data-only GP. The two populations are independent
conditional on the target parameters, but a population's temporal outputs are
correlated. Inputs are normalized to the public parameter box; outputs are
divided by the public initial values and centered at one. The model is
`high(theta,t)=low(theta,t)+delta(theta,t)`, with independent low and discrepancy
processes, fixed autoregressive coefficient one, Matérn-5/2 parameter kernels,
and a shared Matérn-5/2 temporal correlation on `t/8` of length 0.25.

Each population has six fitted parameter length scales and two process standard
deviations. Their deterministic starting values are 0.5 for lengths, 1 for the
low process standard deviation, and 0.25 for discrepancy. Bounded marginal
likelihood uses L-BFGS-B, at most 40 iterations, length bounds `[0.05,2]`, and
standard-deviation bounds `[0.001,10]`. Nonconvergence is logged, not hidden.
Run-kernel jitter is `1e-7`; target likelihood regularization is `1e-8` in
normalized-output variance units. These numerical floors are **not physical
measurement noise**, and the resulting posterior is an approximation.

The estimator uses trajectories on `0.5,1,...,8` and 2,048 scrambled Sobol prior
particles, uniform in the public parameter box. It includes emulator covariance
in the likelihood and submits the posterior mean parameters. The environment
itself still permits arbitrary query times. No offline solver-derived model,
hidden parameter, or cross-episode training data is supplied to the estimator.

The adaptive policy is a lightweight adaptation of the expected-uncertainty-
reduction-per-cost principle in [Stroh et al., MR-SUR](https://arxiv.org/abs/2007.13553),
not an exact reproduction of that paper's experiments or an optimal policy.
Its uncertainty statistic is the sum of posterior variances of log parameters.
It compares both fidelities at eight global and eight posterior-weighted
candidate locations, plus unpurchased population/time measurements on its grid.
Only affordable new purchases are compared.

Each action uses eight joint hypothetical outcomes with common random draws.
The same sampled latent target parameters apply to both populations. A simulated
trajectory is sampled conditional on the already purchased target observations;
then the GP is conditioned on that entire hypothetical trajectory and the target
posterior recomputed. A measurement fantasy instead conditions the target at
the proposed variable/time on existing target observations. Hyperparameters
stay fixed during fantasies. Neither operation calls a physical solver.
The selected action maximizes estimated reduction per credit, even when all
estimated gains are nonpositive. There is no uncertainty-based stopping bonus.

## Runs, evaluation, and limits

The debug target is `(1,0.08,1.4)`. Development uses uniform target seeds
1000--1007 and policy seed zero. Evaluation uses target seeds 2000--2019 and
policy seeds 0,1,2: 120 episodes and 60 paired comparisons. A saved development
freeze checks code/test/config hashes and numerical versions before evaluation
targets are generated. Evaluation evidence must not be used to tune policies.

Each episode runs in a fresh supervised process with a 300-second elapsed limit
and one BLAS thread. Local emulator analysis is uncharged scientific analysis;
its runtime remains reported. This toy studies allocation among fixed-price
resources, not unexpected solver runtimes, justified confidence, or efficient
early stopping. It also does not isolate the effects of choosing resource types
from choosing their locations: both are part of the adaptive policy.

Success rates include every planned attempt, including failures and missing
submissions. Error summaries use valid submissions, with their denominator
reported. Paired bootstrap intervals resample whole targets and keep their
three seeds together. Numerical validation uses only debug/development cases;
its unbudgeted rich-data recovery is a privileged diagnostic, not a third baseline.

Use the module entry points `budgeted_science.resource_planning.validate`,
`budgeted_science.resource_planning.experiment`, and
`budgeted_science.resource_planning.reporting`. Exact commands, verified run
locations, outcomes, source hashes, and limitations are recorded in the
[results](resource_planning_toy_results.md). Raw manifests, chronology, full
numerical artifacts, and private evaluation data remain in ignored run folders.
