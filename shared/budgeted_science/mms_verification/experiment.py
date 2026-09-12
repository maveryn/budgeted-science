"""CPU commissioning, five small policy controls, durable logs and offline reports."""
import argparse
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import statistics
from time import perf_counter

from ..agents.records import RunLog, digest, json_text, read_events, utc_now
from . import VERSION
from .catalog import SLOTS, make_catalog, public_original_data, public_study
from .environment import Audit, score
from .numerics import DIAGNOSTIC, GRIDS, MMS_GRIDS, ORDER_BAND, PROBLEMS, STUDY_PROFILES, validate
from .policies import POLICIES, run_policy

ROOT = Path(__file__).resolve().parents[3]
RUNS = ROOT / "demos" / "claim_verification" / "runs"


def provenance():
    files = list(Path(__file__).parent.glob("*.py"))
    files.append(Path(__file__).parents[1]/"agents"/"records.py")
    return {"version": VERSION, "python": platform.python_version(), "platform": platform.platform(),
            "dependencies": {p: importlib.metadata.version(p) for p in ("numpy", "scipy")},
            "source_sha256": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in sorted(files)}}


def configuration():
    return {"grids": list(GRIDS), "mms_grids": list(MMS_GRIDS), "order_band": list(ORDER_BAND),
            "problems": {k: asdict(v) for k, v in PROBLEMS.items()},
            "diagnostic_profile": asdict(DIAGNOSTIC),
            "private_study_profiles": {k: asdict(v) for k, v in STUDY_PROFILES.items()},
            "private_development_slots": SLOTS, "budgets": [10, 20], "policies": list(POLICIES),
            "cost": "(grid+1)^2/289; grid-size proxy, not measured FLOPs/runtime",
            "api_dollars": 0, "classification": "CPU development commissioning, no agents or held-out evaluation"}


def aggregate(results):
    groups = []
    for budget, policy in sorted(set((r["budget"], r["policy"]) for r in results)):
        rows = [r for r in results if r["budget"] == budget and r["policy"] == policy]
        group = {"budget": budget, "policy": policy, "episodes": len(rows),
                 "joint_correct": sum(r["evaluation"]["joint_correct"] for r in rows),
                 "incomplete": sum(not r["evaluation"]["complete"] for r in rows),
                 "mean_credits": statistics.mean(r["spent"] for r in rows),
                 "mean_seconds": statistics.mean(r["seconds"] for r in rows)}
        for name in ("qoi", "order"):
            evaluations = [r["evaluation"][name] for r in rows]
            group[name] = {key: sum(e[key] for e in evaluations)
                           for key in ("correct", "covered", "false_accept", "false_reject")}
            group[name]["abstentions"] = sum(e["verdict"] == "ABSTAIN" for e in evaluations)
            group[name]["true_claims"] = sum(e["truth"] for e in evaluations)
            group[name]["false_claims"] = sum(not e["truth"] for e in evaluations)
        groups.append(group)
    return groups


def report_text(summary):
    lines = ["# MMS verification: CPU development results", "",
             f"Batch status: {summary.get('status', 'complete')}; unattempted policy slots: {summary.get('unattempted', 0)}.", "",
             "Six studies on three physical problems. No agents, API calls, or held-out systems. "
             "Two original studies are numerically identical inactive-feature controls. "
             "Budgets were commissioned before policies ran. Repeated policies/budgets do not add independent cases.", "",
             "Commissioning requires the same independent-grid-32 plug-in estimate used by the study-aware policy to classify "
             "each selected value correctly. Together with directly measured MMS order, this makes its correct scientific "
             "answers a commissioning invariant (assuming successful execution), not held-out performance evidence.", "",
             "## Studies and separately scored truths", "",
             "| Study | Development category | Reported QoI error | Finite-grid orders | QoI true | Order true |",
             "|---|---|---:|---|---|---|"]
    for c in summary["cases"]:
        p = c["private"]
        lines.append(f"| {c['id']} | {c['category']} | {100*p['q_error']:.4f}% | "
                     f"{p['observed_orders'][0]:.3f}, {p['observed_orders'][1]:.3f} | {p['qoi_truth']} | {p['order_truth']} |")
    lines += ["", "## Policy results", "",
              "All correctness counts include abstentions/incomplete episodes in the denominator. "
              "QoI-only refinement is a partial-task control, not a full verifier. "
              "No error bound, confidence score, or cost-saving reward is claimed.", "",
              "| Credits available | Policy | QoI correct | Order correct | Both correct | Q/order abstentions | Mean spent | Mean seconds |",
              "|---:|---|---:|---:|---:|---:|---:|---:|"]
    for g in summary["aggregate"]:
        n = g["episodes"]
        lines.append(f"| {g['budget']} | {g['policy']} | {g['qoi']['correct']}/{n} | {g['order']['correct']}/{n} | "
                     f"{g['joint_correct']}/{n} | {g['qoi']['abstentions']}/{g['order']['abstentions']} | "
                     f"{g['mean_credits']:.4f} | {g['mean_seconds']:.4f} |")
    lines += ["", "## Per-episode records", "", "| Budget | Policy | Study | QoI | Order | Spent | Trace |",
              "|---:|---|---|---|---|---:|---|"]
    for r in summary["results"]:
        lines.append(f"| {r['budget']} | {r['policy']} | {r['study_id']} | {r['evaluation']['qoi']['verdict']} | "
                     f"{r['evaluation']['order']['verdict']} | {r['spent']:.4f} | [events]({r['directory']}/events.jsonl) |")
    lines += ["", "## Limits", "",
              "These are deliberately selected development controls, not a difficult general verification benchmark. "
              "The finite-grid order band is an operational criterion, not proof of asymptotic correctness. "
              "Code-order failure does not by itself disprove the original value. Independent recomputation uses a separate "
              "assembly of the same discretization, not an exact-answer tool. MMS exact errors are public only on diagnostics. "
              "Credits proxy grid size; sparse solve/runtime costs are not calibrated by that rule. "
              "Local trusted-process separation is not a sandbox. Original manufactured forcing may permit analytic shortcuts "
              "if arbitrary coding/source inspection is later allowed.", ""]
    return "\n".join(lines)


def artifact_hashes(path):
    path = Path(path)
    return {p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(path.rglob("*")) if p.is_file() and p.suffix in (".json", ".jsonl")
            and p != path/"completion.json"}


def reconcile(path, summary):
    """Cross-check saved scores/submissions/charges/evidence without running tools."""
    catalog_path = path/"private"/"catalog.json"
    cases = {c["id"]: c for c in json.loads(catalog_path.read_text(encoding="utf-8"))["cases"]} if catalog_path.exists() else {}
    for row in summary["results"]:
        episode = (path/row["directory"]).resolve()
        if not episode.is_relative_to(path.resolve()):
            raise ValueError("episode path leaves run")
        saved = json.loads((episode/"result.json").read_text(encoding="utf-8"))
        if saved != row or score(row["submission"], cases[row["study_id"]]) != row["evaluation"]:
            raise ValueError("episode result/evaluation mismatch")
        events, _ = read_events(episode)
        pending, submission, units, evidence = {}, None, 0, {"original"}
        for event in events:
            if event["kind"] == "request":
                pending[event["call_id"]] = event
            elif event["kind"] == "response":
                request = pending[event["call_id"]]
                if request["action"] == "submit" and event["response"]["ok"]:
                    args = request["arguments"]
                    submission = {"qoi": args["qoi"], "order": args["order"],
                                  "evidence_ids": args["evidence_ids"], "explanation": args.get("explanation", "")}
            elif event["kind"] == "purchase":
                if event["charged_units"] != (event["grid"]+1)**2:
                    raise ValueError("recorded purchase price mismatch")
                units += event["charged_units"]
            elif event["kind"] == "numerical":
                artifact_path = (episode/event["artifact_path"]).resolve()
                if not artifact_path.is_relative_to(episode):
                    raise ValueError("artifact path leaves episode")
                artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
                evidence.add(artifact["id"])
        if submission != row["submission"] or abs(units/289-row["spent"]) > 1e-10 or row["spent"] > row["budget"]:
            raise ValueError("submission or ledger does not match episode events")
        if submission and not set(submission["evidence_ids"]).issubset(evidence):
            raise ValueError("submission cites missing purchased evidence")


def render(path):
    """Offline only: no solver, tool execution, network or credential access."""
    path = Path(path)
    manifest = json.loads((path/"manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((path/"summary.json").read_text(encoding="utf-8"))
    completion = json.loads((path/"completion.json").read_text(encoding="utf-8"))
    if digest(summary) != completion["summary_sha256"] or digest(manifest) != completion["manifest_sha256"]:
        raise ValueError("saved manifest/summary integrity mismatch")
    if artifact_hashes(path) != completion["artifact_sha256"]:
        raise ValueError("saved episode/catalog artifact integrity mismatch")
    reconcile(path, summary)
    regenerated = aggregate(summary["results"])
    if regenerated != summary["aggregate"]:
        raise ValueError("aggregate mismatch")
    target = path/"report.md"
    target.write_text(report_text(summary), encoding="utf-8")
    for row in summary["results"]:
        episode = path/row["directory"]
        events, torn = read_events(episode)
        lines = ["# CPU audit transcript", "", f"Study: {row['study_id']}; policy: {row['policy']}; budget: {row['budget']}", ""]
        for event in events:
            if event["kind"] in ("public_input", "request", "response", "failure"):
                lines += [f"## {event['sequence']}: {event['kind']}", "", "```json", json_text(event), "```", ""]
            elif event["kind"] == "numerical":
                lines += [f"Numerical artifact: [{event['artifact_path']}]({event['artifact_path']})", ""]
        if torn:
            lines.append("Interrupted final event retained as a torn log tail.")
        (episode/"transcript.md").write_text("\n".join(lines), encoding="utf-8")
    return target


def run_cpu(root=RUNS):
    log = RunLog(root, "mms-cpu")
    started = perf_counter()
    manifest = {**provenance(), "utc": utc_now(), "configuration": configuration()}
    catalog, results, status = {"cases": [], "feasibility": []}, [], "complete"
    try:
        log.write_json("manifest.json", manifest)
        log.event("frozen", manifest_sha256=digest(manifest))
        numerical = validate()
        log.write_json("validation.json", numerical)
        catalog = make_catalog()
        log.write_json("private/catalog.json", catalog)
        log.write_json("commissioning.json", {k: v for k, v in catalog.items() if k != "cases"})
        log.event("commissioned", catalog_sha256=digest(catalog), budgets=catalog["budgets"])
        for case in catalog["cases"]:
            log.write_json(f"public/{case['id']}/study.json", public_study(case))
            log.write_json(f"public/{case['id']}/original_data.json", public_original_data(case))
        for budget in catalog["budgets"]:
            for policy in POLICIES:
                for case in catalog["cases"]:
                    episode = RunLog(log.path/"episodes", f"b{budget}-{policy}")
                    start = perf_counter()
                    # Cold per-episode cache keeps measured CPU timings comparable.
                    # Within-episode reuse remains free; separate tests check warm caches.
                    def sink(kind, **data):
                        if kind == "numerical":
                            artifact = data.pop("artifact")
                            data["artifact_path"] = episode.write_json(f"artifacts/{artifact['id']}.json", artifact)
                        episode.event(kind, **data)
                    audit = Audit(case, budget, sink=sink)
                    failure, diagnostics = None, None
                    try:
                        episode.write_json("public.json", audit.describe())
                        episode.write_json("original_data.json", public_original_data(case))
                        episode.event("public_input", content=audit.describe())
                        diagnostics = run_policy(policy, audit.describe(), audit.call)
                    except (Exception, KeyboardInterrupt) as exc:
                        failure = {"type": type(exc).__name__, "message": str(exc)}
                        episode.event("failure", **failure)
                        if isinstance(exc, KeyboardInterrupt):
                            raise
                    finally:
                        row = {"study_id": case["id"], "policy": policy, "budget": budget,
                               "spent": audit.status()["spent"], "seconds": perf_counter()-start,
                               "submission": audit.submission, "evaluation": score(audit.submission, case),
                               "diagnostics": diagnostics, "failure": failure, "api_dollars": 0,
                               "directory": episode.path.relative_to(log.path).as_posix()}
                        episode.write_json("result.json", row)
                        episode.close()
                        results.append(row)
                        log.event("episode", result=row)
    except KeyboardInterrupt:
        status = "interrupted"
        log.event("interrupted", attempted=len(results))
    except Exception as exc:
        status = "failed"
        log.event("failure", error_type=type(exc).__name__, message=str(exc))
    finally:
        source_match = provenance()["source_sha256"] == manifest["source_sha256"]
        if not source_match:
            status = "source_mismatch"
        summary = {"version": VERSION, "status": status, "source_freeze_matches": source_match,
                   "unattempted": 60-len(results),
                   "cases": [{k:v for k,v in c.items() if k != "original"} for c in catalog["cases"]],
                   "feasibility": catalog["feasibility"], "results": results, "aggregate": aggregate(results),
                   "seconds": perf_counter()-started, "api_dollars": 0}
        log.write_json("summary.json", summary)
        log.event("finished", status=status, episodes=len(results), seconds=summary["seconds"])
        log.close()
        log.write_json("completion.json", {"summary_sha256": digest(summary), "manifest_sha256": digest(manifest),
                                           "artifact_sha256": artifact_hashes(log.path)})
    render(log.path)
    return log.path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    cpu = sub.add_parser("cpu")
    cpu.add_argument("--output", type=Path, default=RUNS)
    replay = sub.add_parser("render")
    replay.add_argument("path", type=Path)
    args = parser.parse_args()
    if args.command == "validate":
        print(json_text(validate()))
    elif args.command == "cpu":
        print(run_cpu(args.output))
    else:
        print(render(args.path))


if __name__ == "__main__":
    main()
