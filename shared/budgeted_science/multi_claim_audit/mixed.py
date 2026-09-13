"""Six heterogeneous claims with shared evidence; preserves the original toy."""
from copy import deepcopy
import math

import numpy as np

from . import core as original

VERSION = "predator-prey-mixed-claims-v1"
REPORT_THETA = original.REPORT_THETA
INTERVENTION_THETA = (1.0, 0.088, 1.4)
SHUFFLE_SEED = 731
GRID = np.arange(17, dtype=float) / 2


def printed(value):
    return float(format(float(value), ".10g"))


def table_value(table, variable, time):
    return float(np.asarray(table["values"])[list(table["times"]).index(time), ("x", "y").index(variable)])


def field(table):
    times = np.asarray(table["times"], dtype=float)
    values = np.asarray(table["values"], dtype=float)
    if times.shape != (16,) or not np.array_equal(times, GRID[1:]) or values.shape != (16, 2):
        raise ValueError("complete half-unit trajectory required")
    if not np.isfinite(values).all() or np.min(values) <= 0:
        raise ValueError("finite positive population outputs required")
    return np.vstack([[10.0, 5.0], values])


def quantity(kind, baseline=None, intervention=None, observations=None):
    """Arithmetic only. Inputs must already be acquired; never calls a solver."""
    obs = observations or {}
    if kind == "numerical_point":
        return table_value(baseline, "x", .5) if baseline is not None else None
    if kind == "cumulative_abundance":
        return float(np.trapezoid(field(baseline)[:, 0], GRID)) if baseline is not None else None
    if kind == "intervention_effect":
        if baseline is None or intervention is None:
            return None
        peak = float(np.max(field(baseline)[:, 0]))
        return float((peak - np.max(field(intervention)[:, 0])) / peak)
    if kind == "target_agreement":
        return obs.get(("x", 4.0))
    if kind == "target_recovery":
        if ("x", 4.0) not in obs or ("x", 6.0) not in obs:
            return None
        denominator = obs["x", 4.0]
        return obs["x", 6.0] / denominator - 1 if denominator > 0 else None
    if kind == "target_composition":
        if ("x", 6.0) not in obs or ("y", 6.0) not in obs:
            return None
        denominator = obs["x", 6.0]
        return obs["y", 6.0] / denominator if denominator > 0 else None
    raise ValueError("unknown scientific quantity")


def classify(claim, value):
    if not isinstance(value, (int, float, np.number)) or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError("finite numerical quantity required")
    if claim["operator"] == "relative_error_le":
        result = original.classify(claim["reported_value"], value, claim["relative_tolerance"])
        return {**result, "criterion_margin": claim["relative_tolerance"] - result["relative_error"]}
    if claim["operator"] == "ge":
        margin = value - claim["threshold"]
        return {"criterion_margin": margin, "verdict": "ACCEPT" if margin >= -1e-14 else "REJECT"}
    raise ValueError("unknown claim operator")


def build_study():
    base = original.build_study()
    config = original.harder_config(32)
    intervention = original._solve_low(INTERVENTION_THETA, config)
    intervention_table = {"times": list(config.working_times), "values": intervention.sample(config.working_times).tolist()}
    low = base["public"]["original"]
    effect = quantity("intervention_effect", low, intervention_table)
    # Report a conservative whole-percentage lower bound from the actual Euler
    # estimate, not a threshold chosen to match the private reference verdict.
    threshold = math.floor(100 * effect) / 100
    values = {"numerical_point": printed(quantity("numerical_point", low)),
              "cumulative_abundance": printed(quantity("cumulative_abundance", low)),
              "target_agreement": printed(table_value(low, "x", 4)),
              "target_composition": printed(table_value(low, "y", 6) / table_value(low, "x", 6))}
    specs = [
        {"kind": "numerical_point", "scope": "specified_model", "operator": "relative_error_le",
         "reported_value": values["numerical_point"], "relative_tolerance": .05,
         "text": f"The reported baseline prey population x(0.5)={values['numerical_point']:.10g} is within 5% of the accurately integrated model at the report parameters."},
        {"kind": "target_agreement", "scope": "fixed_target", "operator": "relative_error_le",
         "reported_value": values["target_agreement"], "relative_tolerance": .05,
         "text": f"The reported prediction x(4)={values['target_agreement']:.10g} is within 5% of the fixed target's noise-free prey population at t=4."},
        {"kind": "cumulative_abundance", "scope": "specified_model", "operator": "relative_error_le",
         "reported_value": values["cumulative_abundance"], "relative_tolerance": .05,
         "text": f"The reported cumulative prey index A={values['cumulative_abundance']:.10g} is within 5% of the accurately integrated baseline model's index. A is trapezoidal integration of x over the fixed grid 0,0.5,...,8; it is not the continuous-time integral."},
        {"kind": "intervention_effect", "scope": "specified_model", "operator": "ge", "threshold": threshold,
         "text": f"Increasing theta2 by 10%, from 0.08 to 0.088 with other parameters unchanged, reduces the model's grid-sampled peak prey population by at least {threshold*100:g}%. Define R=(max_grid x_baseline-max_grid x_intervention)/max_grid x_baseline on 0,0.5,...,8; the assertion is R>={threshold:g}."},
        {"kind": "target_recovery", "scope": "fixed_target", "operator": "ge", "threshold": .20,
         "text": "The fixed target's noise-free prey population recovers by at least 20% between t=4 and t=6: G=x_target(6)/x_target(4)-1 >= 0.20. This is an assertion about the target, not the baseline model's predicted trend."},
        {"kind": "target_composition", "scope": "fixed_target", "operator": "relative_error_le",
         "reported_value": values["target_composition"], "relative_tolerance": .10,
         "text": f"The reported predator-to-prey ratio y(6)/x(6)={values['target_composition']:.10g} is within 10% of the fixed target's noise-free ratio at t=6."},
    ]
    order = np.random.default_rng(SHUFFLE_SEED).permutation(len(specs)).tolist()
    claims = [{"id": f"C{i+1}", **specs[j]} for i, j in enumerate(order)]
    refs = deepcopy(base["private"]["references"])
    refs["intervention"] = original.checked_reference(INTERVENTION_THETA, config)
    target_obs = {(var, t): table_value(refs["target"], var, t) for var, t in (("x", 4.), ("x", 6.), ("y", 6.))}
    truth = {}
    for claim in claims:
        ref_value = quantity(claim["kind"], refs["numerical"], refs["intervention"], target_obs)
        truth[claim["id"]] = {"reference_value": ref_value, **classify(claim, ref_value)}
    public = {"claims": claims, "report_parameters": list(REPORT_THETA),
              "intervention_parameters": list(INTERVENTION_THETA), "original": deepcopy(low),
              "environment": config.public(),
              "intervention_summary": {"fidelity": "low", "step": .1,
                  "baseline_grid_peak": printed(np.max(field(low)[:, 0])),
                  "intervention_grid_peak": printed(np.max(field(intervention_table)[:, 0])),
                  "estimated_peak_reduction": printed(effect)}}
    public["report"] = ("Predator-prey study: numerical adequacy, intervention and target agreement\n\n"
        "Initial populations are (10,5); horizon [0,8]. Baseline model parameters are (1,0.08,1.4). "
        "The intervention changes only theta2 to 0.088. The baseline table and intervention summary "
        "come from actual Euler calculations at step 0.1. The intervention lower bound rounds its "
        "estimated percentage reduction down to a whole percentage point. All aggregate and peak "
        "quantities are defined on 0,0.5,...,8, including the known initial state. "
        "The target's parameters are not asserted to equal the report parameters. The report separately "
        "asserts target recovery of at least 20%, which must be checked against the target. "
        "The order of the following six claims does not indicate priority.\n\n" +
        "\n\n".join(c["id"] + ": " + c["text"] for c in claims))
    private = deepcopy(base["private"])
    private.update(references=refs, truth=truth, shuffle_seed=SHUFFLE_SEED, permutation=order,
                   intervention_original_artifact=intervention.artifact(),
                   intervention_original_table=intervention_table,
                   case_status="development: same exploratory target; heterogeneous claims commissioned before agent run")
    return {"version": VERSION, "public": public, "private": private}


class Audit(original.Audit):
    """Reuse original purchase/scoring mechanics, with a separate study version."""
    def __init__(self, study, log=None, *, budget=32):
        if study["version"] != VERSION or type(budget) is not int or budget not in (32, 52):
            raise ValueError("mixed study requires 32 credits (or 52 for the CPU diagnostic)")
        self._study = deepcopy(study)
        self.public = deepcopy(study["public"])
        self.public["environment"]["budget"] = float(budget)
        self._environment = original.PlanningEnvironment(study["private"]["target_parameters"],
            original.harder_config(budget=budget), log=log, noise_seed=study["private"]["noise_seed"])
        self._tools = self._environment.tools
        self.submission = None


def fixed_policy(call, public):
    """Fixed, presentation-order-independent acquisition; arithmetic on purchases.

    At 32, a baseline high solve and x(4),x(6) measurements fit exactly.
    The same order at 52 adds the intervention high solve and y(6) measurement.
    Missing inputs cause abstention; low predictions are not treated as exact.
    """
    simulations, observations, ids = {}, {}, []
    actions = [("simulate_high", {"theta": public["report_parameters"]}, "baseline"),
               ("measure_target", {"variable": "x", "time": 4.}, None),
               ("measure_target", {"variable": "x", "time": 6.}, None),
               ("simulate_high", {"theta": public["intervention_parameters"]}, "intervention"),
               ("measure_target", {"variable": "y", "time": 6.}, None)]
    for name, args, label in actions:
        result = call(name, **args)
        if result["status"] == "success":
            if label:
                simulations[label] = result
                ids.append(result["result_id"])
            else:
                observations[args["variable"], args["time"]] = result["value"]
                ids.append(result["record_id"])
    verdicts, estimates = {}, {}
    for claim in public["claims"]:
        value = quantity(claim["kind"], simulations.get("baseline"), simulations.get("intervention"), observations)
        estimates[claim["id"]] = value
        try:
            verdicts[claim["id"]] = classify(claim, value)["verdict"] if value is not None else "ABSTAIN"
        except ValueError:
            verdicts[claim["id"]] = "ABSTAIN"
    return call("submit", verdicts=verdicts, evidence_ids=ids,
                explanation=f"Fixed acquisition and plug-in arithmetic on purchased evidence. No uncertainty certificate. Estimated claim quantities: {estimates}")
