"""CPU policies using only the public ``call(name, arguments)`` interface.

No numerical backend is imported. Raw qois remain stored-sample quantities.
The common estimator ranks independent check runs by (dt/8)**p + (output_step/8)**s, with
p=s=1 for peak_time for both methods: the piecewise-linear argmax location is
generally first-order in dt. For height/cumulative, p=1 for Euler, p=2 for
explicit-midpoint RK2, and s=2. This proxy assumes comparable leading-error coefficients;
it is not an error bound. Ranking never uses agreement with the reported claim.
For peak_height/cumulative only, a matching-method, matching-output-schedule
coarser run permits unvalidated Richardson extrapolation with the known p.
Matching output schedules do not guarantee aligned interpolation-error coefficients.
Sampled peak times are not extrapolated or interpolated.

Relative verdict tolerance is tolerance * abs(estimated quantity). A successful
independent check must supply the primary estimate for ACCEPT/REJECT; otherwise
submit ABSTAIN. The original may only be a compatible Richardson coarse partner.
Adaptive scores are discrepancy-guided heuristics, not expected information
gains: paired claim-specific changes/tolerance, times a refinement fraction,
divided by quoted credits. Two original-axis probes precede this ranking.
"""

from copy import deepcopy
import math
from numbers import Real
import random


ORDERS = {"Euler": 1, "RK2": 2}
QUANTITIES = ("peak_height", "peak_time", "cumulative")
DT_MENU = (.02, .04, .08, .16, .32)
OUTPUT_MENU = (.02, .04, .08, .16, .32, .64, 1.28)
POLICIES = ("fixed_rk2", "fixed_euler", "fixed_dense_output", "random", "adaptive")
FIXED = {
    "fixed_rk2": ("RK2", .04, .04, 0.),
    "fixed_euler": ("Euler", .02, .04, 0.),
    "fixed_dense_output": ("RK2", .08, .02, 0.),
}
CONFIG_KEYS = ("method", "dt", "output_step", "output_offset")
ASSUMPTIONS = [
    "Comparable leading-error coefficients in the dimensionless resolution proxy.",
    "Height/cumulative integration: Euler order 1, RK2 order 2; asymptotic regime unvalidated.",
    "Piecewise-linear peak-time location: integration order 1 for both methods.",
    "Stored peak-time sampling order 1; peak-height/cumulative sampling order 2.",
    "Richardson only for non-time qois, same method and identical output schedule.",
    "Matching output schedules do not guarantee aligned interpolation-error coefficients.",
    "All estimates are numerical heuristics, not certified accuracy or confidence bounds.",
]


def _finite(value):
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value)


def _json_diagnostics(result):
    """Replace nonfinite diagnostic numbers by null, retaining their locations.

    This is serialization only: unusable qois are rejected before estimation.
    Explicit metadata distinguishes nonfinite values from genuinely absent data.
    """
    replacements = []

    def clean(value, path):
        if isinstance(value, float) and not math.isfinite(value):
            replacements.append({"path": path, "value": str(value)})
            return None
        if isinstance(value, dict):
            return {key: clean(item, path + [key]) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [clean(item, path + [index]) for index, item in enumerate(value)]
        return value

    cleaned = clean(result, [])
    if replacements:
        cleaned["nonfinite_diagnostics"] = replacements
    return cleaned


def _config(value):
    if not isinstance(value, dict) or value.get("method") not in ORDERS:
        raise ValueError("unsupported method/configuration")
    result = {key: value[key] for key in CONFIG_KEYS}
    if not all(_finite(result[key]) for key in CONFIG_KEYS[1:]):
        raise ValueError("nonfinite configuration")
    dt, step, offset = (float(result[key]) for key in CONFIG_KEYS[1:])
    if not (.01 <= dt <= .32 and .01 <= step <= 2 and 0 <= offset < 1):
        raise ValueError("configuration outside public bounds")
    if not math.isclose(8 / dt, round(8 / dt), rel_tol=0, abs_tol=1e-8):
        raise ValueError("dt must divide the horizon")
    return dict(method=result["method"], dt=dt, output_step=step, output_offset=offset)


def _key(config):
    return tuple(config[key] for key in CONFIG_KEYS)


def _schedule(config):
    return config["output_step"], config["output_offset"]


def _claim(value):
    if not isinstance(value, dict) or value.get("quantity") not in QUANTITIES:
        raise ValueError("unsupported claim quantity")
    if value.get("tolerance_kind") not in ("absolute", "relative"):
        raise ValueError("unsupported tolerance kind")
    if not _finite(value.get("reported")) or not _finite(value.get("tolerance")) or value["tolerance"] <= 0:
        raise ValueError("invalid reported quantity/tolerance")
    return deepcopy(value)


def _record(response, run_id, expected=None):
    if response.get("status") != "success" or not isinstance(run_id, str) or not run_id:
        raise ValueError("successful identified run required")
    config = _config(response["config"])
    if expected is not None and _key(config) != _key(expected):
        raise ValueError("returned configuration differs from requested check")
    qois = response["qois"]
    if not isinstance(qois, dict) or not all(_finite(qois.get(q)) for q in QUANTITIES):
        raise ValueError("finite stored-sample qois required")
    return {"run_id": run_id, "status": "success", "config": config,
            "qois": {q: float(qois[q]) for q in QUANTITIES}}


def _quality(config, quantity):
    p = 1 if quantity == "peak_time" else ORDERS[config["method"]]
    s = 1 if quantity == "peak_time" else 2
    return (config["dt"] / 8) ** p + (config["output_step"] / 8) ** s


def _allowance(claim, estimate):
    return claim["tolerance"] * (abs(estimate) if claim["tolerance_kind"] == "relative" else 1.)


def estimate_claim(claim, runs, original_run_id=None, *, original_config=None):
    """Apply the identical purchased-evidence estimator for every policy.

    ``runs`` contain run_id, status, config and the unmodified three qois.
    Ties depend on configuration/run ID, never closeness to the printed claim.
    Only successful configs distinct from the original can supply the primary
    estimate. Pass original_config when its read failed so config aliases remain
    excluded. The original can contribute only as a compatible coarse partner.
    """
    result = {"verdict": "ABSTAIN", "diagnosis": "Insufficient independent numerical evidence.",
              "estimate": None, "evidence_ids": [], "ranking": [], "richardson": None,
              "assumptions": list(ASSUMPTIONS), "certified": False, "discarded_runs": []}
    try:
        claim = _claim(claim)
        if original_config is not None:
            original_config = _config(original_config)
    except (ValueError, KeyError, TypeError) as exc:
        result["diagnosis"] = str(exc)
        return _json_diagnostics(result)
    records = {}
    for run in runs:
        try:
            record = _record(run, run.get("run_id"))
            records[record["run_id"]] = record
        except (ValueError, KeyError, TypeError) as exc:
            result["discarded_runs"].append({"run_id": run.get("run_id"), "reason": str(exc)})
    ordered = sorted(records.values(), key=lambda r: (_quality(r["config"], claim["quantity"]),
                                                     _key(r["config"]), r["run_id"]))
    original = records.get(original_run_id)
    if original_config is None and original is not None:
        original_config = original["config"]
    independent = [r for r in ordered if r["run_id"] != original_run_id
                   and (original_config is None or _key(r["config"]) != _key(original_config))]
    eligible_ids = {r["run_id"] for r in independent}
    result["evidence_ids"] = sorted(records)
    result["ranking"] = [{"run_id": r["run_id"], "quality_proxy": _quality(r["config"], claim["quantity"]),
                          "primary_eligible": r["run_id"] in eligible_ids,
                          "raw_quantity": r["qois"][claim["quantity"]]} for r in ordered]
    if not independent:
        return _json_diagnostics(result)
    fine = independent[0]
    cfg = fine["config"]
    value = fine["qois"][claim["quantity"]]
    result.update(selected_run_id=fine["run_id"], raw_estimate=value)
    coarse = [r for r in ordered if r["config"]["method"] == cfg["method"]
              and _schedule(r["config"]) == _schedule(cfg)
              and r["config"]["dt"] > cfg["dt"] * (1 + 1e-10)]
    if coarse and claim["quantity"] != "peak_time":
        partner = min(coarse, key=lambda r: (r["config"]["dt"], r["run_id"]))
        ratio = partner["config"]["dt"] / cfg["dt"]
        p = ORDERS[cfg["method"]]
        correction = (value - partner["qois"][claim["quantity"]]) / (ratio ** p - 1)
        value += correction
        result["richardson"] = {"fine_run_id": fine["run_id"], "coarse_run_id": partner["run_id"],
                                "order": p, "ratio": ratio, "correction": correction,
                                "validated": False}
    if not _finite(value):
        result["diagnosis"] = "Nonfinite extrapolation; no defensible estimate."
        return _json_diagnostics(result)
    result["estimate"] = value
    allowance = _allowance(claim, value)
    difference = abs(value - claim["reported"])
    if not _finite(allowance) or (claim["tolerance_kind"] == "relative" and allowance == 0):
        result["diagnosis"] = "Relative scale is zero or tolerance scale is nonfinite."
        return _json_diagnostics(result)
    slack = 8 * math.ulp(max(abs(value), abs(claim["reported"]), allowance))
    verdict = "ACCEPT" if difference <= allowance + slack else "REJECT"
    result.update(verdict=verdict, absolute_difference=difference, absolute_tolerance=allowance,
                  normalized_difference=difference / allowance,
                  diagnosis="Claim agrees with the numerical estimate." if verdict == "ACCEPT"
                  else "Claim differs from the numerical estimate beyond tolerance.")
    return _json_diagnostics(result)


def _menu():
    return [dict(method=method, dt=dt, output_step=step, output_offset=offset)
            for method in ORDERS for dt in DT_MENU for step in OUTPUT_MENU for offset in (0., .25)]


def _axis_options(config, parent_id):
    for axis, field in (("integration", "dt"), ("sampling", "output_step")):
        for factor in (.5, 2.):
            trial = {**config, field: config[field] * factor}
            try:
                trial = _config(trial)
            except ValueError:
                continue
            yield {"config": trial, "axis": axis, "parent_run_id": parent_id,
                   "direction": "refine" if factor < 1 else "coarsen", "factor": factor}
    yield {"config": {**config, "output_offset": .25 if config["output_offset"] == 0 else 0.},
           "axis": "sampling", "parent_run_id": parent_id, "direction": "phase", "factor": 1.}
    yield {"config": {**config, "method": "RK2" if config["method"] == "Euler" else "Euler"},
           "axis": "method", "parent_run_id": parent_id, "direction": "crosscheck", "factor": 1.}


def _signals(claim, runs, estimate):
    width = _allowance(claim, estimate if estimate is not None else claim["reported"])
    if not _finite(width) or width <= 0:
        width = math.ulp(max(1., abs(claim["reported"])))
    pairs = []
    for i, a in enumerate(runs):
        for b in runs[i + 1:]:
            ac, bc = a["config"], b["config"]
            if ac["method"] == bc["method"] and _schedule(ac) == _schedule(bc) and ac["dt"] != bc["dt"]:
                axis = "integration"
            elif ac["method"] == bc["method"] and ac["dt"] == bc["dt"] and _schedule(ac) != _schedule(bc):
                axis = "sampling"
            elif ac["method"] != bc["method"] and ac["dt"] == bc["dt"] and _schedule(ac) == _schedule(bc):
                axis = "method"
            else:
                continue
            change = abs(a["qois"][claim["quantity"]] - b["qois"][claim["quantity"]])
            pairs.append({"axis": axis, "run_ids": [a["run_id"], b["run_id"]],
                          "absolute_change": change, "normalized_change": min(change / width, 1e12)})
    weights = {}
    for axis in ("integration", "sampling", "method"):
        values = [p["normalized_change"] for p in pairs if p["axis"] == axis]
        weights[axis] = max(max(values), 1e-6) if values else 1.
    return weights, pairs


class _Session:
    def __init__(self, call):
        self.call = call
        self.trace, self.acquisitions, self.decisions = [], [], []
        self.runs, self.attempted, self.quotes = {}, set(), {}
        self.stop_reason = None

    def ask(self, name, arguments):
        # Execution/deadline/ledger failures belong to the runner. Only explicit
        # status responses represent completed scientific actions here.
        response = self.call(name, deepcopy(arguments))
        if not isinstance(response, dict):
            response = {"status": "invalid_response"}
        self.trace.append({"name": name, "arguments": deepcopy(arguments), "response": deepcopy(response)})
        return response

    def remaining(self):
        response = self.ask("budget", {})
        value = response.get("remaining")
        if response.get("status") != "success" or not _finite(value) or value < 0:
            self.stop_reason = "Public budget unavailable."
            return None
        return min(float(value), 8.)

    def quote(self, config, remaining, *, reuse=False):
        key = _key(config)
        if key in self.attempted:
            return None
        if key not in self.quotes:
            self.quotes[key] = self.ask("quote_check", config)
        quote = self.quotes[key]
        if quote.get("status") != "success":
            return None
        if quote.get("episode_reuse"):
            return quote if reuse else None
        work, credits = quote.get("work"), quote.get("credits")
        if isinstance(work, bool) or not isinstance(work, int) or not 0 < work <= 800:
            return None
        if not _finite(credits) or not math.isclose(credits, work / 100, rel_tol=0, abs_tol=1e-12):
            return None
        return quote if work <= math.floor(remaining * 100 + 1e-8) else None

    def purchase(self, config, quote, stage):
        self.attempted.add(_key(config))
        response = self.ask("run_check", config)
        acquisition = {"stage": stage, "config": deepcopy(config), "quote": deepcopy(quote),
                       "response": deepcopy(response), "used_by_estimator": False}
        self.acquisitions.append(acquisition)
        if response.get("status") != "success":
            return
        try:
            record = _record(response, response.get("run_id"), config)
        except (ValueError, KeyError, TypeError) as exc:
            acquisition["evidence_error"] = str(exc)
            return
        self.runs[record["run_id"]] = record
        acquisition["used_by_estimator"] = True
        # Compact run results already carry all qois; a failed table read does
        # not discard those purchased values. Full table responses stay in trace.
        read = self.ask("read_run", {"run_id": record["run_id"]})
        acquisition["read_status"] = read.get("status")
        if read.get("status") == "success":
            try:
                reread = _record(read, record["run_id"], config)
                if reread["qois"] != record["qois"]:
                    raise ValueError("read_run qois disagree with run_check")
            except (ValueError, KeyError, TypeError) as exc:
                self.runs.pop(record["run_id"], None)
                acquisition.update(used_by_estimator=False, evidence_error=str(exc))


def _adaptive(session, claim, original_config, original_id):
    initial_budget = session.remaining()
    if initial_budget is None:
        return
    # Reserve room for both axes when possible. Prefer half-spacing probes,
    # then a phase probe, then double-spacing; never spend > half initial budget.
    options = list(_axis_options(original_config, original_id))
    preference = {"refine": 0, "phase": 1, "coarsen": 2}
    for axis in ("integration", "sampling"):
        remaining = session.remaining()
        if remaining is None:
            return
        ranked = []
        for option in options:
            if option["axis"] != axis:
                continue
            quote = session.quote(option["config"], min(remaining, initial_budget / 2))
            if quote is not None:
                ranked.append({**option, "quote": quote})
        ranked.sort(key=lambda a: (preference[a["direction"]], a["quote"]["credits"], _key(a["config"])))
        session.decisions.append({"stage": "probe_" + axis, "ranked": deepcopy(ranked)})
        if ranked:
            session.purchase(ranked[0]["config"], ranked[0]["quote"], "probe_" + axis)
    while True:
        remaining = session.remaining()
        if remaining is None:
            return
        records = list(session.runs.values())
        estimator = estimate_claim(claim, records, original_id, original_config=original_config)
        weights, pairs = _signals(claim, records, estimator["estimate"])
        options = [a for r in records for a in _axis_options(r["config"], r["run_id"])]
        if not records:
            options = list(_axis_options(original_config, original_id))
        ranked = {}
        for option in options:
            config, axis = option["config"], option["axis"]
            if option["direction"] == "coarsen" and any(p["axis"] == axis for p in pairs):
                continue  # Once measured, refine an axis instead of buying more coarse probes.
            quote = session.quote(config, remaining)
            if quote is None:
                continue
            order = 1 if claim["quantity"] == "peak_time" else (ORDERS[config["method"]] if axis == "integration" else 2)
            fraction = 1 - option["factor"] ** order if option["direction"] == "refine" else .5
            score = weights[axis] * fraction / quote["credits"]
            item = {**option, "quote": quote, "normalized_signal": weights[axis],
                    "refinement_fraction": fraction, "score": score}
            key = _key(config)
            if key not in ranked or score > ranked[key]["score"]:
                ranked[key] = item
        # When axis-isolating options are exhausted/unaffordable, explore the
        # finite public menu. Joint changes are not attributed to either axis.
        if not ranked:
            for config in _menu():
                quote = session.quote(config, remaining)
                if quote is not None:
                    ranked[_key(config)] = {"config": config, "quote": quote, "axis": "joint",
                                           "parent_run_id": None, "direction": "menu_fallback",
                                           "normalized_signal": max(weights.values()), "refinement_fraction": .25,
                                           "score": .25 * max(weights.values()) / quote["credits"]}
        ordered = sorted(ranked.values(), key=lambda a: (-a["score"], _key(a["config"])))
        session.decisions.append({"stage": "adaptive", "remaining": remaining, "axis_weights": weights,
                                  "observed_pairs": pairs, "ranked": deepcopy(ordered)})
        if not ordered:
            session.stop_reason = "No affordable unattempted check remains."
            return
        choice = ordered[0]
        session.purchase(choice["config"], choice["quote"], "adaptive")


def run_policy(call, policy, seed=0):
    """Submit once and return JSON-finite diagnostics; tool exceptions propagate."""
    if policy not in POLICIES:
        raise ValueError("unknown CPU policy")
    # Construct/shuffle before describe or any access to original evidence.
    random_plan = _menu() if policy == "random" else []
    if random_plan:
        random.Random(seed).shuffle(random_plan)
    session = _Session(call)
    description = session.ask("describe", {})
    original_id = description.get("original_run_id")
    claim, original_config = None, None
    if description.get("status") == "success":
        try:
            claim = _claim(description.get("claim"))
            original_config = _config(description["original_config"])
        except (ValueError, KeyError, TypeError) as exc:
            session.stop_reason = str(exc)
        else:
            read = session.ask("read_run", {"run_id": original_id})
            try:
                session.runs[original_id] = _record(read, original_id, original_config)
            except (ValueError, KeyError, TypeError) as exc:
                session.stop_reason = str(exc)
    if claim is not None and original_config is not None:
        if policy in FIXED:
            config = dict(zip(CONFIG_KEYS, FIXED[policy]))
            remaining = session.remaining()
            quote = session.quote(config, remaining, reuse=True) if remaining is not None else None
            session.decisions.append({"stage": "fixed", "config": config, "quote": deepcopy(quote)})
            if quote is not None:
                session.purchase(config, quote, "fixed")
            else:
                session.stop_reason = "Fixed check unavailable or unaffordable."
        elif policy == "random":
            for index, config in enumerate(random_plan):
                remaining = session.remaining()
                if remaining is None:
                    break
                quote = session.quote(config, remaining)
                session.decisions.append({"stage": "random", "plan_index": index, "config": config,
                                          "remaining": remaining, "quote": deepcopy(quote)})
                if quote is not None:
                    session.purchase(config, quote, "random")
            if session.stop_reason is None:
                session.stop_reason = "Predetermined affordable menu exhausted."
        else:
            _adaptive(session, claim, original_config, original_id)
    estimator = estimate_claim(claim, list(session.runs.values()), original_id,
                               original_config=original_config)
    justification = estimator["diagnosis"] + " "
    if estimator["estimate"] is not None:
        justification += f"Purchased-data estimate={estimator['estimate']:.12g}; "
        if "absolute_tolerance" in estimator:
            justification += f"claim allowance={estimator['absolute_tolerance']:.12g}. "
    justification += "Resolution-order ranking and any Richardson correction are unvalidated numerical assumptions, not certified bounds."
    submission = session.ask("submit", {"verdict": estimator["verdict"], "diagnosis": estimator["diagnosis"],
                                        "evidence_ids": estimator["evidence_ids"], "justification": justification})
    return _json_diagnostics({"policy": policy, "seed": seed, "random_plan": deepcopy(random_plan),
            "acquisitions": session.acquisitions, "decisions": session.decisions,
            "runs": list(session.runs.values()), "estimator": estimator, "submission": submission,
            "submitted": submission.get("status") in ("success", "submitted"),
            "stop_reason": session.stop_reason, "trace": session.trace})
