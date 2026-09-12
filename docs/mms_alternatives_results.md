# MMS verification: original versus expanded tool menus

Executed 12 September 2026: **twelve fresh Luna/high episodes, all completed;
both claims correct on 6/6 studies with each menu**. The extra choices did not
make this toy challenging for Luna. The unchanged study-aware CPU rule also
gets both claims right on all six studies.

## Setup

The [matched-menu protocol](mms_alternatives_protocol.md) preserves the existing
steady 2-D advection-diffusion toy, six development studies, report data, and
two separately scored claims: original point-value accuracy within 2%, and
the audited implementation's relevant finite-grid MMS orders in `[1.7,2.3]`
on grids 8/16/32. It is not physical validation or certified asymptotic order.

Each study received one fresh original-menu and one fresh expanded-menu
episode, alternating menu order between studies. Both had 10 independent
scientific credits, exact model `gpt-5.6-luna`, high reasoning, 32,768 output
tokens per response, 30 responses/tool requests, and five minutes. The entire
batch had a $2 API ceiling. No retries, substitutions, case replacement, limit
increases, or post-result tuning were used. All six pairs had byte-identical
scientific prompts. Common tool schemas were unchanged.

The expanded menu added:

- An affine manufactured-solution test, with exact diagnostic error norms.
- An ILU-GMRES check of the same purchased discrete equations.
- Free Richardson point-value extrapolation with caller-supplied order.

New solves retain the grid-size price `(grid+1)^2/289`, not a measured-work or
runtime price. The two paid checks are valid but insufficient by themselves
for the original claims. Richardson uses purchased results and its stated
error-model assumption. No tool is deliberately broken or returns fake data.

## Results

| Method/menu | Value correct | Order correct | Both correct | Mean credits |
|---|---:|---:|---:|---:|
| Luna/high, original | 6/6 | 6/6 | 6/6 | 8.8206 |
| Luna/high, expanded | 6/6 | 6/6 | 6/6 | 8.5807 |
| Unchanged study-aware CPU rule, either menu | 6/6 | 6/6 | 6/6 | 8.8166 |

No abstentions, incomplete episodes, false acceptances, false rejections,
tool errors, or run errors occurred. All 91 model responses resulted in valid
tool calls. Explanations were preserved, not semantically graded.

Both menus gave the same correct verdict pair in each row:

| Development category | Value | Order | Original credits | Expanded credits | Extra tool used |
|---|---|---|---:|---:|---|
| Sound diffusion | ACCEPT | ACCEPT | 9.8166 | 9.8166 | Richardson |
| Correct mixed-boundary code, coarse study | REJECT | ACCEPT | 6.3287 | 6.3287 | Richardson |
| Upwind advection, coarse study | REJECT | REJECT | 7.3287 | 6.3287 | Richardson |
| First-order Neumann boundary treatment | REJECT | REJECT | 9.8166 | 9.3772 | Richardson |
| Upwind advection, finer study | ACCEPT | REJECT | 9.8166 | 9.8166 | None |
| Inactive upwind change in diffusion | ACCEPT | ACCEPT | 9.8166 | 9.8166 | Richardson |

Luna called Richardson once in five of six expanded episodes. It never called
the affine test or alternative algebraic solver. The added free helper was
used, but the paid alternatives did not divert this sample of investigations.
Small spending differences do not establish that Richardson caused improved
efficiency; each condition has only one sample per study, and saving credits
was not a scored objective. Mean episode time was 58.18 seconds for original
and 45.75 for expanded, including API waiting/logging; these are descriptive
timings, not a latency advantage claim.

## CPU checks

Before live execution, the same study-aware rule was replayed with each menu
on all six studies. Both matched its previously saved correct verdicts.
Separate ten-credit diagnostic traces executed each additional check.

- The largest affine RMS error across these cases and grids 8/16/32 was
  `6.0432e-15`, including schemes that fail the original order claim. Their
  near-exact affine results therefore do not establish second-order accuracy.
- Iterative re-solves of the original studies had scaled algebraic residuals
  at most `1.0443e-14` and absolute point-value differences from the original
  direct solve at most `2.7756e-15`. This confirms same-discrete-system
  agreement, including inaccurate discretizations, not physical correctness.
- Richardson outputs were computed from purchased audited grid-8/grid-16
  values with assumed order 2. Formula, free reuse, compatible-record checks,
  and absence of an unpaid solver call were tested. These estimates were not
  used as private truth or certified bounds.

The original successful CPU route remains intact. Its point-value feasibility
was explicitly commissioned in the earlier toy; 6/6 CPU success is not an
independent generalization finding.

## Accounting and reproducibility

The live batch used **91 responses, 831,377 input tokens across repeated
histories, and 49,840 output tokens including reasoning**. Saved standard
cached/uncached accounting gives a lower estimate of **$0.10136878**;
conservative accounting gives an upper bound of **$0.26765225**. These are
accounting bounds, not an invoice. No uncertain usage or pending reservation
remains; $1.73234775 of the batch allowance was unused.

Local artifacts, ignored by Git:

- [Aggregate report and all twelve transcripts](../demos/claim_verification/runs/20260912T203839Z-mms-menu-live-37cf05f41f/report.md).
- [Complete live logs](../demos/claim_verification/runs/20260912T203839Z-mms-menu-live-37cf05f41f/).
- [Frozen manifest](../demos/claim_verification/runs/20260912T203839Z-mms-menu-live-37cf05f41f/manifest.json).
- [Machine-readable results](../demos/claim_verification/runs/20260912T203839Z-mms-menu-live-37cf05f41f/summary.json).
- [CPU comparison and diagnostic artifacts](../demos/claim_verification/runs/20260912T203310Z-mms-menu-cpu-af162b2aba/).
- [Retained scripted rehearsal](../demos/claim_verification/runs/20260912T203330Z-mms-menu-dry-run-c1b812f594/report.md).

The source-manifest SHA-256 was
`3021be4f04079633a397a1184298b1e58f30e223ad2e28d6fe8beb599b6f20a2`.
CPU preparation, rehearsal, live execution and final source verification
matched. Recorded versions: Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1,
OpenAI SDK 2.54.0, httpx 0.28.1, budgeted-science 0.1.0.

From the repository root, regenerate the batch and episode reports/transcripts
without solvers, tools, credentials, or API calls:

```powershell
python -m budgeted_science.agents.mms_alternatives_catalog --render demos/claim_verification/runs/20260912T203839Z-mms-menu-live-37cf05f41f
```

JSON/JSONL integrity, recorded scores, slot identities, events and tool-action
counts are checked during replay. All available API-visible material is saved,
including returned reasoning summaries and opaque encrypted items, not raw
internal reasoning. Credentials and raw logs are not committed.

Verification passed: **701 shared tests plus 14 planning-pilot tests**, including
12 new tests covering numerical equivalence, limited diagnostic relevance,
prices/cache/failures, schemas, privacy, matched prompts, and complete offline
campaign/replay. The old scientific implementation and agent commands remain
unchanged. No standalone proposal was edited.

## Interpretation

This is a successful menu-robustness demonstration, not a harder benchmark.
The right diagnostic and a short affordable solution route remain available.
The added paid checks were not used, so this run does not measure Luna's
response to actually receiving their reassuring but insufficient results.

Six development studies share three systems, including an identical harmless
control. Perfect verdicts here do not establish open-ended report auditing,
independent construction of verification tests, justified confidence, or an
advantage over classical verification. These results provide no evidence that
adding plausible alternative tools alone solves the toy's difficulty problem.
