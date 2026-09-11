"""Fixed two-check verifier; policy decisions use public audit tools only."""
import argparse
import json
import math
from pathlib import Path
import re
from time import monotonic

from ..agents.records import RunLog, digest
from .environment import Episode, summarize
from .numerics import peak
from .reporting import numeric_quotes, render_episode
from .runner import DEFAULT_RUNS, PROMPT, provenance, save_public
from .studies import validate_study

METHOD = "fixed_two_check"
RULE = "ACCEPT iff abs(reported_Q - refined_Q) / abs(refined_Q) <= 0.05."


def fixed_two_check(call):
    """No study, parameters, reference, label, or evaluator is passed here."""
    inventory = call("list_artifacts", {})["artifacts"]
    analysis = next(a for a in inventory if a["role"] == "analysis")
    report = next(a for a in inventory if a["role"] == "report")
    call("read_artifact", {"id": report["id"]})
    text = call("read_artifact", {"id": analysis["id"]})["content"]
    # Restricted structured artifact, not general free-form report understanding.
    matches = re.findall(r"^Result:\s*(\S+)\s*$", text, flags=re.MULTILINE)
    if len(matches) != 1:
        raise ValueError("expected one reported result in the public analysis")
    reported = float(matches[0])
    if not math.isfinite(reported) or reported <= 0:
        raise ValueError("reported peak must be finite and positive")
    evidence = [analysis["id"], report["id"]]
    result = call("refine_integration", {"run_id": analysis["run_id"]})
    if result["status"] == "success":
        evidence.append(result["run_id"])
        result = call("refine_sampling", {"run_id": result["run_id"]})
    if result["status"] != "success":
        call("submit", dict(verdict="ABSTAIN", diagnosis="Required audit check unavailable.",
                            evidence_ids=evidence,
                            justification="Could not obtain the combined numerical check."))
        return {"reported_q": reported, "discrepancy": None, "check_failed": True}
    refined = result["q"]
    if not math.isfinite(refined) or refined <= 0:
        raise ValueError("refined peak must be finite and positive")
    discrepancy = abs(reported - refined) / abs(refined)
    evidence.append(result["run_id"])
    call("submit", dict(
        verdict="ACCEPT" if discrepancy <= 0.05 else "REJECT",
        diagnosis="Fixed integration-plus-sampling numerical comparison.",
        evidence_ids=list(dict.fromkeys(evidence)),
        justification=(f"Reported Q={reported:.10g}; {result['run_id']} Q={refined:.17g}. "
                       f"Relative discrepancy is {discrepancy:.17g}; threshold is 0.05. "
                       "This is an approximate numerical check, not a certified error bound.")))
    return {"reported_q": reported, "refined_q": refined,
            "discrepancy": discrepancy, "check_failed": False}


def run_episode(study, root, *, backend=None, clock=monotonic):
    log = RunLog(root, "fixed-two-check-episode")
    start = clock()
    try:
        log.write_json("manifest.json", {**provenance(), "method": METHOD, "rule": RULE,
                                        "scripted": False, "case_id": study["case_id"],
                                        "request_limit": 30, "deadline_seconds": 300})
        log.write_json("private/study.json", study)
        save_public(log, "public", study["artifacts"])
        def record(kind, **data):
            if kind == "numerical_artifact":
                artifact = data.pop("artifact")
                link = log.write_json(f"private/numerical/{data['run_id']}.json", artifact)
                log.event(kind, **data, artifact_path=link)
            else:
                log.event(kind, **data)
        episode = Episode(study, credits=5, backend=backend, log=record)
        log.event("prompt", text=PROMPT)
        log.event("assistant_message", text=f"Fixed numerical baseline. {RULE}")
        count = 0
        def call(name, arguments):
            nonlocal count
            if count >= 30 or clock() - start >= 300:
                raise TimeoutError("baseline request or runtime limit")
            count += 1
            return episode.tools.call(name, arguments, f"baseline-{count}")
        diagnostics = None
        try:
            diagnostics = fixed_two_check(call)
            if episode.state == "active":
                episode.abort("baseline ended without submission")
        except KeyboardInterrupt:
            episode.abort("interrupted")
            log.event("interrupted", spent=episode.spent)
        except Exception as exc:
            episode.abort("baseline execution error")
            log.event("failure", error=log.redactor.error(exc))
        evaluation = episode.evaluate()  # Private scoring, only after the decision.
        quotes = numeric_quotes(episode.submission or {},
                                {key: peak(run)["q"] for key, run in episode.runs.items()
                                 if run["status"] == "success"})
        save_public(log, "purchased", {k: v for k, v in episode.artifacts.items()
                                     if k not in study["artifacts"]})
        log.write_json("private/evaluation.json", evaluation)
        log.write_json("diagnostics.json", diagnostics)
        elapsed = clock() - start
        log.event("finished", evaluation=evaluation, submission=episode.submission,
                  numeric_quotes=quotes, api_calls=0, api_usd=0, tool_requests=count,
                  runtime_seconds=elapsed)
        render_episode(log.path)
        return {"case_id": study["case_id"], "episode_path": str(log.path),
                "category": study["private"]["category"], "format": study["format"],
                "evaluation": evaluation, "diagnostics": diagnostics,
                "runtime_seconds": elapsed}
    finally:
        log.close()


def render_results(path):
    """Saved records only: no policy or tool execution."""
    path = Path(path)
    rows = json.loads((path / "results.json").read_text(encoding="utf-8"))["cases"]
    summary = summarize([r["evaluation"] for r in rows])
    lines = ["# Fixed two-check verification baseline", "",
             "Development variants share six systems; not held-out evaluation.",
             "Task-specific numerical verifier, not a general report verifier or an LLM.",
             "", RULE, "",
             f"Correct: {summary['correct']}/{summary['episodes']}; "
             f"coverage: {summary['coverage']:.1%}; abstentions: {summary['abstentions']}; "
             f"incomplete: {summary['incomplete']}.",
             f"False acceptances: {summary['false_accepts']}/{summary['invalid_claims']}; "
             f"false rejections: {summary['false_rejects']}/{summary['valid_claims']}.",
             f"Total scientific credits: {sum(summary['credits_spent']):g}. API expenditure: $0.",
             "", "| Case | Category | Verdict | Correct | Discrepancy % | Credits | Transcript |",
             "|---|---|---|---|---:|---:|---|"]
    for row in rows:
        ep = Path(row["episode_path"])
        render_episode(ep)
        e, d = row["evaluation"], row["diagnostics"]
        discrepancy = f"{100*d['discrepancy']:.6f}" if d and d["discrepancy"] is not None else "n/a"
        link = ep.relative_to(path).as_posix() + "/transcript.md"
        lines.append(f"| {row['case_id']} | {row['category']} | {e['verdict']} | "
                     f"{e['correct']} | {discrepancy} | {e['spent']:g} | [trace]({link}) |")
    lines.extend(["", "Both checks fit the budget. The combined calculation is an approximate "
                  "check, not the private reference. No claim of adaptive auditing, general "
                  "document understanding, or confidence calibration follows."])
    (path / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (path / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def run_catalog(catalog_path, root=DEFAULT_RUNS):
    catalog_path = Path(catalog_path).resolve()
    catalog = json.loads((catalog_path / "private/catalog.json").read_text(encoding="utf-8"))
    integrity = json.loads((catalog_path / "catalog_integrity.json").read_text(encoding="utf-8"))
    if digest(catalog) != integrity["catalog_digest"] or not catalog["complete"]:
        raise ValueError("catalog integrity/commissioning check failed")
    for study in catalog["studies"]:
        validate_study(study)
    log = RunLog(root, "fixed-two-check")
    try:
        log.write_json("manifest.json", {**provenance(), "method": METHOD, "rule": RULE,
                                        "catalog_path": str(catalog_path),
                                        "catalog_digest": integrity["catalog_digest"],
                                        "case_ids": [s["case_id"] for s in catalog["studies"]],
                                        "cohort": "development", "systems": len(catalog["systems"])})
        rows = []
        for study in catalog["studies"]:
            log.event("episode_started", case_id=study["case_id"])
            row = run_episode(study, log.path / "episodes")
            rows.append(row)
            log.event("episode_finished", **row)
        log.write_json("results.json", {"method": METHOD, "cases": rows, "api_usd": 0})
        summary = render_results(log.path)
        log.event("finished", summary=summary)
        return log.path
    finally:
        log.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--catalog", type=Path)
    mode.add_argument("--render", type=Path)
    parser.add_argument("--root", type=Path, default=DEFAULT_RUNS)
    args = parser.parse_args()
    if args.render:
        print(json.dumps(render_results(args.render), indent=2))
    else:
        path = run_catalog(args.catalog, args.root)
        print(path)
        print((path / "summary.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
