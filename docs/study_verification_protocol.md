# Three-stage computational-study verification: frozen development pilot

## Scientific question and scoring

Audit a completed input-processing -> simulation -> output-analysis study. The
claim is the integral of downstream concentration over dimensionless time [0,1]
at x=0.75, with a 3% relative numerical-accuracy tolerance. A verdict is correct
only if it matches that printed number's error against an independently checked
continuous mathematical reference. ACCEPT/REJECT/ABSTAIN are available; abstention
is completed but not correct. Diagnoses and explanations are retained, not graded.
An inaccurate procedure with a coincidentally accurate number must be ACCEPTed.
This is not physical validation, parameter inference, or evidence sufficiency.

## Three stages

1. Raw coefficients in cm/s, cm^2/s and 1/s are converted to SI, then to
   dimensionless v=v_SI*T/L, D=D_SI*T/L^2, k=k_SI*T. The problem specifies L=1 m
   and T=1 s. The original preprocessing artifact records the normalization it
   actually used. Changing normalization in a rerun does not change the scored
   target, dimensionless geometry, initial profile or horizon.
2. Reuse the existing periodic linear transport equation, wrapped unit-peak
   Gaussian (center 0.25, width 0.045), decay 0.1 and velocity 0.6. The two
   intended diffusivities are 0.0005 and 0.003. Original fine studies use
   nx=128, centered advection, RK2, dt=1/1024 and output_dt=1/256. Coarse studies
   use nx=32, upwind advection, RK2, dt=1/256 and output_dt=1/1024.
3. The original exposure is actually calculated by trapezoidal integration of
   its saved sensor samples over its recorded analysis window. No final answer
   is fabricated. The claim prints ten significant digits.

Each system contributes six variants: sound; harmless input normalization
(L=0.997); consequential input normalization (L=0.8); coarse numerical study;
truncated analysis window [0,0.875]; harmless truncation [0,0.999]. Other settings
are held fixed. These are 12 development claims, not 12 independent systems.
Each category contains both systems; total six true and six false claims.
Commissioning requires true errors <=2.4% and false errors >=3.6%, failing rather
than silently substituting systems/settings. Thus these are not boundary cases.
Catalog order is shuffled once with seed 9122026 before policy/model outcomes.
Opaque IDs do not name variants; all six artifact roles exist in every study.

The existing Gaussian-image and analytic-Fourier references agree independently.
Reference generation is harness-side; neither policy nor agent may query it.
The physical equation is analytically tractable, so excluding a reference-query
tool does not prevent the agent from deriving an analytic approximation.

## Actions and scientific resources

`describe`, `read_artifact`, `prepare_inputs`, `quote`, `inspect_existing_run`,
`analyze_run`, `budget`, and `submit` are free. `run_simulation` is charged by
nx*(RHS evaluations + saved output fields)/16384, with a four-credit episode cap.
Euler costs one RHS per timestep, RK2 two. This is a work proxy, not FLOPs or money.
Output uses interpolation between actual integration steps. Unit arithmetic and
quadrature over existing arrays are not charged artificial diagnostic prices.

Every simulation uses the explicitly selected input ID. Every analysis uses the
explicitly selected run, window and quadrature. No action automatically fixes
the other stages or returns a reference, verdict, or certified error bound.
Original/purchased exact configurations are reusable free; a backend cache hit
does not waive a new episode's purchase. Invalid/unauthorized/unaffordable calls
are free, failed completed work is charged, and duplicated call IDs cannot buy
again. Full trajectories and input/analysis provenance are logged.

No full-budget requirement, savings bonus or early-stop reward. These are
trusted in-process numerical tools, not an arbitrary-code sandbox. All original
settings are inspectable; the task is not a secret implementation-bug puzzle.

## CPU comparisons

All controls choose an affordable, stable configuration using a frozen heuristic
balancing normalized spatial, integration and output spacings; they do not call
the reference. They compare the original claim to the resulting approximate
exposure using the 3% threshold (not a certified error estimate).

- `solver_only`: preserves original processed inputs and analysis settings.
- `input_and_solver`: recomputes inputs using intended normalization, preserves analysis.
- `solver_and_analysis`: preserves inputs, uses the entire required analysis window.
- `end_to_end`: uses intended input normalization and the full analysis window.
- `random`: seed-0 fixed random choice of whether to correct inputs/analysis.
  This particular draw selects both, making it identical to `end_to_end` here;
  it is not an independent confirmation or a randomized solver search baseline.

The final two can legally handle every stage within the budget because input
arithmetic and stored-array analysis are cheap. We do not claim this is an
adaptive scientific-investigation benchmark simply because it has three stages.
No labels, hidden parameters, references or baseline results reach model context.

## Luna evaluation

Exactly one `gpt-5.6-luna` episode per frozen claim, high reasoning, 4 scientific
credits, 30 responses, 30 tool calls, 32,768 maximum output tokens per response
including reasoning, 20-minute episode deadline. All twelve cases share a $2
TOTAL API spending ceiling, not $2 per case. No substitution, automatic restart,
automatic resume, limit increase, or post-result case selection.

Reuses the streamed Responses API runner: standard tier, store=false,
truncation disabled, sequential calls, token-count-based upper-bound reservations,
reasoning summaries and opaque encrypted-reasoning replay, no generation retries.
Uncertain usage retains its reservation. Credentials load privately in live mode
only; tests and dry-runs never read them. Inputs above 256k tokens are rejected.

Pricing/settings rechecked 2026-09-12 using
[official model documentation](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
and [pricing](https://developers.openai.com/api/docs/pricing): standard input
$0.20/M, cached input $0.02/M, output $1.20/M; reserve $0.25/M input to cover
cache writes. Costs are conservative bounds, not invoices. Available API-visible
logs are retained; raw internal reasoning is not exposed.

## Reproduction

From the repository root, using the existing optional `agents` installation:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_study_verification.py -q
.\.venv\Scripts\python.exe -B -m budgeted_science.study_verification.experiment cpu
# Use the printed CPU path explicitly; never silently choose a newest directory.
.\.venv\Scripts\python.exe -B -m budgeted_science.agents.study_catalog --dry-run --catalog PATH_TO_CPU_RUN
# Paid evaluation only with explicit authorization:
.\.venv\Scripts\python.exe -B -m budgeted_science.agents.study_catalog --live --catalog PATH_TO_CPU_RUN
.\.venv\Scripts\python.exe -B -m budgeted_science.study_verification.experiment render --path PATH_TO_CPU_RUN
.\.venv\Scripts\python.exe -B -m budgeted_science.agents.study_catalog --render PATH_TO_BATCH_OR_EPISODE
```

All generated artifacts stay in unique ignored `demos/claim_verification/runs/`
directories. Manifests pin catalog, code, import hashes, software, settings and
case order. Full API/event/numerical logs and readable transcripts are local.
Offline regeneration runs neither solvers nor API calls. A new `--live` command
creates a NEW batch; it is not a resume. Existing demos/proposals are unchanged.
