"""Coherent completed studies and deterministic development commissioning."""

from copy import deepcopy
import csv
import io
import json

import numpy as np

from ..agents.records import digest
from .numerics import (Backend, BOUNDS, INITIAL, VERSION, configuration,
                       output_grid, peak, reference, reported_value)


SEEDS = tuple(range(7100, 7106))
CATEGORIES = ("sound", "harmless_integration", "consequential_integration",
              "harmless_sampling", "consequential_sampling")
FORMATS = ("research_report", "lab_notebook", "results_memo")
EULER_STEPS = (0.005, 0.01, 0.02, 0.04, 0.08, 0.16, 0.32)
OUTPUT_SPACINGS = (0.1, 0.25, 0.5, 1.0, 2.0, 4.0)
PHASES = (0.0, 0.25, 0.5, 0.75)


def error_fraction(q_reported, q_reference):
    if not np.isfinite(q_reference) or q_reference <= 0:
        raise ValueError("positive finite reference required")
    return abs(q_reported - q_reference) / abs(q_reference)


def truth_label(q_reported, q_reference, tolerance=0.05):
    error = error_fraction(q_reported, q_reference)
    # Only absorb machine arithmetic at an inclusive boundary, not scientific error.
    roundoff = 8 * np.finfo(float).eps * max(abs(q_reported), abs(q_reference))
    return abs(q_reported - q_reference) <= tolerance * abs(q_reference) + roundoff


def configuration_text(config):
    if config["method"] == "Euler":
        integration = f"Explicit Euler; integration timestep {config['dt']:.12g}."
    else:
        integration = (f"{config['method']}; relative tolerance {config['rtol']:.12g}; "
                       f"absolute tolerance {config['atol']:.12g}.")
    differences = np.diff(config["output_times"])
    return (integration + f"\nStored samples: {len(config['output_times'])}, including t=0 and t=8."
            + f"\nOutput gaps range from {min(differences):.12g} to {max(differences):.12g}."
            + "\nThe exact output schedule is the time column of the trajectory artifact.")


def render_report(study, format_id):
    if format_id not in range(3):
        raise ValueError("unknown report format")
    q = format(study["reported_q"], ".10g")
    claim = (f"The maximum population of species A over t in [0, 8] is {q}, "
             "accurate to within +/-5% relative to the mathematical model's true maximum.")
    setup = ("A completed numerical study of a coupled two-population dynamical system. "
             "Species A is x; species B is y. Initial populations: x(0)=10, y(0)=5. "
             "Population and time units are dimensionless. The physical setup is fixed; "
             "this audit concerns numerical accuracy, not agreement with experiments.")
    method = configuration_text(study["run"]["config"])
    analysis = ("The reported result is the maximum x value among the stored trajectory samples, "
                "rounded to ten significant digits. No measurement noise is included. "
                "The solver log, trajectory, and analysis record accompany this report.")
    if format_id == 0:
        return f"# Computational study\n\n## Setup\n{setup}\n\n## Numerical procedure\n{method}\n\n## Result and claim\n{claim}\n\n## Analysis\n{analysis}\n"
    if format_id == 1:
        return f"# Lab notebook\n\nResult recorded:\n{claim}\n\nCalculation notes:\n{method}\n\nExperimental context:\n{setup}\n\nProcessing notes:\n{analysis}\n"
    return f"# Results memo\n\nTo: study auditor\nSubject: population maximum\n\n{setup}\n\nReported conclusion:\n{claim}\n\nHow this number was produced:\n{analysis}\n\nRun configuration:\n{method}\n"


def trajectory_csv(run):
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["time", "x", "y"])
    for t, pair in zip(run["times"], run["values"]):
        writer.writerow([format(float(v), ".17g") for v in (t, *pair)])
    return out.getvalue()


def make_artifacts(study):
    run, case_id = study["run"], study["case_id"]
    role_content = [
        ("report", "text/markdown", render_report(study, study["format_id"])),
        ("solver_log", "text/plain", "Run completed successfully.\n" + configuration_text(run["config"]) + "\n"),
        ("trajectory", "text/csv", trajectory_csv(run)),
        ("analysis", "text/plain",
         f"Operation: maximum of stored x samples.\nResult: {study['reported_q']:.10g}\n"
         "Reported precision: ten significant digits.\n"
         f"Stored-sample peak time: {peak(run)['time']:.17g}\n"
         "Scope: numerical accuracy of the specified mathematical model.\n"),
    ]
    return {case_id + f"-a{index + 1}": {"role": role, "media_type": media,
            "content": content, "run_id": study["run_id"]}
            for index, (role, media, content) in enumerate(role_content)}


def make_study(seed, theta, category, run, ref, format_id):
    case_id = "study-" + digest({"seed": seed, "category": category, "version": VERSION})[:14]
    q = reported_value(run)
    study = {"case_id": case_id, "run_id": "run-" + digest({"case": case_id})[:14],
             "format_id": format_id, "format": FORMATS[format_id], "reported_q": q,
             "run": deepcopy(run),
             "private": {"seed": seed, "theta": list(theta), "category": category,
                         "reference_q": ref["q"], "reference_checks": ref["checks"],
                         "relative_error": error_fraction(q, ref["q"]),
                         "claim_valid": bool(truth_label(q, ref["q"])),
                         "cohort": "development", "tolerance": 0.05}}
    study["artifacts"] = make_artifacts(study)
    return study


def commission(log=None):
    """Retain every sweep record; never replace a system or relax an admission band."""
    catalog = {"version": VERSION, "cohort": "development", "seeds": list(SEEDS),
               "systems": [], "studies": [], "failures": [], "complete": False,
               "selection_rule": {"harmless": "0.005 <= error < 0.04, nearest 0.02",
                                  "consequential": "error > 0.06, nearest 0.10",
                                  "sound": "error < 0.001", "ties": "configuration order"}}
    backend = Backend()
    for system_index, seed in enumerate(SEEDS):
        bounds = np.asarray(BOUNDS)
        theta = np.random.default_rng(seed).uniform(bounds[:, 0], bounds[:, 1])
        system = {"seed": seed, "theta": theta.tolist(), "sweep": [], "selections": {}}
        catalog["systems"].append(system)
        try:
            ref = reference(theta)
            system["reference"] = ref
        except Exception as exc:
            catalog["failures"].append({"seed": seed, "stage": "reference", "error": str(exc)})
            continue
        configs = [("sound", configuration())]
        configs.extend(("integration", configuration("Euler", dt=dt)) for dt in EULER_STEPS)
        configs.extend(("sampling", configuration(times=output_grid(spacing, phase)))
                       for spacing in OUTPUT_SPACINGS for phase in PHASES)
        for order, (family, config) in enumerate(configs):
            run, cache_hit = backend.get(theta, config)
            item = {"order": order, "family": family, "config": config, "run": run,
                    "backend_cache_hit": cache_hit}
            if run["status"] == "success":
                q = reported_value(run)
                error = error_fraction(q, ref["q"])
                item.update(reported_q=q, error=error,
                            band="clearly_valid" if error < .04 else (
                                "clearly_invalid" if error > .06 else "borderline"))
            else:
                item["excluded_reason"] = "numerical failure"
            system["sweep"].append(item)
        for variant_index, category in enumerate(CATEGORIES):
            if category == "sound":
                selected = system["sweep"][0]
                options = [selected] if selected.get("error", 1) < .001 else []
            else:
                family = "integration" if category.endswith("integration") else "sampling"
                harmless = category.startswith("harmless")
                options = [item for item in system["sweep"] if item["family"] == family
                           and "error" in item and (
                               .005 <= item["error"] < .04 if harmless else item["error"] > .06)]
                options.sort(key=lambda item: (abs(item["error"] - (.02 if harmless else .10)),
                                               item["order"]))
            if not options:
                catalog["failures"].append({"seed": seed, "stage": "selection", "category": category})
                continue
            chosen = options[0]
            study = make_study(seed, theta, category, chosen["run"], ref,
                               (system_index + variant_index) % 3)
            catalog["studies"].append(study)
            system["selections"][category] = {"order": chosen["order"],
                                               "case_id": study["case_id"], "error": chosen["error"]}
        if log is not None:
            log("system_commissioned", seed=seed, selected=len(system["selections"]),
                reference_disagreement=ref["max_relative_disagreement"])
    catalog["complete"] = len(catalog["studies"]) == 30 and not catalog["failures"]
    return catalog


def validate_study(study):
    """Consistency checks when reloading private harness records."""
    if study["reported_q"] != reported_value(study["run"]):
        raise ValueError("claim no longer matches the computation")
    private = study["private"]
    if bool(private["claim_valid"]) != bool(truth_label(study["reported_q"], private["reference_q"])):
        raise ValueError("inconsistent label")
    if make_artifacts(study) != study["artifacts"]:
        raise ValueError("study artifacts were altered")
    # Fail early on non-JSON/nonfinite records.
    json.dumps(study, allow_nan=False)
    return study
