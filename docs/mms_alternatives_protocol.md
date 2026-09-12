# MMS verification: matched alternative-tool menus

Frozen small extension of the [MMS toy](mms_verification_protocol.md), not a
replacement benchmark. Reuse all six existing development studies in their
original order. Do not change either claim, the public report, numerical
problem, scoring, ten-credit limit, or successful original audit route.

## Additional checks

| Tool | Operation | Price | Interpretation |
|---|---|---|---|
| `run_affine_mms` | Manufacture `u=1.1+0.2*x+0.35*y` with selected original problem family, grid and kernel | `(grid+1)^2/289` | Tests consistency on this affine profile; exactness here does not establish the original sinusoidal finite-grid order claim. |
| `crosscheck_linear_solver` | ILU-preconditioned GMRES on a purchased run's same discrete operator, source, boundaries and grid | `(grid+1)^2/289` | Tests algebraic agreement, not a different discretization. |
| `richardson` | Point-value extrapolation from two purchased original-study results, using caller-supplied order | Free | Assumes leading error `C*h^p`; neither a certified error bound nor an observed-order measurement. |

GMRES uses `rtol=1e-12`, `atol=1e-13`, restart 50, maximum 200 restart
cycles; ILU uses drop tolerance `1e-4` and fill factor 10. Its actual runtime
and iterations are recorded. Prices remain the declared grid-size proxy,
not measured FLOPs, runtime, or a claim of equal computational difficulty.
The original direct solver already reports its algebraic residual for free.

Affine diagnostics return their exact error norms, not a pass/fail verdict.
At numerical-floor errors, convergence order is undefined. The original
`run_mms` diagnostic and two scored claims remain unchanged. Richardson
accepts same-kernel, increasing-grid original-study records only, with finite
assumed order in `[0.1,8]`; diagnostic records cannot be substituted. Derived
records can be retrieved and cited at no scientific charge.

All solves use complete versioned keys. Failed executed solves are charged
and cached; invalid/unaffordable requests are uncharged. Purchased results
are free to reuse; backend cache hits still incur independent episode charges.
No exact original-study answer, fault flag, category, or CPU outcome is sent
to the model. New implementations are isolated from the frozen old modules.

## Matched model protocol

- Exact model `gpt-5.6-luna`, high reasoning, standard service, Responses API.
- Six original-menu and six expanded-menu fresh episodes, independent history
  and ten-credit ledger. Alternate which menu is first between studies.
- Same scientific prompt within each pair. The tool menu differs; shared
  schemas and relative alphabetical ordering are identical. The common prompt
  identifies the original MMS profile explicitly and omits the varying
  remaining API allowance. The actual allowance is enforced and logged.
- 30 responses, 30 tool requests, 32,768 output tokens per response including
  reasoning, five-minute episode deadline; no full-budget submission rule.
- **$2 for the entire twelve-slot batch**, not per slot. Reserve maximum
  generation cost before each request. No automatic retry, substitution,
  increase, or restart; preserve incomplete outcomes and uncertain charges.
- Available API-visible messages, summaries, opaque encrypted reasoning,
  requests, stream events, tool responses, numerical fields, private scoring,
  and source/prompt/schema hashes are retained locally. No raw internal
  reasoning is claimed. Credentials and raw runs remain ignored by Git.

Model capabilities and prices were checked in the official
[Luna documentation](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
and [pricing table](https://developers.openai.com/api/docs/pricing) on
12 September 2026. Conservative bounds use $0.25/M input and $1.20/M output;
inputs over 256,000 tokens are refused by the existing runner.

## CPU commissioning and reproduction

CPU preparation replays the unchanged study-aware rule with both menus and
checks its verdicts against the saved CPU pilot. Separate diagnostic traces
exercise affine grids 8/16/32, iterative re-solving of the original, and
Richardson from audited grids 8/16. These diagnostics are not an adaptive
baseline or evidence of agent performance. The original successful CPU route
was deliberately ensured during the original toy's commissioning.

From the repository root, with the editable environment installed:

```powershell
python -m budgeted_science.agents.mms_alternatives_catalog --cpu
python -m budgeted_science.agents.mms_alternatives_catalog --dry-run --prepared PATH_TO_CPU_RUN
python -m budgeted_science.agents.mms_alternatives_catalog --live --prepared PATH_TO_CPU_RUN
python -m budgeted_science.agents.mms_alternatives_catalog --render PATH_TO_SAVED_BATCH
```

`--live` makes paid calls only when explicitly invoked. CPU preparation seals
the code/dependencies/cases before evaluation; changes require new preparation.
Dry-run uses scripted fake responses and costs zero API dollars. Render checks
saved JSON/JSONL integrity and rebuilds reports/transcripts without scientific
tools or API calls. There is no automatic crash-resume for these batch slots.

Report each claim and joint correctness, abstentions/incomplete outcomes,
scientific spending, extra-tool use, runtime and API bounds. These six studies
share three physical systems and include an identical harmless control. One
episode per menu/study is a descriptive robustness check, not a reliable
causal estimate or evidence of a difficult benchmark. Extra tools may help,
be ignored, or consume resources without answering the original claims.
