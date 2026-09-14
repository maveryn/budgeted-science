# Adaptive multifidelity design: five-case planning comparison

The new CPU policy passed **3/5 systems**, compared with **1/5** for the saved
local-fitting baseline and **0/5** for the saved adaptive-GP baseline. It matched
Sol's pass count, but not Sol's mean error. A large failure on system 6021
remains. These results support using it as an additional numerical comparison;
they do not establish general superiority or optimal allocation.

Only the main predator–prey parameter-estimation task was evaluated. No LLM
episodes were rerun, credentials read, verification tasks changed, or proposal
documents edited.

## Unchanged task and matching

The equations, public parameter bounds, initial state, horizon, noisy evidence,
measurement menu, numerical solvers, and scoring are unchanged from the v2
planning pilot. The budget is 32 credits: low-fidelity trajectory 1,
high-fidelity trajectory 8, and additional scalar target measurement 12.
Success requires all three parameters within 5% of their hidden values.
Local statistical analysis is scientifically uncharged, as for the existing
numerical fitting helpers; runtime is recorded separately.

The five reused systems have seeds 6000, 6020, 6021, 6022, 6023, with noise
replicate 0 and noise seed ten times the target seed. The private harness
checks the generated targets against the saved comparison and checks the free
noisy observations against the actual saved Sol episode. Policies receive none
of these case identifiers, target parameters, or reference data.

Policy seed is 0. Settings were frozen after checks on development systems
5000–5007, before running these five comparison episodes. The final development
version passed 2/8; its results are retained. These are reused pilot systems,
not fresh held-out evaluation. No configuration was retuned after the five-case
run.

## Implemented algorithm

The policy is named adaptive_multifidelity_design. Its implementation is a
**frozen-Jacobian local covariance-reduction proxy**, not MR-SUR, a reproduction
of an optimal design algorithm, or a calibrated posterior-confidence procedure.

1. Fit a joint low-plus-discrepancy GP to successful purchased trajectories.
   Normalize parameters to the public unit box. Model
   log(population / initial_population) / time; invert this transform when
   interpreting predictions. The low kernel combines Matérn-5/2 and linear
   covariance terms; an independent smooth discrepancy kernel relates high
   and low responses. Kernel settings are fixed and logged, not learned from
   private trajectories.
2. Continuously optimize the approximate observation likelihood with six
   bounded multistart fits. GP approximation uncertainty and the public
   measurement noise enter the likelihood. Final submission is its best
   continuous estimate, not a random particle or an unpaid exact simulation.
3. Construct finite-difference sensitivities of this learned approximation
   and a local unit-parameter covariance C = (12 I + J^T R^-1 J)^-1.
   Nearby uncertainty directions and distinct fitted modes supply
   likelihood-weighted design locations. Numerically duplicate optimizer
   solutions do not get extra weight.
4. Score affordable actions after every acquisition. A measurement is valued
   by its estimated Fisher/covariance reduction in poorly constrained
   directions. A simulation is valued by the reduction in local parameter
   covariance when conditioning the forward GP on that candidate trajectory,
   holding sensitivities and predicted means fixed. Both use the actual
   action price as divisor. Candidates include global Sobol points,
   plausible local points, and previously purchased parameter locations at
   the other fidelity.
5. Buy the highest-scoring action, update using its actual result, and repeat.
   Before four affinely independent successful simulations support a local
   fit, use integrated forward-variance reduction under the public prior as
   a bootstrap criterion. Measurements receive zero bootstrap value.
   Continue until no new action is affordable; all five runs spent 32 credits.

The acquisition schedule is not precomputed. Nevertheless, **all five runs
ended with 12 low simulations, one high simulation, and one target measurement**.
The acquisition order and locations differed. This result does not demonstrate
adaptation of total resource-type counts; it demonstrates data-dependent
placement and timing under the shared cap.

## Five individual results

Parameter tuples and error tuples are ordered (theta1, theta2, theta3).
Errors below are relative percentages, not tolerance-normalized errors.
The full-precision submitted values and scores are in the machine-readable run.

| System | Submitted parameters | Per-parameter errors | Largest error | All within 5%? | Seconds |
|---:|---|---|---:|:---:|---:|
| 6000 | (1.074124, 0.1142182, 1.337922) | (1.8397%, 3.6939%, 2.6608%) | 3.6939% | Yes | 1.49 |
| 6020 | (0.942308, 0.0680010, 1.648455) | (0.6462%, 0.0282%, 2.4098%) | 2.4098% | Yes | 2.05 |
| 6021 | (0.881444, 0.0936527, 1.540850) | (17.8638%, 72.9165%, 37.7992%) | 72.9165% | No | 1.79 |
| 6022 | (1.180146, 0.1067856, 0.995331) | (3.2214%, 7.0155%, 10.6029%) | 10.6029% | No | 1.41 |
| 6023 | (0.950180, 0.1107542, 0.844259) | (0.4403%, 0.0611%, 0.8123%) | 0.8123% | Yes | 1.43 |

Each row used **12 / 1 / 1 purchases and 32 credits**. There were no incomplete
episodes or failed purchases. Total: 70 purchases, 160 scientific credits,
8.16 seconds of recorded episode runtime, and **$0 API expenditure**.

### Saved-method comparison

| Method | Successes / five | Median largest error | Mean largest error |
|---|---:|---:|---:|
| Adaptive multifidelity design (new) | 3/5 | 3.6939% | 18.0871% |
| Local fitting (saved) | 1/5 | 5.9961% | 21.6541% |
| Adaptive GP (saved) | 0/5 | 17.5129% | 26.2857% |
| GPT-5.6 Sol, high (saved) | 3/5 | 3.0347% | 5.3288% |
| GPT-5.6 Terra, high (saved) | 2/5 | 20.9225% | 19.4282% |
| GPT-5.6 Luna, high (saved) | 0/5 | 17.6567% | 25.7649% |

All methods have five valid submissions in this comparison. The new method
turns local-fitting failures on 6020 and 6023 into passes. It still fails on
6021 and 6022. Its worst-case error is substantial, and Sol's lower mean error
should not be obscured by the equal pass count.

This comparison changes the estimator as well as the acquisition rule.
Differences cannot be attributed to acquisition quality alone.

## Complete acquisition records

The following files contain every purchased action, its location, charge,
remaining credits, and chosen acquisition score. Adjacent events.jsonl
files retain **all candidate scores**, fits, exact tool responses, and links
to complete purchased trajectories. The private evaluation occurs only after
submission.

| System | Paid measurement | Purchase number | High-fidelity purchase number | Full trace |
|---:|---|---:|---:|---|
| 6000 | y(5.5) | 6 | 10 | [14 actions](../demos/planning/runs/adaptive_multifidelity_design/20260914T030431Z-pilot-c80fc4e963/episodes/20260914T030431Z-6000-e1a1e87c19/trace.md) |
| 6020 | y(3.5) | 7 | 11 | [14 actions](../demos/planning/runs/adaptive_multifidelity_design/20260914T030431Z-pilot-c80fc4e963/episodes/20260914T030432Z-6020-3c7b08bfb6/trace.md) |
| 6021 | y(5.0) | 6 | 9 | [14 actions](../demos/planning/runs/adaptive_multifidelity_design/20260914T030431Z-pilot-c80fc4e963/episodes/20260914T030434Z-6021-b8d928341d/trace.md) |
| 6022 | y(5.5) | 7 | 8 | [14 actions](../demos/planning/runs/adaptive_multifidelity_design/20260914T030431Z-pilot-c80fc4e963/episodes/20260914T030436Z-6022-72d5523df6/trace.md) |
| 6023 | y(5.5) | 7 | 9 | [14 actions](../demos/planning/runs/adaptive_multifidelity_design/20260914T030431Z-pilot-c80fc4e963/episodes/20260914T030438Z-6023-880c053602/trace.md) |

These raw runs remain local and ignored by Git. The trace links are therefore
local provenance links, not artifacts included in a clone of this repository.

## Validation, reproduction, and limitations

The 18 new offline tests cover direct GP conditioning, full-trajectory
transformation, hypothetical conditioning against an augmented GP, Fisher
rank-one updates, covariance positivity, mode deduplication, affordability,
duplicate exclusion, changed-evidence responses, deterministic replay,
charging, timeout handling, and offline regeneration.

The policy module imports no environment, solver, evaluator, filesystem, or
API functionality. Instrumented tests prevent solver execution outside
metered calls and prevent any private-evaluator access during the policy.
Separate tests block all physical calls during fitting and acquisition scoring.
Runtime audits confirmed all 70 purchases, all five 32-credit ledgers, exact
initial-observation matching, unchanged frozen source hashes, and an unchanged
saved comparison artifact.

The existing 914-test shared suite had one skipped test and one source-freeze
guard interruption caused by adding a test file during that run. Rerunning
the affected 13-test module with the code held fixed passed. The 14 original
planning-pilot tests also passed. No unrelated implementation was changed.

Software: Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1.

~~~powershell
python -m unittest discover -s tests -p test_adaptive_multifidelity_design.py
python -m budgeted_science.resource_planning.adaptive_design_pilot development
python -m budgeted_science.resource_planning.adaptive_design_pilot pilot --freeze <DEVELOPMENT_DIR>
python -m budgeted_science.resource_planning.adaptive_design_pilot render --run <PILOT_DIR>
~~~

Development freeze:
demos/planning/runs/adaptive_multifidelity_design/20260914T030337Z-development-038ce708cb/.
Five-case run:
demos/planning/runs/adaptive_multifidelity_design/20260914T030431Z-pilot-c80fc4e963/.
The manifest records source hashes and frozen settings before evaluation;
offline rendering neither executes tools nor reruns numerical experiments.

SHA-256:

- Policy: bd4853332b31b6dc2d874cf735a78821ec13c7be888c4dbcf4fdc032359e2617.
- Harness: 1b6fb600b57e0b57f6affad281d7e7621d315ca8e58e703cd51668a2e33f79af.
- Saved Terra-extension comparison:
  ce634654f8f8c0fcf215ff53815210c4859617c6860ea38077f7df11f1a75f41.

Important shortcuts:

- Fixed GP priors, independent output channels, first-order transformed noise,
  local covariance, limited multistart search, and frozen-mean/Jacobian action
  updates are approximations. They can miss competing parameter explanations
  and misjudge nonlinear or spatially varying model discrepancy.
- The greedy gain-per-credit rule does not explicitly reserve resources for a
  later expensive action. In these runs, affordable choices eventually reduced
  to cheap simulations. No claim of globally optimal allocation is made.
- Nonpositive noisy observations cause an explicit incomplete outcome in this
  log-response policy; they are not silently clipped. Successful simulations
  with nonpositive output are excluded from this fit without refunding their
  cost. This is a policy limitation, not a change to the environment.
- The five reused systems are too few to support statistical superiority,
  and the poorer 2/8 development result is a warning against generalization.
  Nothing here establishes calibrated confidence, efficient stopping, or
  unexpected execution-cost adaptation.
