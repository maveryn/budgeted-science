"""Resource-specific evaluation derived from saved records, never from reruns."""

from .records import json_text
from .reporting import _write


def purchases(status):
    counts = {"simulate_low": 0, "simulate_high": 0, "measure_target": 0}
    for entry in status.get("ledger", []):
        counts[entry["kind"]] += 1
    return counts


def write_report(path, manifest, events, finished, status):
    config = manifest["public_configuration"]
    lines = ["# Predator-prey resource-planning episode", "",
             f"Mode: {manifest['mode']}; termination: **{status}**.", "",
             f"Model: {config['model']}; reasoning: {config['reasoning_effort']}; "
             f"response limit: {config['max_responses']}; output tokens/response: {config['max_output_tokens']}.", "",
             "Scientific pool: 40 credits. Low/high/measurement prices: 1/8/12. "
             "Measurements are noiseless; all methods use the same 16-time menu. "
             "GPT starts with free evidence only and can call the shared purchased-evidence fitter; "
             "the two baseline policies pay for their own prescribed 12-credit initialization.", "",
             "E_worst = max_i |estimate_i - target_i| / (0.10 |target_i|). "
             "Success requires E_worst <= 1 and a valid submission. No reward for saving resources, "
             "stopping early, or reporting confidence. Missing submissions are incomplete, not fabricated answers.", ""]
    if manifest["mode"] != "live":
        lines += ["**SCRIPTED OFFLINE FIXTURE: no LLM evaluated; actual API spending $0. "
                  "Token usage below is synthetic testing data.**", ""]
    if manifest.get("resume"):
        lines += ["## Continuation", "", "This continues the same scientific episode with the existing conversation, "
                  "purchases, and API ledger. The prior attempt is preserved in prior_attempts/. "
                  "Counts, scientific spending, API accounting, and elapsed active time below are cumulative; "
                  "offline downtime is excluded. The independent baselines were restored, not rerun.", ""]
        previous_ceiling = manifest["resume"].get("prior_api_ceiling_usd", "2.00")
        if previous_ceiling != config["api_ceiling_usd"]:
            lines += [f"The user explicitly authorized raising the cumulative API ceiling from ${previous_ceiling} "
                      f"to ${config['api_ceiling_usd']}. Prior usage and unknown reservations remain charged to that total.", ""]
        if config.get("require_full_budget"):
            lines += ["The user explicitly added a requirement to spend all 40 scientific credits before submission. "
                      "This is a recorded continuation instruction, not an unchanged-prompt replication of the original attempt.", ""]
    if finished:
        evaluation = finished["evaluation"]
        comparisons = finished.get("fixed_policy") or {}
        rows = [("GPT-5.6 Sol" if manifest["mode"] == "live" else "Scripted fake",
                 evaluation, evaluation.get("scientific_status", {}), status, finished["elapsed_seconds"])]
        for policy in ("random", "adaptive"):
            if policy in comparisons:
                item = comparisons[policy]
                rows.append((policy, item["evaluation"], item["scientific_status"],
                             item["termination_reason"], item["elapsed_seconds"]))
        lines += ["| Method | Success | Worst normalized error | Credits | Low / high / measurement purchases | Seconds |",
                  "|---|---|---:|---:|---|---:|"]
        for name, result, scientific, termination, elapsed in rows:
            valid = result.get("valid", False)
            success = valid and termination == "submitted" and result.get("success", False)
            metric = f"{result['parameter_error']:.8g}" if valid else "Not submitted"
            counts = purchases(scientific)
            allocation = " / ".join(str(counts[k]) for k in ("simulate_low", "simulate_high", "measure_target"))
            lines.append(f"| {name} | {'Yes' if success else 'No'} | {metric} | "
                         f"{scientific.get('spent', 0):g} | {allocation} | {elapsed:.3f} |")
        lines += ["", "## Parameter estimates and errors", ""]
        for name, result, _, termination, _ in rows:
            lines += [f"### {name}", "", f"Termination: {termination}.", "", "```json",
                      json_text({k: result.get(k) for k in
                                 ("theta_true", "theta_hat", "errors", "parameter_error", "valid", "success")}), "```", ""]
        lines += ["## API accounting", "", "Conservative cost bounds, not an invoice. "
                  "Reasoning tokens are included in output usage; cache-write costs are covered by reservations. "
                  f"Unknown usage retains its reservation. The ${config['api_ceiling_usd']} cumulative cap can stop an episode before submission.",
                  "", "```json", json_text(finished["api_budget"]), "```", ""]
        payload = {"mode": manifest["mode"], "termination_reason": status,
                   "evaluation": evaluation, "comparisons": comparisons,
                   "api_budget": finished["api_budget"], "model_responses": finished["model_responses"],
                   "elapsed_seconds": finished["elapsed_seconds"]}
        _write(path / "evaluation.json", json_text(payload) + "\n")
    else:
        lines += ["No final evaluation was recorded. Partial logs are retained; no tools or evaluator were rerun.", ""]
    lines += ["## Interpretation and records", "",
              "This is one preselected instance, not a performance ranking or evidence of general adaptive-allocation gains. "
              "The classical algorithms are unchanged from the frozen pilot. Their results and all private truth were withheld from GPT. "
              "The agent's 20-minute limit includes API latency; baselines have separate five-minute CPU limits, "
              "so elapsed times are descriptive, not matched compute comparisons. "
              "GP diagnostics are approximate and not validated confidence. This toy uses fixed resource prices, "
              "not unexpected execution costs or structural simulator-target mismatch.", "",
              "- [Complete readable transcript](transcript.md)",
              "- [Chronological API and tool events](events.jsonl)",
              "- [Frozen manifest, including PRIVATE instance configuration](manifest.json)",
              "- [Tool schemas](tools.json)",
              "- Complete numerical artifacts, private references, and fitting records are in numerical/, private/, and fitting/.",
              "- Independent CPU baseline records are in comparisons/.", "",
              "Raw records are local, private, and untracked. Review before sharing.", ""]
    _write(path / "report.md", "\n".join(lines))
    return path / "transcript.md", path / "report.md"
