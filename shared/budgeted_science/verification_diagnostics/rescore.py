"""Post-hoc reconstruction diagnostics. Never run a solver or alter source runs."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics

from ..agents.records import RunLog, digest, json_text, read_events
from . import VERSION

ROOT = Path(__file__).resolve().parents[3]
RUNS = ROOT/"demos/claim_verification/runs"


def metrics(rows):
    answer = {}
    for budget, policy in sorted({(r["budget"], r["policy"]) for r in rows}):
        group = [r for r in rows if (r["budget"],r["policy"]) == (budget,policy)]
        errors = [r["check_relative_error"] for r in group if r["check_relative_error"] is not None]
        answer.setdefault(str(budget), {})[policy] = {
            "count":len(group), "verdict_correct":sum(r["verdict_correct"] for r in group),
            "check_available":len(errors), "check_accurate":sum(r["check_accurate"] for r in group),
            "joint":sum(r["joint"] for r in group),
            "correct_verdict_bad_check":sum(r["verdict_correct"] and r["check_relative_error"] is not None and not r["check_accurate"] for r in group),
            "median_check_error":statistics.median(errors) if errors else None,
            "mean_check_error":statistics.mean(errors) if errors else None,
            "max_check_error":max(errors) if errors else None}
    return answer


def analyze(source):
    source = Path(source).resolve()
    hashes = {}
    def read(relative):
        file = (source/relative).resolve()
        if not file.is_relative_to(source):
            raise ValueError("artifact escapes source run")
        payload = file.read_bytes()
        hashes[file.relative_to(source).as_posix()] = hashlib.sha256(payload).hexdigest()
        return json.loads(payload)
    manifest, catalog = read("manifest.json"), read("catalog.json")
    if digest(catalog) != manifest["catalog_hash"]:
        raise ValueError("catalog provenance mismatch")
    cases = {s["id"]:s for s in catalog}
    if len(cases) != len(catalog) or set(cases) != {c["id"] for c in manifest["cases"]}:
        raise ValueError("duplicate or missing catalog case")
    for case in manifest["cases"]:
        if digest(cases[case["id"]]) != case["hash"]:
            raise ValueError("case provenance mismatch")
    rows, slots = [], set()
    allowed = {(c,b,p) for c in cases for b in manifest["budgets"] for p in manifest["policies"]}
    for result_file in sorted((source/"episodes").glob("*/result.json")):
        original = read(result_file.relative_to(source))
        slot = original["case_id"], original["budget"], original["policy"]
        if slot not in allowed or slot in slots:
            raise ValueError("unexpected or duplicate episode slot")
        slots.add(slot)
        episode_dir = result_file.parent
        if (source/original["path"].replace("\\","/")).resolve() != episode_dir.resolve():
            raise ValueError("episode path mismatch")
        event_file = episode_dir/"events.jsonl"
        hashes[event_file.relative_to(source).as_posix()] = hashlib.sha256(event_file.read_bytes()).hexdigest()
        events, torn = read_events(episode_dir)
        case = cases[slot[0]]
        reference = float(case["reference"]["q"])
        claim = case["public"]["claim"]
        tolerance = float(claim["tolerance"])
        if not math.isfinite(reference) or reference == 0 or tolerance <= 0:
            raise ValueError("invalid reference contract")
        truth = abs(claim["value"]-reference)/abs(reference) <= tolerance+1e-12
        evaluation, submission = original["evaluation"], original["submission"]
        verdict = evaluation["verdict"]
        if evaluation["valid"] != truth or evaluation["reference"] != reference:
            raise ValueError("stored evaluation disagrees with catalog")
        if submission is not None:
            submits = [v["arguments"] for v in events if v["kind"] == "tool_request" and v["name"] == "submit"]
            if not submits or submits[-1] != submission or submission["verdict"] != verdict:
                raise ValueError("submission provenance mismatch")
        elif verdict is not None:
            raise ValueError("verdict without submission")
        correct = verdict == ("ACCEPT" if truth else "REJECT")
        if evaluation["correct"] != correct:
            raise ValueError("stored correctness mismatch")
        forecasts = []
        if verdict in ("ACCEPT","REJECT"):
            originals = None
            for rid in submission["evidence_ids"]:
                if rid == "original-prediction":
                    originals = read(episode_dir.relative_to(source)/"originals.json")
                    run = originals["prediction"]
                    if run != case["prediction"]:
                        raise ValueError("original prediction differs from frozen catalog")
                elif rid.startswith("run-"):
                    run = read(episode_dir.relative_to(source)/"numerical"/(rid+".json"))
                else:
                    continue
                if run["experiment"] != "prediction":
                    continue
                if run["status"] != "complete" or not math.isfinite(run["q"]):
                    raise ValueError("cited forecast is incomplete or nonfinite")
                if rid != "original-prediction":
                    exposed = [v["result"] for v in events if v["kind"] == "tool_result" and v["name"] == "predict" and v["result"].get("result_id") == rid]
                    if not exposed or any(any(v[k] != run[k] for k in ("q","theta","method","work","status")) for v in exposed):
                        raise ValueError("forecast artifact differs from model-facing tool record")
                forecasts.append((rid,float(run["q"])))
        # Never pick whichever stored forecast happens to be most accurate.
        if len(forecasts) > 1:
            raise ValueError("multiple cited forecasts: reconstruction selection is ambiguous")
        rid, q = forecasts[0] if forecasts else (None,None)
        error = abs(q-reference)/abs(reference) if q is not None else None
        accurate = error is not None and error <= tolerance+1e-12
        rows.append({"case_id":slot[0],"budget":slot[1],"policy":slot[2],
            "family":case["private"]["family"],"verdict":verdict,"verdict_correct":correct,
            "check_id":rid,"check_value":q,"reference":reference,"check_relative_error":error,
            "check_accurate":accurate,"joint":correct and accurate,"tolerance":tolerance,
            "credits":evaluation["spent"],"source_episode":episode_dir.relative_to(source).as_posix(),
            "torn_event_tail":torn})
    if slots != allowed:
        raise ValueError("source campaign is missing episode results")
    for relative, expected in hashes.items():
        if hashlib.sha256((source/relative).read_bytes()).hexdigest() != expected:
            raise ValueError("source artifact changed during rescoring")
    return rows, hashes


def render(path):
    path = Path(path)
    rows = json.loads((path/"rows.json").read_text(encoding="utf-8"))
    result = {"episodes":len(rows),"api_usd":0,"post_hoc":True,"by_budget":metrics(rows)}
    lines = ["# Post-hoc reconstruction diagnostic", "",
        "Original verdict scores are unchanged. Joint = correct verdict AND cited forecast within the original 3% tolerance. This is not a universal verification score.", "",
        "| Budget | Policy | Verdict correct | Accurate check | Joint | Check available | Median check error |",
        "|---:|---|---:|---:|---:|---:|---:|"]
    for b, policies in result["by_budget"].items():
        for p,m in policies.items():
            median = f"{100*m['median_check_error']:.3f}%" if m["median_check_error"] is not None else "n/a"
            lines.append(f"| {b} | {p} | {m['verdict_correct']}/{m['count']} | {m['check_accurate']}/{m['count']} | {m['joint']}/{m['count']} | {m['check_available']} | {median} |")
    lines.extend(["", "Missing/abstained forecasts do not become correct reconstructions. Error summaries use available cited forecasts only. No best-of-history selection, numerical reruns, confidence grading or original artifact edits."])
    (path/"summary.json").write_text(json_text(result)+"\n",encoding="utf-8")
    (path/"report.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    return result


def run(source, output_root=RUNS):
    rows, hashes = analyze(source)
    log = RunLog(output_root,"verification-rescore")
    try:
        log.write_json("manifest.json",{"version":VERSION,"source":str(Path(source).resolve()),
            "source_artifacts":hashes,"script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "post_hoc":True,"rule":"Only the explicitly cited completed forecast; original relative tolerance; joint is diagnostic, not a replaced original score."})
        log.write_json("rows.json",rows)
        log.event("rescored",episodes=len(rows),source_mutations=0,solver_calls=0,api_usd=0)
        render(log.path)
    finally:
        log.close()
    print(log.path,flush=True)
    return log.path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("rescore","render"))
    parser.add_argument("path",type=Path)
    parser.add_argument("--output-root",type=Path,default=RUNS)
    args=parser.parse_args()
    if args.action == "rescore":
        path=run(args.path,args.output_root)
        print((path/"report.md").read_text(encoding="utf-8"))
    else:
        print(json_text(render(args.path)))


if __name__ == "__main__":
    main()
