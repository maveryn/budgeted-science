"""Small audit policies consuming only public tools and purchased values."""
import math
import re

import numpy as np


COST = {"I": 3, "S": 2}
TOOL = {"I": "refine_integration", "S": "refine_sampling"}


def random_schedule(seed, credits=8):
    rng = np.random.default_rng(seed)
    actions = []
    while options := [a for a in ("I", "S") if COST[a] <= credits]:
        chosen = options[int(rng.integers(len(options)))]
        actions.append(chosen)
        credits -= COST[chosen]
    return actions


def convergence_estimate(records):
    """Sensitivity diagnostic, NOT a certified bound or truth-selected estimate.

    Fit Q(i,s)=Q_limit+a*2^-i+b*4^-s where both axes were refined.
    If only one was refined, extrapolate that axis only. First-order integration
    and second-order peak sampling are assumptions, not validated guarantees.
    """
    varied = [j for j in (0, 1) if len({r["levels"][j] for r in records}) > 1]
    if not records or not varied:
        return None
    matrix = [[1.0] + [(2.0 if j == 0 else 4.0) ** (-r["levels"][j]) for j in varied]
              for r in records]
    values = [r["q"] for r in records]
    coefficients, _, rank, _ = np.linalg.lstsq(np.asarray(matrix), values, rcond=None)
    if rank != len(varied) + 1 or not math.isfinite(coefficients[0]) or coefficients[0] <= 0:
        return None
    return {"q": float(coefficients[0]), "axes_extrapolated": varied,
            "rank": int(rank), "residual_rmse": float(np.sqrt(np.mean((np.asarray(matrix) @ coefficients - values)**2))),
            "certified": False}


def run_policy(call, policy, seed=0, *, estimator="last_run"):
    if estimator not in ("last_run", "extrapolation"):
        raise ValueError("unknown estimator")
    schedules = {"fixed_IIS": ["I", "I", "S"], "fixed_ISS": ["I", "S", "S"],
                 "random": random_schedule(seed), "adaptive_change": ["I", "S"]}
    if policy not in schedules:
        raise ValueError("unknown policy")
    schedule = list(schedules[policy])  # Random schedule fixed before inspecting evidence.
    status = call("budget", {})
    original = status["original_run_id"]
    inventory = call("list_artifacts", {})["artifacts"]
    analysis = next(a for a in inventory if a["role"] == "analysis")
    content = call("read_artifact", {"id": analysis["id"]})["content"]
    matches = re.findall(r"^Result:\s*(\S+)\s*$", content, re.MULTILINE)
    if len(matches) != 1:
        raise ValueError("expected one printed claim")
    reported = float(matches[0])
    initial = call("recompute_peak", {"run_id": original})
    records = [{"run_id": original, "q": initial["q"], "levels": [0, 0]}]
    levels, run_id, changes = [0, 0], original, {}
    executed, failure = [], None
    for index in range(4):
        if index == len(schedule):
            if policy != "adaptive_change" or index != 2:
                break
            # Both increments have been observed; buy another in the direction
            # with the larger absolute peak change per credit. Fixed tie: I.
            chosen = max(("I", "S"), key=lambda a: changes[a] / COST[a])
            schedule.append(chosen)
        action = schedule[index]
        result = call(TOOL[action], {"run_id": run_id})
        if result["status"] != "success":
            failure = result["status"]
            break
        changes[action] = abs(result["q"] - records[-1]["q"])
        levels[0 if action == "I" else 1] += 1
        run_id = result["run_id"]
        records.append({"run_id": run_id, "q": result["q"], "levels": list(levels)})
        executed.append(action)
    estimate = convergence_estimate(records)
    checked = records[-1]["q"]
    alternate = None if failure or estimate is None else (
        "ACCEPT" if abs(reported - estimate["q"]) / abs(estimate["q"]) <= .05 else "REJECT")
    verdict = "ABSTAIN" if failure else ("ACCEPT" if abs(reported - checked) / abs(checked) <= .05 else "REJECT")
    justification = f"Reported Q={reported:.10g}; {run_id} Q={checked:.17g}. Compare their relative difference with 0.05. This is not a certified bound."
    if estimator == "extrapolation":
        verdict = alternate or "ABSTAIN"
        justification = (f"Reported Q={reported:.10g}. Extrapolation unavailable; abstaining."
                         if estimate is None else
                         f"Reported Q={reported:.10g}; extrapolated peak={estimate['q']:.17g}. "
                         "Compare relative difference with 0.05. Extrapolation assumptions are not certified.")
    evidence = [analysis["id"], *[r["run_id"] for r in records]]
    call("submit", {"verdict": verdict,
         "diagnosis": "Budgeted incremental numerical comparison; residual numerical error remains possible.",
         "evidence_ids": evidence,
         "justification": justification})
    return {"policy": policy, "planned_initial_actions": schedules[policy], "actions": executed,
            "records": records, "observed_changes": changes, "failure": failure,
            "last_run_q": checked, "extrapolation": estimate, "extrapolated_verdict": alternate}
