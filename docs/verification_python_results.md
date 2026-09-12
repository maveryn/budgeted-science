# Hosted-Python predator-prey verification: integration tests

## Latest outcome: authorized fresh episode completed

The corrected runner completed one fresh Luna/high episode on the same
development case. Luna **correctly rejected** the inaccurate claim, spending
all five scientific credits on one generic high-accuracy simulation purchase.
The fixed CPU verifier also correctly rejects the claim using five credits.

| Method | Verdict | Correct | Scientific credits |
|---|---|---|---:|
| Luna/high, hosted Python | REJECT | Yes | 5/5 |
| Fixed raw-data CPU verifier | REJECT | Yes | 5/5 |

Luna used three completed Python calls across three model responses:

1. Loaded the public study file.
2. Inspected the report and original numerical configuration (Euler, step 0.16).
3. Loaded its purchased rerun, computed both sampled maxima, their discrepancy,
   and the neighboring samples around the new maximum.

It independently selected DOP853, relative tolerance 1e-12, absolute tolerance
1e-14, and output spacing 0.0025. The returned trajectory contained 3,201 samples.
Its Python calculated a maximum of 28.282749553808586 at t=3.355 versus the
original 30.10709663921399 at t=3.52, a 6.450388% discrepancy. It submitted REJECT
against the printed claim of 30.10709664 within 5%. No helper computed that
comparison for it, and no private reference or CPU result entered its context.

The first response again included one unfinished Python call item, which the
corrected runner preserved without treating it as a completed execution. The
following turns proceeded successfully. There were no runner errors, invalid
scientific requests, retries or additional model calls after submission.

Runtime including container/file operations was **42.25 seconds**. Returned usage
totaled 39,855 input tokens and 2,587 output tokens (2,309 reasoning tokens).
Model-cost bounds are $0.00991584–$0.0245841. Including the $0.09 conservative
hosting reserve, the combined upper bound is **$0.1145841**, below the fresh
episode's $2 ceiling. The reserve is not an actual hosting invoice. All model
usage was resolved; there are no unknown model reservations.

The original public file and purchased trajectory were archived with matching
SHA-256 hashes, then the explicit network-disabled container was deleted.
Offline regeneration reproduced the transcript, Python listing and evaluation
byte-for-byte without contacting the API or running simulations. The frozen
source hash still matches the corrected preparation below; no code was changed.

Latest local records:
[report](../demos/claim_verification/runs/20260912T213930Z-python-live-556c24b977/report.md),
[transcript](../demos/claim_verification/runs/20260912T213930Z-python-live-556c24b977/transcript.md),
[Python code/output](../demos/claim_verification/runs/20260912T213930Z-python-live-556c24b977/python.md),
[raw event log](../demos/claim_verification/runs/20260912T213930Z-python-live-556c24b977/events.jsonl).

This is **one completed demonstration on one previously inspected system**, not
a held-out performance estimate. The earlier incomplete attempt remains below;
it is not silently discarded or merged with the new conversation. The coding
workflow works, but this case still admits a single accurate rerun and does not
show difficulty or an advantage over the CPU verifier.

## First attempt: preserved incomplete outcome

Hosted Python execution and public-file access worked. The first Luna/high
episode ended **incomplete because of a runner bookkeeping error**, before a
scientific purchase or verdict. It is not an accuracy result or evidence that
the scientific task became difficult. That turn attempted exactly one live
episode, with no automatic retry. The fresh run above followed separate approval.

| Method | Outcome | Scientific credits |
|---|---|---:|
| Luna/high with hosted Python | No submission; harness stopped after its first response | 0/5 |
| Fixed raw-data CPU verifier | Correct REJECT | 5/5 |

The existing development claim reports Q=30.10709664. The independently checked
reference is 28.282749565591107, a 6.45039% error, exceeding the 5% tolerance.
The fixed CPU verifier requested DOP853 (1e-10/1e-12) at output spacing 0.0025
and computed 28.282749554666093 from returned raw samples. Private reference and
CPU outcomes were not shown to Luna.

## What the API returned

The explicit 1-GB container confirmed disabled networking. Luna wrote and ran
Python to load the public study JSON and inspect its keys. Its first completed
Responses object contained:

1. One `code_interpreter_call` with status `completed`, with successful output.
2. Another Python call item with status `interpreting` and no output.
3. A completed custom `budget` function request.

The request and returned response both contained `max_tool_calls=1`. The harness
incorrectly interpreted the **two emitted Python items** as two executed calls,
raising `hosted_tool_limit_violation` before processing the free budget request.
The second item's unfinished status is preserved; we do not assert it executed.
The original final counter recorded zero calls because the guard ran before
incrementing it. The API archive establishes one completed call, and the offline
report now derives that count from the archived response instead of that counter.

The corrected runner counts terminal Python calls toward the execution limit,
retains nonterminal items unchanged in replay history, and never invents output
or executes those items locally. Two terminal calls still fail closed. The
installed OpenAI SDK input schema accepts these nonterminal statuses. The fix has
offline coverage and was exercised successfully in the fresh run above.

## Usage and records

One response, 2,570 input tokens and 335 output tokens (319 reasoning tokens).
Elapsed time including creation, upload and cleanup: 12.68 seconds. The measured
model-cost bounds are $0.000916–$0.001888; unresolved model reservations are zero.
The $0.09 conservative hosting reserve brings the combined upper bound to
**$0.091888**. Hosting was not independently invoiced by this runner; the reserve
must not be reported as the actual container charge. Pricing assumptions are in
the [protocol](verification_python_protocol.md).

All available stream events, complete response, code/output, public upload and
container file were saved. The one container was successfully deleted. Only the
public report/raw original trajectory was uploaded; no purchased trajectory was
needed before the stop. No key, repository, equations, private parameter, label,
or evaluator artifact was uploaded.

Local ignored artifacts:

- Original preparation and CPU comparison:
  `demos/claim_verification/runs/20260912T212648Z-python-prepared-cee9e1b4f5/`
- Original offline rehearsal:
  `demos/claim_verification/runs/20260912T212711Z-python-dry-run-6f40e87535/`
- Live attempt:
  [report](../demos/claim_verification/runs/20260912T212848Z-python-live-7ec0ae611c/report.md),
  [transcript](../demos/claim_verification/runs/20260912T212848Z-python-live-7ec0ae611c/transcript.md),
  [Python items](../demos/claim_verification/runs/20260912T212848Z-python-live-7ec0ae611c/python.md).
- Corrected preparation (used for the separately authorized fresh run):
  `demos/claim_verification/runs/20260912T213209Z-python-prepared-9eb48f54b2/`
- Corrected offline rehearsal:
  `demos/claim_verification/runs/20260912T213405Z-python-dry-run-ae0521b83b/`

The live source-manifest hash was
`e328bb3fc82a79018b10cdd243ca6d072c9ac72dfb240c9e909c7ba28d150297`.
Manifests retain individual source hashes, software versions, full settings and
prompt/schema hashes. Raw logs and original preparation remain preserved.

## Verification

The final corrected code passes **723 shared tests and 14 planning-pilot tests
(737 total)**, including 22 new offline tests. Coverage includes scientific
charging/reuse/failure handling, public-data allowlists, duplicate-call protection,
code-only turns, unfinished-call replay, interrupted streams, missing usage,
spending reservations, one-shot live launches, SDK file operations, credential
redaction, safe local download paths and offline regeneration.

The final full runs took 319.49 and 1.06 seconds. Commands:

```powershell
python -B -m unittest discover -s tests
python -B -m unittest discover -s demos/planning/tests
```

Software: Python 3.13.5, NumPy 2.3.4, SciPy 1.16.1, OpenAI SDK 2.54.0,
httpx 0.28.1. The corrected source-manifest hash is
`7a48d0236e98e1d8a9352fb47f15ab64f96cfa9953ae76c2115682333d944d85`.
No implementation changes were made after this corrected preparation.

## Interpretation and next step

The new interface supports real agent-authored Python rather than built-in peak
comparison, but the underlying claim remains solvable by one accurate raw-data
rerun. Neither difficulty nor adaptive benefit follows from changing the tool
interface. The completed fresh run confirms the coding-enabled execution loop,
not a harder benchmark. No additional model episodes or scientific redesign
are part of this result.
