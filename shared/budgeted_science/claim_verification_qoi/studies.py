"""Actual numerical reports; private truth is separate from public artifacts."""
from copy import deepcopy
import csv
import io
import math
from uuid import uuid4

from ..agents.records import digest
from . import VERSION
from .numerics import qois

QUANTITIES = ("peak_height", "peak_time", "cumulative")
TOLERANCES = {"peak_height": ("relative", (.01, .05)),
              "peak_time": ("absolute", (.04, .16)),
              "cumulative": ("relative", (.01, .05))}
DESCRIPTIONS = {
    "peak_height": "maximum prey population over [0,8]",
    "peak_time": "time of the unique global maximum prey population over [0,8]",
    "cumulative": "cumulative prey population integral over [0,8]"}
ANALYSIS = {
    "peak_height": "Maximum of stored x samples.",
    "peak_time": "Time of the earliest largest stored x sample; no sub-sample fitting.",
    "cumulative": "Composite trapezoidal quadrature of stored x samples on their actual time grid."}


def assess(reported, reference, kind, tolerance):
    if (kind not in ("relative", "absolute") or
            any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                for v in (reported, reference, tolerance)) or tolerance <= 0):
        raise ValueError("invalid numerical claim")
    scale = abs(reference) if kind == "relative" else 1.0
    if scale == 0:
        raise ValueError("relative tolerance needs nonzero reference")
    absolute_error = abs(reported-reference)
    allowance = tolerance*scale
    valid = absolute_error <= allowance + 8*math.ulp(max(abs(reported), abs(reference), allowance))
    return {"claim_valid": valid, "absolute_error": absolute_error,
            "normalized_error": absolute_error/allowance, "absolute_tolerance": allowance}


def report(study):
    c, cfg = study["claim"], study["run"]["config"]
    requirement = (f"+/-{100*c['tolerance']:g}% relative to the mathematical-model value"
                   if c["tolerance_kind"] == "relative" else f"+/-{c['tolerance']:g} time units")
    parts = {
        "Setup": "Coupled two-population mathematical model; x is prey, y is predator. "
                 "Initial populations x(0)=10, y(0)=5; interval [0,8]. Units are dimensionless. "
                 "No measurement noise or physical-validation claim. The physical setup cannot be changed.",
        "Claim": f"The {c['description']} is {c['reported']:.10g}, accurate within {requirement}.",
        "Numerics": f"{cfg['method']}; integration step {cfg['dt']:g}; output spacing "
                    f"{cfg['output_step']:g}; output offset {cfg['output_offset']:g} times that spacing. "
                    "Endpoints are included. Numerical interpolation between integration nodes is piecewise linear.",
        "Analysis": ANALYSIS[c['quantity']] + " Reported value rounded to ten significant digits."}
    orders = (("Setup", "Numerics", "Claim", "Analysis"),
              ("Claim", "Analysis", "Numerics", "Setup"),
              ("Setup", "Claim", "Analysis", "Numerics"))
    title = ("Computational study", "Lab notebook", "Results memo")[study["format_id"]]
    return "# " + title + "\n\n" + "\n\n".join("## " + k + "\n" + parts[k] for k in orders[study["format_id"]]) + "\n"


def trajectory_text(run):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("time", "x", "y"))
    for t, pair in zip(run["times"], run["values"]):
        writer.writerow([format(float(v), ".17g") for v in (t, *pair)])
    return stream.getvalue()


def artifacts(study):
    c, run = study["claim"], study["run"]
    content = [("report", report(study)), ("solver_log", str(run["config"]) + "\nStatus: success\n"),
               ("trajectory", trajectory_text(run)),
               ("analysis", ANALYSIS[c["quantity"]] + f"\nResult: {c['reported']:.10g}\n")]
    return {study["case_id"] + f"-a{i}": {"role": role, "run_id": study["run_id"], "content": text}
            for i, (role, text) in enumerate(content, 1)}


def make_study(seed, theta, cohort, profile, run, ref, quantity, tolerance, format_id, physical_id=None):
    kind, allowed = TOLERANCES[quantity]
    if tolerance not in allowed or format_id not in range(3):
        raise ValueError("unsupported claim/format")
    if quantity == "peak_time" and not ref["peak_time_eligible"]:
        raise ValueError("reference peak time is not eligible")
    numerical = qois(run)
    # Never hash the small enumerable seed space into public identifiers.
    # Saved catalogs retain the private pairing map for exact replay.
    physical_id = physical_id or "physical-" + uuid4().hex
    case_id = "study-" + digest([VERSION, physical_id, quantity, tolerance])[:16]
    claim = {"quantity": quantity, "description": DESCRIPTIONS[quantity],
             "reported": float(format(numerical[quantity], ".10g")),
             "tolerance_kind": kind, "tolerance": tolerance}
    truth = assess(claim["reported"], ref["qois"][quantity], kind, tolerance)
    study = {"case_id": case_id, "physical_study_id": physical_id,
             "run_id": "run-" + digest([physical_id, "original"])[:16],
             "claim": claim, "run": deepcopy(run), "format_id": format_id,
             "private": {"seed": seed, "theta": list(theta), "cohort": cohort, "profile": profile,
                         "reference": ref["qois"][quantity], **truth}}
    study["artifacts"] = artifacts(study)
    return study


def validate_study(study):
    c = study["claim"]
    expected = float(format(qois(study["run"])[c["quantity"]], ".10g"))
    if expected != c["reported"] or artifacts(study) != study["artifacts"]:
        raise ValueError("study artifacts no longer match actual computation")
    truth = assess(c["reported"], study["private"]["reference"], c["tolerance_kind"], c["tolerance"])
    if any(truth[k] != study["private"][k] for k in truth):
        raise ValueError("study truth no longer matches printed claim")
    return study
