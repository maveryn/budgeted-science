# Three-stage study verification: CPU pilot and Luna evaluation

Date: 2026-09-12. Status: implementation, CPU evaluation, offline rehearsal and
the explicitly authorized twelve-case live batch are complete. **GPT-5.6 Luna,
high reasoning: 12/12 correct**, matching the full-pipeline CPU control.
All episodes completed without retries, abstention or budget overrun. API cost
bounds for the entire batch: **$0.13437148-$0.34031345**, below the $2 ceiling.
These are usage-based bounds, not an invoice. The earlier blocked launch made
no API calls; this is the first and only live batch for this frozen catalog.

## What changed

The audited object is now an input-processing -> simulation -> output-analysis
study. Each stage has a recorded configuration, and rerunning one stage does
not silently repair another. The underlying simple transport system is reused;
no calibration uncertainty, surrogate, physical validation or LLM judge was added.
The original printed exposure is judged against a continuous mathematical
reference within 3% relative error. Explanations are retained without grading.

There are **12 development claims, from two physical systems**, not twelve
independent scientific problems. Each system has sound, harmless-input,
consequential-input, coarse-numerics, truncated-analysis and harmless-analysis
variants. Six claims are true; six false. Full setup and reproduction commands:
[frozen protocol](study_verification_protocol.md).

## Measured CPU results

Each control makes one affordable approximate solver purchase and uses free
input arithmetic and saved-array integration. Budget: 4 scientific credits.

| Structured control | Correct | Mean credits |
|---|---:|---:|
| Rerun solver only, preserving input/analysis settings | 8/12 | 3.007487 |
| Correct input preparation and rerun solver | 10/12 | 3.007812 |
| Rerun solver and use full analysis window | 10/12 | 3.007487 |
| Full pipeline using intended inputs and full analysis window | 12/12 | 3.007812 |

All 60 CPU episodes (five controls x twelve claims) completed without abstention
or budget overrun. A supplementary seed-0 random *stage-selection* control
happened to choose both corrections, and therefore duplicates the full-pipeline
control exactly (12/12). It is not an additional independent result and does not
constitute a randomized solver-configuration baseline.

Solver-only misses the two input errors and the two analysis errors; adding
only one of these corrections removes the corresponding two mistakes. The
full-pipeline procedure is an executable, non-oracle structured control: it sees
the same public artifacts and obtains all simulations through charged tools.

**Interpretation:** the toy now demonstrates why checking only the final solver
can miss a wrong study result. It still does **not** require adaptive investigation:
one fixed complete workflow succeeds throughout this catalog within budget.
Input conversion and array integration are cheap, so charging artificial fees
for them would manufacture a trade-off absent from this implementation.

## Luna/high: completed matched evaluation

Frozen catalog, order, scientific tools and scoring were unchanged. One episode
per claim, independent histories and purchase ledgers, 4 scientific credits,
30 responses/tool requests maximum, 32,768 output tokens per response including
reasoning and a 20-minute episode deadline. All twelve shared the approved $2
API ceiling. CPU results remained private and were imported without rerunning.

| Measure | Observed result |
|---|---:|
| Correct verdicts | 12/12 |
| Correct acceptance of true claims | 6/6 |
| Correct rejection of false claims | 6/6 |
| Abstentions / incomplete episodes / retries | 0 / 0 / 0 |
| Total / mean scientific credits | 29.697266 / 2.474772 |
| Episodes with no paid simulation | 3 |
| Completed model responses | 161 |
| Input / output tokens | 1,025,417 / 69,966 |
| Reasoning tokens (included in output) | 61,233 |
| Total / mean episode runtime | 936.464 / 78.039 seconds |
| API lower / conservative upper cost | $0.13437148 / $0.34031345 |
| Unknown usage or pending reservations | None |

Every claim family scored 2/2. Individual verdicts and scientific expenditure,
in frozen execution order:

| Case | Family | Verdict | Credits |
|---|---|---|---:|
| study-2330f7df124f | Harmless analysis | ACCEPT | 3.755859 |
| study-5362b7c49a85 | Harmless analysis | ACCEPT | 3.507812 |
| study-d0dfca4b5f4e | Harmless input | ACCEPT | 2.003906 |
| study-9dc337f4445a | Consequential input | REJECT | 3.378906 |
| study-45b35d976af9 | Coarse numerical solve | REJECT | 2.503906 |
| study-f340c9f1623a | Truncated analysis | REJECT | 0 |
| study-e69ac03420a3 | Harmless input | ACCEPT | 0 |
| study-f612bf23ad6f | Truncated analysis | REJECT | 3.511719 |
| study-ae485dce42e0 | Coarse numerical solve | REJECT | 3.761719 |
| study-c21371bd4f6e | Sound | ACCEPT | 0 |
| study-e95351831bf4 | Consequential input | REJECT | 3.511719 |
| study-44dcde47fc06 | Sound | ACCEPT | 3.761719 |

For example, on `study-f340c9f1623a`, Luna read the original analysis window and
reintegrated the saved trajectory over [0,1], rejecting the truncated-window
claim without buying another simulation. Other explanations explicitly used
analytic approximations for the public linear equation. These are qualitative
trace observations, not semantic diagnosis scores or certified confidence.

Luna matched the strongest fixed control, rather than outperforming it. Its
lower average scientific spend is descriptive: saving credits was not a scored
objective and no efficiency or adaptive-allocation advantage is established.
The broader pipeline is functioning, but the catalog remains easy for both a
complete structured workflow and this model. Twelve variants of two systems
cannot establish broad scientific-verification ability.

## Claim errors

Both systems have velocity 0.6 and decay 0.1. System 0 has diffusivity 0.0005;
system 1 has diffusivity 0.003. Their reference exposures are respectively
0.16687323061419293 and 0.1482668850839996.

| Family | System 0 printed exposure | Error | System 1 printed exposure | Error |
|---|---:|---:|---:|---:|
| Sound | 0.1681651052 | 0.7742% | 0.1483605477 | 0.0632% |
| Harmless input | 0.1680943999 | 0.7318% | 0.1486330293 | 0.2469% |
| Consequential input | 0.1406627905 | 15.7068% | 0.1390501343 | 6.2163% |
| Coarse numerical solve | 0.1231355340 | 26.2101% | 0.1185217049 | 20.0619% |
| Truncated analysis | 0.1151765325 | 30.9796% | 0.1027638472 | 30.6900% |
| Harmless analysis | 0.1680234696 | 0.6893% | 0.1481118044 | 0.1046% |

These printed values were produced by the actual recorded pipelines, not edited
afterward. The independent Gaussian-image/Fourier reference checks pass for both
systems. These are deliberately separated development cases: true claims are
below 0.8% error and false claims above 6%, well away from the 3% threshold.
Input artifacts explicitly reveal their normalization and analysis artifacts
their integration window. Semantic metadata shortcuts remain possible, as do
analytic approximations to this elementary equation.

## Records and reproducibility

CPU run:
`demos/claim_verification/runs/20260912T071218Z-study-cpu-331018781a/`

- [Full CPU report](../demos/claim_verification/runs/20260912T071218Z-study-cpu-331018781a/report.md)
- [Frozen manifest and hashes](../demos/claim_verification/runs/20260912T071218Z-study-cpu-331018781a/manifest.json)
- [All generated studies, including PRIVATE references](../demos/claim_verification/runs/20260912T071218Z-study-cpu-331018781a/catalog.json)
- Episode subdirectories retain requests, responses, input/analysis settings,
  original and purchased trajectories, cache events, charges and submissions.

Full twelve-case offline runner rehearsal:
`demos/claim_verification/runs/20260912T071615Z-luna-study-dry-run-1d366069e3/`

- [Offline rehearsal and links to all frozen prompts/transcripts](../demos/claim_verification/runs/20260912T071615Z-luna-study-dry-run-1d366069e3/report.md)
- This fake model always reads the analysis artifact and submits ACCEPT: 6/12
  correct by construction, **not Luna performance**. Actual API expenditure zero.

Software: Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1, OpenAI SDK 2.54.0,
httpx 0.28.1, budgeted-science 0.1.0. Full hashes are in the manifest; principal
scientific sources at freeze:

| File | SHA-256 |
|---|---|
| study_verification/environment.py | `4eef4b47b3ea4aaf02dcb95705750ea1f50fd45d23e093c80ae36c20d402ac32` |
| study_verification/experiment.py | `9599d21fefa8d4426e480f45674805cf2b8376740b33541d6e93156a611eb443` |
| transport_verification/numerics.py (unchanged) | `bdd2426656903e6a1e122b1f4b62184414bf11833fa3b87c42246633b5998d02` |

Verification: **568 tests pass** (554 shared, including 18 new tests; 14
planning-pilot). Coverage includes stage isolation, actual-pipeline values,
unit conversion, quadrature, numerical truth independent of defect category,
abstention, invalid requests, failed-work charging, cache reuse, duplicates,
private prompt isolation, schema validation, streamed-history replay, interrupted
logs/reservations, credential-free dry runs and offline report regeneration.
Earlier numerical/API safeguards remain covered by the unchanged regression suite.

Post-live verification additionally checked all twelve unique case identities,
source/prompt/schema hashes, exact model/high-reasoning settings, all 161 archived
request/response pairs, actual submissions/reference scoring, scientific caps,
and reconciliation of every API reservation. Each episode's transcript, report
and evaluation regenerated byte-identically with solver/API execution blocked;
the batch report also regenerated identically. No implementation changes were
made during this run, and no new paid call was used for verification.

## Completed live scope and records

Recipient: OpenAI Responses API (`https://api.openai.com/v1/responses`, with
input-token counting through the same service). Exact model `gpt-5.6-luna`, high
reasoning. Twelve episodes, four scientific credits each, **$2 total API ceiling**.

Content: these frozen public synthetic transport-study prompts, function schemas,
conversation history, and requested public tool outputs (including synthetic
trajectories and computed coefficients/integrals). No proposal documents, personal
application files, private reference answers, case labels or baseline outcomes
are transmitted. The API key is used only for authentication and is not logged.
No automatic retries, model changes, cap increases or additional batches.

The user explicitly approved this synthetic workflow after reviewing its scope.
Only one live batch was executed:

`demos/claim_verification/runs/20260912T072528Z-luna-study-live-c1eedf3e34/`

- [Complete comparison and links to all twelve transcripts](../demos/claim_verification/runs/20260912T072528Z-luna-study-live-c1eedf3e34/report.md)
- [Machine-readable aggregate](../demos/claim_verification/runs/20260912T072528Z-luna-study-live-c1eedf3e34/summary.json)
- [Frozen batch manifest](../demos/claim_verification/runs/20260912T072528Z-luna-study-live-c1eedf3e34/manifest.json)
- [Zero-simulation truncated-analysis example](../demos/claim_verification/runs/20260912T073211Z-live-f134fb5c68/transcript.md)

Each linked episode contains the full request/response/stream-event archive,
public artifacts, purchased numerical arrays, exact tool results, opaque
encrypted reasoning, available reasoning summaries and private evaluation.
Raw internal reasoning is not exposed. All raw runs remain ignored/local;
credentials and proposal documents were unchanged. Do not interpret a new
`--live` invocation as continuation: it would launch another paid batch and
requires new authorization.
