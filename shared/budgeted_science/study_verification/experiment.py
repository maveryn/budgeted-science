"""Small development catalog and structured, non-oracle audit controls."""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from ..agents.records import RunLog, digest, json_text, read_events
from ..agents.runner import provenance
from ..transport_verification import numerics as num
from ..transport_verification.environment import relative_error, within
from ..transport_verification.experiment import configuration_menu
from . import VERSION
from .environment import Backend, Episode, analyze, process_inputs

ROOT = Path(__file__).resolve().parents[3]
RUNS = ROOT/"demos/claim_verification/runs"
POLICIES = ("solver_only", "input_and_solver", "solver_and_analysis", "end_to_end", "random")
VARIANTS = (
    ("sound", 1., "fine", 1.),
    ("harmless_input", .997, "fine", 1.),
    ("input", .8, "fine", 1.),
    ("numerical", 1., "coarse", 1.),
    ("analysis", 1., "fine", .875),
    ("harmless_analysis", 1., "fine", .999),
)


def science_hashes():
    paths = sorted(Path(__file__).parent.glob("*.py"))
    paths += [Path(num.__file__), Path(__file__).parents[1]/"transport_verification/environment.py",
              Path(__file__).parents[1]/"transport_verification/experiment.py"]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def build_catalog(backend=None):
    backend = backend or Backend()
    studies = []
    for index, p in enumerate(num.SYSTEMS[:2]):
        raw = {"velocity_cm_s": p["v"]*100, "diffusivity_cm2_s": p["D"]*10000, "decay_per_s": p["k"]}
        intended = {"length_m": 1., "duration_s": 1.}
        canonical = process_inputs(raw, **intended)
        reference = num.reference(canonical)
        for vi, (family, length, fidelity, end) in enumerate(VARIANTS):
            normalization = {"length_m": length, "duration_s": 1.}
            used = process_inputs(raw, **normalization)
            cfg = (num.config(128, 1/1024, "centered", "RK2", 1/256) if fidelity == "fine"
                   else num.config(32, 1/256, "upwind", "RK2", 1/1024))
            run, _ = backend.run(used, cfg)
            if run["status"] != "complete":
                raise ValueError("commissioning failure: original solve incomplete")
            run["system_used"] = deepcopy(used)
            analysis_config = {"start": 0., "end": end, "method": "trapezoid"}
            result = {"run_id": "original", **analyze(run, **analysis_config)}
            value = float(format(result["value"], ".10g"))
            error = relative_error(value, reference["qois"]["exposure"])
            expected_valid = family in ("sound", "harmless_input", "harmless_analysis")
            if (expected_valid and error > .024) or (not expected_valid and error < .036):
                raise ValueError(f"commissioning failure: {index}/{family} error={error}; no silent retuning")
            claim = {"quantity": "exposure", "value": value, "tolerance": .03,
                     "definition": "integral of c(0.75,t) from dimensionless time 0 to 1 using the intended problem normalization"}
            report = ("Study report", "Laboratory notebook", "Results memo")[(index+vi) % 3]
            public = {"report": f"{report}: downstream cumulative exposure is {value:.10g}, accurate within 3% relative error.",
                "claim": claim, "raw_inputs": raw, "intended_normalization": intended,
                "processed_inputs": used, "equation": "c_t + v*c_x = D*c_xx - k*c",
                "domain": [0., 1.], "boundary": "periodic", "horizon": 1.,
                "initial": {"type": "wrapped Gaussian, unit peak", "center": num.X0, "width": num.WIDTH},
                "sensor": num.SENSOR, "stage_contract": "Use intended L and T: v*=v_SI*T/L, D*=D_SI*T/L^2, k*=k_SI*T. The dimensionless geometry and initial profile are fixed. Integrate exposure over the entire stated horizon.",
                "scope": "Verification against the stated mathematical problem, not experimental validation or uncertain-parameter inference."}
            artifacts = {
                "problem": {"role": "problem specification", "content": deepcopy(public)},
                "preprocessing": {"role": "input preparation", "content": {"normalization_used": normalization,
                    "conversion": "v_SI=velocity_cm_s*0.01; D_SI=diffusivity_cm2_s*0.0001; v=v_SI*T/L; D=D_SI*T/L**2; k=decay_per_s*T", "processed": used}},
                "simulation": {"role": "simulation configuration", "content": {"input_id": "study-input", "system_used": used, "config": cfg, "status": run["status"]}},
                "analysis": {"role": "output analysis", "content": {"config": analysis_config, "result": result}},
                "report": {"role": "report", "content": {"text": public["report"], "claim": claim}},
                "trajectory": {"role": "stored trajectory", "content": {"run_id": "original", "samples": len(run["times"]), "access": "inspect_existing_run"}},
            }
            study = {"id": "study-"+digest({"version": VERSION, "system": index, "variant": vi})[:12],
                "system": canonical, "original": run, "original_analysis": result, "artifacts": artifacts,
                "public": public, "reference": reference,
                "private_selection": {"family": family, "system_index": index, "cohort": "development",
                                      "expected_valid": expected_valid, "relative_error": error}}
            studies.append(study)
    # Freeze a shuffled order before any policy or model results; no label-derived IDs in public views.
    return [studies[int(i)] for i in np.random.default_rng(9122026).permutation(len(studies))]


def choose_config(system, budget):
    menu = configuration_menu(system, budget)
    if not menu:
        raise ValueError("no affordable stable numerical check")
    # Fixed approximation-quality heuristic, no reference query or policy-result tuning.
    def quality(cfg):
        transit = num.WIDTH/system["v"]
        return ((1/cfg["nx"]/num.WIDTH)**2 + (cfg["dt"]/transit)**2 +
                (cfg["output_dt"]/transit)**2, num.quote(cfg)["credits"], digest(cfg))
    return min(menu, key=quality)


def policy(tools, name, seed=0):
    if name not in POLICIES:
        raise ValueError("unknown policy")
    public = tools.call("describe")["study"]
    artifact = tools.call("read_artifact", {"id": "analysis"})["content"]
    correct_input, correct_analysis = {
        "solver_only": (False, False), "input_and_solver": (True, False),
        "solver_and_analysis": (False, True), "end_to_end": (True, True),
        "random": tuple(bool(i) for i in np.random.default_rng(seed).integers(0, 2, 2)),
    }[name]
    system, input_id = public["processed_inputs"], "study-input"
    if correct_input:
        prepared = tools.call("prepare_inputs", public["intended_normalization"])
        system, input_id = prepared["system"], prepared["input_id"]
    cfg = choose_config(system, tools.call("budget")["budget"]["remaining"])
    check = tools.call("run_simulation", {"input_id": input_id, **cfg})
    if "error" in check or check["status"] != "complete":
        return tools.call("submit", {"verdict": "ABSTAIN", "diagnosis": "check unavailable",
                                     "evidence_ids": ["original"], "justification": "No completed comparison."})
    settings = {"start": 0., "end": 1., "method": "trapezoid"} if correct_analysis else artifact["config"]
    estimate = tools.call("analyze_run", {"run_id": check["run_id"], **settings})
    verdict = "ACCEPT" if within(public["claim"]["value"], estimate["value"], .03) else "REJECT"
    return tools.call("submit", {"verdict": verdict, "diagnosis": "structured numerical comparison",
        "evidence_ids": ["original", check["run_id"], estimate["analysis_id"]],
        "justification": f"{name}: compare original {public['claim']['value']} with approximate {estimate['value']}; no certified bound."})


def render(path):
    path = Path(path)
    manifest = json.loads((path/"manifest.json").read_text(encoding="utf-8"))
    rows = [json.loads(f.read_text(encoding="utf-8")) for f in sorted((path/"episodes").glob("*/result.json"))]
    summary = {"version": VERSION, "cases": len(manifest["case_ids"]), "episodes": len(rows), "policies": {}}
    for p in POLICIES:
        group = [r for r in rows if r["policy"] == p]
        summary["policies"][p] = {"correct": sum(r["evaluation"]["correct"] for r in group), "count": len(group),
            "incomplete": sum(r["evaluation"]["incomplete"] for r in group),
            "mean_credits": sum(r["evaluation"]["spent"] for r in group)/len(group) if group else None}
    lines = ["# Computational-study CPU controls", "", "Twelve development claims from two systems; no API calls.",
        "Free input arithmetic and stored-array analysis; four credits for numerical work. No confidence/diagnosis grading.", "",
        "```json", json_text(summary), "```", "", "| Case | Family (private) | Policy | Valid | Correct | Credits |",
        "|---|---|---|---|---|---:|"]
    for r in rows:
        e = r["evaluation"]
        lines.append(f"| {r['case_id']} | {r['family']} | {r['policy']} | {e['valid']} | {e['correct']} | {e['spent']:.6f} |")
    (path/"summary.json").write_text(json_text(summary)+"\n", encoding="utf-8")
    (path/"report.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    return summary


def run_cpu(output_root=RUNS):
    log = RunLog(output_root, "study-cpu")
    backend = Backend()
    print(log.path, flush=True)
    try:
        studies = build_catalog(backend)
        log.write_json("catalog.json", studies)
        log.write_json("manifest.json", {"version": VERSION, "budget": 4, "case_ids": [s["id"] for s in studies],
            "catalog_hash": digest(studies), "scientific_source_hashes": science_hashes(),
            "variants": VARIANTS, "policies": POLICIES, "policy_seed": 0,
            "frozen_before_policy_execution": True, **provenance(ROOT)})
        log.event("campaign_started", cases=len(studies))
        for s in studies:
            for p in POLICIES:
                episode_log = RunLog(log.path/"episodes", p)
                start = time.perf_counter()
                episode_log.write_json("public/artifacts.json", s["artifacts"])
                episode_log.write_json("numerical/original.json", s["original"])
                ep = Episode(s, backend=backend, log=episode_log)
                try:
                    policy(ep.tools, p)
                    row = {"case_id": s["id"], "policy": p, "family": s["private_selection"]["family"],
                        "evaluation": ep.evaluation(), "submission": ep.submission, "seconds": time.perf_counter()-start}
                    episode_log.write_json("result.json", row)
                    episode_log.event("episode_finished", result=row)
                finally:
                    episode_log.close()
                log.event("episode_completed", path=str(episode_log.path.relative_to(log.path)), result=row)
            print(s["id"], s["private_selection"]["family"], s["private_selection"]["relative_error"], flush=True)
        log.event("campaign_finished", cases=len(studies))
    finally:
        log.close()
    print(json_text(render(log.path)), flush=True)
    return log.path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["cpu", "render"])
    parser.add_argument("--path", type=Path)
    parser.add_argument("--output-root", type=Path, default=RUNS)
    args = parser.parse_args()
    if args.action == "render":
        if args.path is None:
            parser.error("render requires --path")
        print(json_text(render(args.path)))
    else:
        run_cpu(args.output_root)


if __name__ == "__main__":
    main()
