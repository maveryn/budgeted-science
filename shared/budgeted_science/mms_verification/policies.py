"""Transparent CPU policies using only public metadata and purchased results."""
import math

from .catalog import relevant_family
from .numerics import MMS_GRIDS, ORDER_BAND, PROBLEMS, charge_units, relative_error

POLICIES = ("study_refinement", "fixed_diffusion", "fixed_suite", "study_aware", "early_reject")


def order_verdict(records, family):
    available = {r["grid"]: r["diagnostic_errors"]["rms_error"] for r in records
                 if r.get("kind") == "mms" and r.get("family") == family
                 and r.get("kernel") == "audited" and r.get("status") == "complete"}
    measured = []
    for a, b in zip(MMS_GRIDS, MMS_GRIDS[1:]):
        if a in available and b in available and min(available[a], available[b]) > 1e-12:
            measured.append(math.log2(available[a]/available[b]))
    if any(not ORDER_BAND[0] <= p <= ORDER_BAND[1] for p in measured):
        return "REJECT", measured
    return ("ACCEPT" if len(measured) == 2 else "ABSTAIN"), measured


def qoi_verdict(public, records, kernel):
    # Same plug-in estimator for all methods; comparison is not a rigorous bound.
    available = sorted((r for r in records if r.get("kind") == "study"
                        and r.get("kernel") == kernel and r.get("status") == "complete"
                        and r["grid"] >= 16), key=lambda r: r["grid"])
    if not available or available[-1]["grid"] < 32:
        return "ABSTAIN", None
    q = available[-1]["q"]
    discrepancy = relative_error(public["reported_q"], q)
    diagnostic = {"check_id": available[-1]["id"], "check_q": q,
                  "relative_difference": discrepancy,
                  "last_grid_change": abs(q-available[-2]["q"]) if len(available) > 1 else None,
                  "interpretation": "Plug-in numerical comparison, not a certified error bound."}
    return ("ACCEPT" if discrepancy <= public["relative_tolerance"] else "REJECT"), diagnostic


def run_policy(name, public, call):
    if name not in POLICIES:
        raise ValueError("unknown policy")
    family = relevant_family(public["problem"])
    records, responses = [], []
    remaining = public["budget"]["remaining"]
    sequence = 0

    def purchase(action, **args):
        nonlocal remaining, sequence
        # Original numerical result is free to retrieve using the same action.
        is_original = (action == "run_study" and args.get("kernel") == "audited"
                       and args["grid"] == public["original_grid"])
        cost = 0 if is_original else charge_units(args["grid"])/289
        if cost > remaining+1e-12:
            return None
        sequence += 1
        response = call(f"call-{sequence:03d}", action, **args)
        responses.append(response)
        remaining = response["budget"]["remaining"]
        if response["ok"]:
            record = response["result"]
            records.append(record)
            return record
        return None

    if name == "study_refinement":
        for grid in (16, 32, 64):
            purchase("run_study", grid=grid, kernel="audited")
    else:
        families = list(PROBLEMS) if name == "fixed_suite" else ["diffusion" if name == "fixed_diffusion" else family]
        for diagnostic in families:
            for grid in MMS_GRIDS:
                purchase("run_mms", family=diagnostic, grid=grid, kernel="audited")
                # Falsifies this explicitly conjunctive finite-grid criterion;
                # does not claim to diagnose asymptotic order or QoI accuracy.
                if name == "early_reject" and order_verdict(records, family)[0] == "REJECT":
                    break
        # The plug-in verdict only uses this grid. Do not buy an unused 16-grid
        # check just to make a complete workflow artificially more expensive.
        purchase("run_study", grid=32, kernel="independent")
    qoi, qdiag = qoi_verdict(public, records, "audited" if name == "study_refinement" else "independent")
    order, observed = order_verdict(records, family)
    sequence += 1
    response = call(f"call-{sequence:03d}", "submit", qoi=qoi, order=order,
                    evidence_ids=list(dict.fromkeys(r["id"] for r in records)),
                    explanation="CPU rule; QoI plug-in comparison and relevant finite-grid order criterion evaluated separately.")
    if not response["ok"]:
        raise RuntimeError("policy submission rejected: "+response.get("error", "unknown"))
    return {"qoi_comparison": qdiag, "purchased_orders": observed,
            "tool_responses": len(responses)+1, "policy": name}
