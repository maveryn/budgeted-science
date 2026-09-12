# Predator-prey claim audit with hosted Python

This independent extension retains the original predator-prey study and objective
5%-accuracy verdict, but replaces specialized analysis/refinement helpers with
agent-written Python and a generic numerical service. Earlier catalogs, runners,
and results are unchanged. No generated code executes on the local machine.

## First test

One existing development case, `study-234bf5051eba1b`, from system seed 7102 with
consequential integration error. It was used in the earlier tool-menu comparison.
Selection is explicit, not randomized or held out; the purpose is testing file
access, analysis code, paid reruns, logging and submission.

The claim is the printed maximum of prey population x on [0,8], within 5% of the
fixed mathematical model's maximum. The private DOP853/Radau reference and scoring
contract are unchanged. Correct ACCEPT/REJECT is scored; ABSTAIN is complete but
not correct. Explanations are retained, not semantically graded.

## Public files and tools

Only an allowlisted public JSON file is uploaded initially: the short report,
original run ID, numerical configuration, output times and x/y values. Private
parameters, equations, internal solver interpolation coefficients, labels,
reference, repository and credentials are not uploaded. Purchased runs use the
same raw-file schema. Local API functions and hosted Python alternate; Python
cannot directly invoke local services.

| Interface | Behavior |
|---|---|
| Hosted Python | Agent-written analysis of public/purchased files; no scientific-credit charge |
| `simulate` | Agent selects source run, Euler/DOP853/Radau, step/tolerances and output schedule; raw file only |
| `run_record` | Free retrieval of an original or purchased raw file |
| `budget` | Free ledger/status |
| `submit` | ACCEPT/REJECT/ABSTAIN, diagnosis, run evidence IDs, explanation |

There is no peak, convergence, error-estimate or verdict helper. The report itself
still describes its original numerical method. The agent can plot, fit,
interpolate, compare, or write other analysis code.

Five scientific credits use the earlier fixed-price semantics: changing the
integration configuration relative to a chosen purchased source costs 3; changing
its output schedule costs 2; changing both costs 5. Exact purchased configurations
are free. Executed failures remain charged and cached. Invalid or unaffordable
requests are uncharged. This is an illustrative service-price schedule, not
runtime/FLOP measurement; high accuracy remains affordable in one combined call.

Euler step is in [0.001,0.32] and must divide 8; adaptive relative tolerance in
[1e-12,1e-3], absolute tolerance in [1e-14,1e-6]. Output spacing is 0 to inherit,
or [0.0025,4], with a phase fraction in [0,1). Both endpoints are included.
Unused solver arguments do not change cache identity or charge. Reruns use the
actual numerical trajectory, not interpolation of sparse saved output.

The CPU comparison selects DOP853 at 1e-10/1e-12 and spacing 0.0025, computes the
maximum from returned arrays, and compares it with the public printed value.
It uses the same raw service and an independent five-credit ledger. This is a
claim-specific comparison, not a general free-form scientific verifier.

## Hosted execution, limits and dollars

Exact model `gpt-5.6-luna`, high reasoning, standard tier, streaming Responses API,
`store=false`, no retries/substitution, 30 responses, 30 function requests,
32,768 output tokens per response, 20-minute episode deadline. A response may use
one built-in Python call; code-only responses can continue in the same episode.
The API can also emit an unfinished call item after reaching that limit. Such
items are retained as returned, not counted as completed execution or run locally.
Reasoning summaries, opaque encrypted items and complete Code Interpreter items
are replayed. Raw internal reasoning is not available.

One explicit 1-GB container has networking disabled and a 20-minute inactivity
expiry. Returned memory/network settings are checked before model use. Only its
own generated/uploaded files are archived, then this ephemeral container is
deleted. No Docker, WSL or local arbitrary Python execution is used.

The combined ceiling is USD 2. Standard Luna rates are $0.20/M input, $0.02/M
cache reads, $0.25/M cache writes, $1.20/M output; long-context rates can double
input and multiply output by 1.5. A hosted 1-GB container is listed at $0.03 per
20-minute session; eligible sessions may instead be billed by minute with a
five-minute minimum. Sources checked 2026-09-12:
[model](https://developers.openai.com/api/docs/models/gpt-5.6-luna),
[pricing](https://developers.openai.com/api/docs/pricing),
[Code Interpreter](https://developers.openai.com/api/docs/guides/tools-code-interpreter).

Accounting reserves $0.09 for hosting, covering three 20-minute blocks including
cleanup/inactivity margin. This is not a measured hosting bill. Each generation
reserves two maximum-size input passes (922,000 tokens each), because one built-in
tool call can add a second internal model pass. Both use the long-context
cache-write rate of $0.50/M; output is reserved at $1.80/M. The resulting generation
reservation is $0.9809824, regardless of the smaller initial input count. Input
counting must succeed and initial input must not exceed 256,000 tokens.
Returned usage is settled at conservative long-context rates; unknown usage
keeps its full reservation and ends the episode. These are documented pricing/cap
assumptions, not an invoice. No automatic new container, retry or paid continuation
occurs. A persistent one-shot marker prevents reusing a prepared live slot.

## Records and reproduction

```powershell
python -m budgeted_science.agents.verification_python --prepare
python -m budgeted_science.agents.verification_python --dry-run --prepared <prepared-directory>
# Requires explicit authorization; reads the existing key privately:
python -m budgeted_science.agents.verification_python --live --prepared <prepared-directory>
python -m budgeted_science.agents.verification_python --render <episode-directory>
```

Prepare freezes sources, case, settings, schemas, prompt template and CPU result.
Do not change implementation after preparation. Each episode saves its actual
prompt/schema with container paths before the first generation. Raw runs are
unique and ignored under `demos/claim_verification/runs/`.

Records include requests/counts/stream events/responses, exact delivered tool
results, numerical artifacts, code/outputs, upload hashes, container metadata,
file inventory/downloads, private scoring and CPU comparison. `python.md` displays
API-visible executed code; `transcript.md` shows the full conversation. Downloads
are inert hash-named `.bin` files with original names in the inventory, never
executed locally. Archiving has a 100-file, 20-MB safety cap; omissions/failures
are logged. The prompt requests at most 10 MB of generated files. Offline
rendering reads logs only.

Dry-run uses scripted output, **not local execution of model-generated Python**,
and costs zero. The real SDK is separately tested with mock HTTP transport.

## Interpretation

This changes the interface, not the scientific difficulty. A single well-chosen
high-accuracy rerun can still solve this claim family. Coding can help the agent;
it need not make the task harder. Success establishes mechanics, not adaptive
auditing, general code verification, justified confidence or baseline superiority.

See the [integration-test results](verification_python_results.md): the first
attempt stopped on a now-fixed item-counting guard. A separately authorized fresh
Luna/high episode then completed with a correct REJECT, three Python executions,
one five-credit simulation purchase, and a $0.115 conservative combined cost bound.
