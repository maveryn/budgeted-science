# Scientific claim verification: CPU commissioning results

Completed September 11, 2026. **No LLM or API evaluation was performed.**
This milestone verifies numerical construction, audit-tool contracts, scoring,
and scripted logging. It does not report agent performance.

## Implemented task

An auditor receives a completed two-population computational study, its solver
metadata, stored trajectory, analysis record, and a quantitative claim:
the maximum of species A over [0,8] is the reported value, accurate within 5%.
This is solution verification for a specified mathematical model, not physical
validation, parameter inference, or code repair.

The private dynamics reuse the planning toy's unchanged RHS:
`x' = theta1*x - theta2*x*y - 0.01*x*x` and
`y' = 0.9*theta2*x*y - theta3*y`, with initial state (10,5).
There is no measurement noise. Six development systems use seeds 7100-7105 and
the existing v2 parameter bounds. They were inspected during planning and are
not held-out test systems.

Each system has one sound study, harmless and consequential integration
variants, and harmless and consequential output-sampling variants. All 30
studies were admitted without changing systems or widening the error bands.
There are **18 within-tolerance and 12 outside-tolerance claims**.

The three report formats (research report, notebook, memo) each occur ten
times, with two instances of each numerical category per format. Every public
study has four artifact roles. Configuration, trajectory, analysis, and claim
are generated coherently from executed calculations; final answers are not
manually perturbed. The literal claim uses ten significant digits and is the
value scored.

## Reference and numerical commissioning

Sound studies use DOP853 at relative/absolute tolerances 1e-9/1e-11 with output
spacing 0.01. Integration variants use Euler steps 0.005, 0.01, 0.02, 0.04, 0.08,
0.16, or 0.32. Sampling variants retain accurate integration and use spacings
0.1, 0.25, 0.5, 1, 2, or 4 at four phase offsets. Endpoints are always included.
The full 32-configuration sweep per system is saved, including unselected
and borderline configurations.

Selection uses errors in [0.5%,4%) nearest 2% for harmless variants, errors
above 6% nearest 10% for consequential variants, and below 0.1% for sound
controls. Ties use configuration order. Incomplete, nonfinite, or
negative-population computations cannot be admitted.

DOP853 and independent Radau references both use 1e-11/1e-13. Peak extraction
brackets derivative zeros, refines roots, checks endpoints, and repeats with
4,097 and 8,193 search points. The required cross-method/search relative
agreement is below 1e-7; the largest observed disagreement over the six systems
was **8.6810e-12**. This is an independently checked numerical reference, not
a certified exact solution.

The separately documented debug configuration (1,0.08,1.4) has peak
**33.81031969392815**, near time 2.76758027. Its reference relative disagreement
was 1.2511e-12.

| Study category | Studies | Original relative-error range (%) |
|---|---:|---:|
| Sound | 6 | 0.000191-0.000730 |
| Harmless integration degradation | 6 | 1.370371-2.172815 |
| Consequential integration degradation | 6 | 6.450388-12.956404 |
| Harmless sampling degradation | 6 | 0.964418-2.579682 |
| Consequential sampling degradation | 6 | 7.970778-12.281489 |

## Audit actions and measured effects

The episode has **5 audit credits**. Integration refinement costs 3, switches
to DOP853 at 1e-10/1e-12, and preserves stored output times. Sampling refinement
costs 2, preserves integration settings, and outputs every 0.0025. It reruns
the same integrator and evaluates its interpolant; it does not reconstruct
missing peaks from sparse published samples.

Both checks can be chained. Existing-artifact inspection, peak recomputation,
comparisons, budget queries, and submission are free. There is no direct
reference query, physical observation, candidate-parameter simulation, or fit.
Repeated purchased configurations are free; cross-episode backend caching
does not remove scientific charges. Executed failures are charged and cached.
Submission is permitted before spending all credits, without a savings bonus.

All **90 check configurations** completed: integration-only, sampling-only, and
combined checks on each of the 30 studies.

| Original study category | Integration-only result within 5% | Sampling-only result within 5% | Combined result within 5% |
|---|---:|---:|---:|
| Sound | 6/6 | 6/6 | 6/6 |
| Harmless integration | 6/6 | 6/6 | 6/6 |
| Consequential integration | 6/6 | 0/6 | 6/6 |
| Harmless sampling | 6/6 | 6/6 | 6/6 |
| Consequential sampling | 0/6 | 6/6 | 6/6 |

These are **numerical results of purchased checks, not agent verdict scores**.
The largest combined-check relative error was 0.000019843% (approximately
1.9843e-7 as a fraction). Sampling-only leaves integration failures at up to
12.9564% error; integration-only leaves sampling failures at up to 12.2815%.
This establishes that the two checks address different numerical mechanisms.

Because both checks fit the default budget, a workflow can always buy both.
The result therefore does not establish a need for adaptive selection.
Differences between runs are not automatically error bounds. The original
reported claim remains the scoring target even after better calculations
have been obtained.

## Verdict and explanation contracts

ACCEPT is correct when the original literal reported value is within 5% of
the reference; REJECT is correct otherwise. ABSTAIN is a completed submission
but not a correct binary answer. Report correctness over all episodes,
coverage, false acceptance among invalid claims, false rejection among valid
claims, abstentions, incomplete outcomes, and expenditure separately.

No LLM judge or explanation-quality score is present. Submitted evidence IDs
must refer to available artifacts or runs. Optional explicit citations of the
form `run-ID Q=number` can be checked mechanically against stored peaks.
Other text is retained but not semantically graded; this does not establish
evidential sufficiency or diagnostic correctness.

## Logged offline fixtures

The answers below are predetermined software fixtures, **not a classical
general verifier or model performance experiment**.

| Fixture | Termination | Credits | Contract outcome |
|---|---|---:|---|
| ACCEPT on a sound study | Submitted | 5 | Correct binary verdict |
| REJECT on an integration-failure study | Submitted | 5 | Correct binary verdict |
| ABSTAIN | Submitted | 0 | Abstention; not counted correct |
| Interrupted after integration purchase | Aborted | 3 | Incomplete, charge and partial trace retained |

Complete local transcripts:

- [ACCEPT fixture](../demos/claim_verification/runs/20260911T222714Z-scripted-9cbd6da220/transcript.md)
- [REJECT fixture](../demos/claim_verification/runs/20260911T222715Z-scripted-6412ea110c/transcript.md)
- [ABSTAIN fixture](../demos/claim_verification/runs/20260911T222716Z-scripted-9b185a290e/transcript.md)
- [Interrupted fixture](../demos/claim_verification/runs/20260911T222717Z-scripted-bb31213f8d/transcript.md)
- [Machine-readable fixture summary](../demos/claim_verification/runs/20260911T222717Z-fixture-summary-80cf60f44e/fixtures.json)

The runner records frozen prompts/scripts, exact messages and tool results,
underlying numerical artifacts, charges, cache events, and private evaluation.
It deduplicates call IDs and enforces 30 tool requests and a five-minute
deadline. Offline regeneration requires no solver or model execution.
Live execution and crash-resume are intentionally absent.

## Verification and reproduction

**350 tests passed: 336 root tests, including 56 new verification tests,
plus 14 preserved planning-pilot tests.** Coverage includes numerical
references, report consistency, format balance, hidden-state separation,
correct and incorrect checks, both chaining orders, charging/cache semantics,
original-claim scoring, malformed submissions, interrupted execution, synthetic
secret redaction, no-SDK imports, and byte-identical offline regeneration.

Software: Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1. The scientific source
manifest SHA-256 is
`b9b1d0be56f66c98155a134ee48ebcea60dcd1cabbf63851c9ac7cb3fac78ecb`.
The existing implementation was clean at 75109f3 before this separate milestone.
Per-file source hashes are retained in the linked manifest.

- [Complete 30-study catalog table and 90 check-effect rows](../demos/claim_verification/data/20260911T222704Z-catalog-791b1692dd/report.md)
- [Frozen numerical/source manifest](../demos/claim_verification/data/20260911T222704Z-catalog-791b1692dd/manifest.json)
- [Catalog integrity hashes](../demos/claim_verification/data/20260911T222704Z-catalog-791b1692dd/catalog_integrity.json)
- [Commands and full public-tool contract](../demos/claim_verification/README.md)

These local raw-data links require this workspace. Fresh checkouts can regenerate
the catalog and fixtures using the documented commands. Generated runs and
private study records remain ignored; the code and this curated report are
checkpointed. Earlier commissioning directories are preserved rather than
overwritten.

## Interpretation limits

This is one fixed peak-accuracy claim family with six related physical systems,
not 30 independent systems or genuinely arbitrary scientific reports.
Template variation preserves facts but does not establish robust document
understanding. Metadata shortcuts may remain. The references and error margins
make an objective verdict target possible; they do not certify an agent's
confidence or explanation.

Prices are an explicit toy resource model, not laboratory costs or measured
runtime. The permissive five-credit budget, free inspection, and predetermined
fixture answers preclude claims about efficient stopping, agent superiority,
or adaptive allocation. No general classical verifier is required. More
diverse claims and report structures, stronger agent controls, and actual
model evaluation remain separate future work.
