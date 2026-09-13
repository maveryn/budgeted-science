# Three target-dependent claims: development protocol

This separate variant preserves the six-claim catalogs, runners, results and
proposal documents. It reuses the six frozen predator-prey worlds from
`paired-claim-followup-v2`, with three claims per study, all about the unknown
fixed target. No specified-model numerical-accuracy or intervention claims remain.

## Science and report construction

The unchanged dynamics are

\[
x'=\theta_1 x-\theta_2xy-0.01x^2,\qquad
y'=0.9\theta_2xy-\theta_3y.
\]

Initial populations are (10,5), horizon [0,8], parameter bounds
[0.6,1.4], [0.04,0.12], [0.8,2.0]. The agent sees the family, bounds, initial
state and numerical settings, not the equations or hidden parameter vector.
Existing private targets, independent numerical references, observation seeds
and noise are unchanged. Each pair has identical free early evidence and report.

Every study has these three claim types in a deterministic shuffled order:

1. Every reported parameter estimate is within 5% of its true target value:
   `max(abs(reported_theta-target_theta)/abs(target_theta)) <= 0.05`.
2. Target trapezoidal prey abundance on 0,0.5,...,8 exceeds the existing threshold.
3. Target late recovery `x(8)/x(6)-1` exceeds the existing threshold.

The integral/recovery thresholds remain 126/0.05, 142/0.05 and 130/-0.40 across
the three pairs. They are inherited development choices, not new held-out
scientific requirements. All six worlds remain; no label or performance gate
selects or replaces cases. Reference quantities are not exposed to investigators.

The new report estimate is **actually fitted** to free noisy x(1),y(1), using
bounded least squares and high-fidelity early predictions with theta2 fixed
at 0.08. This author restriction and every evaluated parameter/early prediction
are disclosed. The author then runs Euler at the fitted estimate to produce the
published original trajectory. Its parameter-accuracy assertion is not a
uniqueness or confidence certificate; two early observations do not identify
three unconstrained parameters. The author has no access to private target
parameters through the fitting function. Author computations are pre-existing
report preparation, not charged audit purchases; only early high predictions,
not full high trajectories, are published.

Unlike the previous variant, **no alternative fit or exhaustive two-candidate
set is supplied**. Neither investigator assumes such a restriction. This changes
report content as well as claims, so a score difference is not an isolated
effect of reducing the number of claims. The six reused worlds are three
engineered development pairs, not an independent random sample.

## Audit resources and score

Each episode starts with all **32 shared scientific credits**. Tools are the
existing seven actions: low/high simulation, scalar target measurement, evidence,
status, cached-candidate comparison and submission. New low/high trajectories
cost **1/8**, and a new target scalar costs **12**. Low is Euler dt=0.1; high is
DOP853 at rtol=1e-10, atol=1e-12 in the same family as the target. No structural
model discrepancy, trained surrogate, Python tool or fitting helper is supplied.

Measurement times are 0.5,1,...,8. Noise standard deviations are 0.1 for x and
0.05 for y. Noisy x(1),y(1), exact initial conditions, the report and original
Euler trajectory are free. Repeated measurements return the same record, not
independent trials. Original low and already purchased simulations are free to
retrieve. All study claims may reuse acquired evidence. Invalid/unaffordable
requests cost nothing; executed failures retain charges.

Utility is **+1 correct / -2 wrong / 0 abstain**, with raw counts, coverage and
costs reported separately. Submit three verdicts; incomplete runs remain
incomplete. There is no spending penalty, full-budget requirement, stopping
bonus, confidence score or LLM judge. Reference labels use true parameters and
the unchanged independently checked numerical target trajectory. These are
synthetic target-accuracy claims, not validation against physical experiments.

## CPU comparison

The planning demo's existing `run_local_policy` and `LocalFit` are reused with
seed 0 and unchanged numerical settings. The policy explores continuous
parameter space, selects one measurement using local sensitivity information,
buys a paired high solve and refines locally. The free report's original low
trajectory is included alongside its own purchases. No alternative-candidate
restriction or hidden target information is used.

At submission, the baseline compares its continuous fitted parameters with the
reported estimate and uses its high-minus-low-corrected local affine trajectory
for the other two quantities. These final predictions are analysis of purchased
data, not unpaid physical simulations. Verdicts are plug-in decisions, not
confidence tests; invalid nonpositive/nonfinite trajectory predictions lead to
abstention. Full fit diagnostics and all purchases are logged. The CPU deadline
is five minutes. No baseline victory or universal recoverability is required.

## Luna execution and safeguards

Six independent episodes, exact `gpt-5.6-luna`, high reasoning, **$1 per episode
and $6 total**, 30 responses, 60 tool requests, 32,768 output tokens per response,
20 minutes. Preserve standard-tier streaming Responses API, store=false,
reasoning summaries and opaque encrypted replay. No automatic retries,
substitutions, cap increases or live crash-resume. Exclusive attempt markers
prevent repeating a prepared campaign; interrupted attempts remain recorded.

Official [model settings](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
and [pricing](https://developers.openai.com/api/docs/pricing#standard-pricing-data)
were checked on 2026-09-13. Reservations use $0.25/M input and $1.20/M output,
including the full output allowance; requests above 256,000 input tokens are
refused. Usage estimates are not invoices. Uncertain requests keep reservations
and halt the campaign. Credentials are read only by explicit live mode and are
never printed or committed.

## Commands and records

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_target_three_claims.py -v
# CPU only: construct reports, run six baseline episodes, freeze prompts/settings.
.venv\Scripts\python.exe -m budgeted_science.agents.target_three_claims prepare
.venv\Scripts\python.exe -m budgeted_science.agents.target_three_claims dry-run <prepared-directory>
# Paid execution requires authorization; never repeat a completed campaign.
.venv\Scripts\python.exe -m budgeted_science.agents.target_three_claims live <prepared-directory>
.venv\Scripts\python.exe -m budgeted_science.agents.target_three_claims render <campaign-directory>
.venv\Scripts\python.exe -m budgeted_science.agents.target_three_claims render-episode <episode-directory>
```

Prepared artifacts:
`demos/paired_claim_audit/runs/20260913T085926Z-target-three-prepared-cdb738cbfa`.
Catalog hash:
`086f913625f20a5c49eac56ad8cdafeec19fa2ef5468fef2d9d8b24fca7f1d8b`.
Source-manifest hash:
`0e5802ebbf82391722cde3392275a514a5ab339de9301c18d0eb124eba417af1`.
The scripted six-episode rehearsal is
`campaigns/20260913T085954Z-dry-run-a7c71ad815`; all-abstain fixture outputs are
not model results and cost zero API dollars.

Frozen prompts/schemas, versions/source hashes, complete API-visible records,
chronological actions, numerical artifacts, private labels and evaluations,
CPU traces and readable transcripts are retained in unique ignored directories.
Offline regeneration makes no API or solver calls. Raw internal reasoning is
not available. Older code and records, credentials and proposal files are not
modified or committed with this variant.
