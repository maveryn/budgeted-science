"""Trusted predator-prey adapter; no API calls or credential reads on import."""

from copy import deepcopy
from dataclasses import dataclass
import json
import time

import numpy as np

from budgeted_science.resource_planning.config import Config
from budgeted_science.resource_planning.emulator import Calibration, GPSettings, check_deadline
from budgeted_science.resource_planning.environment import Episode
from budgeted_science.resource_planning.policies import run_policy
from .config import RunConfig
from .planning import validate_arguments
from .records import digest


@dataclass(frozen=True)
class ResourceRunConfig:
    model: str = "gpt-5.6-sol"
    reasoning_effort: str = "high"
    api_ceiling_usd: str = "2.00"
    max_responses: int = 30
    max_output_tokens: int = 32768
    deadline_seconds: float = 1200.0
    task_variant: str = "resource_planning"

    def __post_init__(self):
        RunConfig(**{k: getattr(self, k) for k in (
            "model", "reasoning_effort", "api_ceiling_usd", "max_responses",
            "max_output_tokens", "deadline_seconds")})
        if self.task_variant != "resource_planning":
            raise ValueError("unknown resource task")

    def public(self):
        return {**self.__dict__, "environment": Config().public(),
                "fit_settings": GPSettings().to_dict(), "fitting_seed": 0,
                "agent_initialization": "free initial evidence only; no paid warm start"}


@dataclass(frozen=True)
class ResourceInstance:
    theta: tuple
    target_seed: int = 2000

    @classmethod
    def first_evaluation(cls):
        bounds = np.asarray(Config().bounds)
        return cls(tuple(np.random.default_rng(2000).uniform(bounds[:, 0], bounds[:, 1])))

    def private(self):
        return {"target_parameters": list(self.theta), "target_seed": self.target_seed,
                "selection": "first frozen evaluation target by original ordering"}


def tool_definitions():
    theta = {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3}
    actions = [
        ("simulate_low", "Purchase a low-accuracy candidate trajectory for 1 credit. Returns x,y at all 16 times. Exact repeat is free.", {"theta": theta}),
        ("simulate_high", "Purchase a high-accuracy candidate trajectory for 8 credits. Returns x,y at all 16 times. Exact repeat is free.", {"theta": theta}),
        ("measure_target", "Purchase one noiseless scalar from the fixed target for 12 credits. Existing observations are free. No candidate parameters accepted.",
         {"variable": {"type": "string", "enum": ["x", "y"]},
          "time": {"type": "number", "enum": list(Config().working_times)}}),
        ("get_status", "Free budget, purchase inventory, and submission status; no new evidence.", {}),
        ("evidence", "Retrieve all already available observations and purchased trajectories for free.", {}),
        ("compare_cached_candidates", "Free residual comparisons of purchased candidates against available target observations. Residuals are not parameter errors.", {}),
        ("fit_purchased", "Free approximate GP parameter fit using only purchased simulations and available observations. Requires at least one successful simulation; returns no acquisition recommendations.", {}),
        ("submit", "Submit a three-parameter estimate within the public bounds and end the episode. No private score is returned.", {"theta_hat": theta}),
    ]
    return [{"type": "function", "name": name, "description": description, "strict": True,
             "parameters": {"type": "object", "properties": properties,
                            "required": list(properties), "additionalProperties": False}}
            for name, description, properties in actions]


def prompts(config, episode):
    public = Config().public()
    return [
        {"role": "developer", "content":
         "You are conducting a budgeted scientific parameter-recovery investigation. "
         "Use only the provided tools. Choose your own purchases and analysis. "
         "Your final answer must be a valid submit tool call; prose does not count. "
         "There is no required acquisition sequence or lengthy written plan. "
         "There is no code execution, web access, or access to private evaluator files."},
        {"role": "user", "content": f"""Infer the three fixed unknown parameters theta=[theta1,theta2,theta3] of a predator-prey system from the available evidence and candidate models.

Public configuration: {json.dumps(public)}
The populations are x and y; initial conditions are known. The horizon is 8 in dimensionless time units. The system equations and fixed constants are not supplied. The high-accuracy candidate simulator represents the same system family as the fixed target, without structural mismatch. The cheaper simulator has numerical approximation error whose magnitude depends on parameters and time. Do not assume a low-fidelity best fit is accurate for the target.

Initial free observations: {json.dumps(episode.initial_observations)}

You have 40 shared scientific credits. A NEW low simulation costs 1, a NEW high simulation 8, and a NEW target scalar measurement 12. A candidate simulation accepts your chosen theta and purchases its full trajectory; responses return x,y at times 0.5,1.0,...,8.0. Target measurements accept only x/y and one of those times, not candidate parameters. Measurements are noiseless. Exact repeats of purchased simulations or observations, including the free observations at time 1, cost zero. Known time-zero values are in the evidence. Invalid or unaffordable requests cost nothing; a simulation that executes and fails retains its charge and is cached. Prices are declared resource credits, not measured runtime or dollars. You start with no paid simulations or measurements.

Analysis and retrieval are free scientific actions. compare_cached_candidates compares only purchased predictions with available observations. fit_purchased uses a two-fidelity GP (high=low+discrepancy), independent population channels, correlated time outputs, and 2,048 prior particles with fixed numerical settings. It returns an approximate posterior mean and diagnostics. These diagnostics are not validated confidence statements. It only uses purchased data, cannot run new simulations or measurements, and requires at least one successful simulation. You may submit its estimate or a different in-bounds vector. An unchanged-evidence fit is reused. Free tools remain available after scientific credits run out.

Success requires EVERY parameter to have relative error at most 10 percent. The private evaluator reports E_worst=max_i(abs(theta_hat_i-theta_true_i)/(0.10*abs(theta_true_i))); success is E_worst<=1. It scores your submitted parameters, not your explanations or confidence. There is no bonus for saving credits or stopping early. Private scores and true parameters are not revealed during the investigation.

Submit before the separate runner limits: {config.max_responses} model responses and {config.deadline_seconds:g} seconds. API usage has a separate ${config.api_ceiling_usd} ceiling and can end the episode before the scientific budget is exhausted. No fallback answer is supplied if you do not submit."""},
    ]


def environment_logger(log, role, parent):
    """Archive private events, never forwarding them to the model-facing stream."""
    def emit(kind, **data):
        data = deepcopy(data)
        if kind == "episode_started":
            artifact = log.write_json(f"private/{role}-reference.json", data.pop("target_artifact"))
            data["private_reference_artifact"] = artifact
        if kind == "simulation" and data.get("artifact") is not None:
            result = data.get("result", {})
            result_id = result.get("result_id", f"event-{log._sequence + 1}")
            artifact = log.write_json(f"numerical/{role}/{result_id}.json", data.pop("artifact"))
            data["artifact_path"] = artifact
            log.event("simulation_finished", role=role, parent_call=parent(),
                      result_id=result_id, artifact=artifact)
        log.event("environment_event", role=role, parent_call=parent(), event_kind=kind, data=data)
    return emit


class ResourceEpisode:
    def __init__(self, config, instance, log, deadline=None):
        self.log, self.deadline, self.parent_call = log, deadline, None
        self.executed, self.fits = {}, {}
        self.schemas = {t["name"]: t["parameters"] for t in tool_definitions()}
        self.environment = Episode(instance.theta, log=environment_logger(log, "agent", lambda: self.parent_call))
        self.tools = self.environment.tools
        self.initial_observations = self.tools.evidence()["observations"]

    @property
    def submission(self):
        return self.tools.get_status()["submission"]

    def budget_status(self):
        status = self.tools.get_status()
        return {k: status[k] for k in ("status", "spent", "remaining")}

    def fit(self):
        evidence = self.tools.evidence()
        successful = [s for s in evidence["simulations"] if s["status"] == "success"]
        if not successful:
            raise ValueError("fit_purchased requires at least one purchased successful simulation")
        fingerprint = digest({"simulations": successful, "observations": evidence["observations"],
                              "settings": GPSettings().to_dict(), "seed": 0})
        started = time.monotonic()
        if fingerprint in self.fits:
            result = deepcopy(self.fits[fingerprint])
            result.update(cache_hit=True, analysis_seconds=time.monotonic() - started)
            self.log.event("fit_reused", role="agent", parent_call=self.parent_call, result=result)
            return result
        public = Config().public()
        calibration = Calibration(successful, evidence["observations"], public["bounds"],
                                  public["initial"], public["working_times"], seed=0,
                                  settings=GPSettings(), deadline=self.deadline)
        check_deadline(self.deadline)
        diagnostics = calibration.diagnostics()
        fit_id = f"fit-{len(self.fits) + 1:04d}"
        artifact = self.log.write_json(f"fitting/{fit_id}.json", {
            "evidence_hash": fingerprint, "diagnostics": diagnostics,
            "particles": calibration.particles.tolist(), "weights": calibration.weights.tolist(),
            "input_simulation_ids": [s["result_id"] for s in successful],
            "input_observation_ids": [o["record_id"] for o in evidence["observations"]]})
        result = {"status": "success", "fit_id": fit_id, "posterior_mean": diagnostics["posterior_mean"],
                  "uncertainty_log_parameters": diagnostics["uncertainty_log_parameters"],
                  "effective_particles": diagnostics["effective_particles"],
                  "maximum_particle_weight": diagnostics["maximum_particle_weight"],
                  "note": "Approximate GP diagnostics, not validated confidence; no new scientific data acquired.",
                  "cache_hit": False, "analysis_seconds": time.monotonic() - started}
        self.fits[fingerprint] = deepcopy(result)
        self.log.event("fit_finished", role="agent", parent_call=self.parent_call,
                       evidence_hash=fingerprint, artifact=artifact, result=result)
        return result

    def execute(self, call_id, name, arguments):
        self.log.event("tool_requested", role="agent", call_id=call_id, name=name, arguments=arguments)
        signature = digest([name, arguments])
        output = None
        if call_id in self.executed:
            previous, result = self.executed[call_id]
            output = ({**deepcopy(result), "replayed_call": True} if previous == signature else
                      {"ok": False, "error": "call_id_conflict"})
        self.parent_call = call_id
        try:
            if output is None:
                if not isinstance(call_id, str) or not call_id or name not in self.schemas:
                    raise ValueError("unknown tool or invalid call ID")
                if self.submission is not None:
                    raise ValueError("episode has already been submitted")
                def reject(value):
                    raise ValueError("nonfinite JSON constant")
                args = json.loads(arguments, parse_constant=reject)
                validate_arguments(args, self.schemas[name])
                check_deadline(self.deadline)
                if name == "fit_purchased":
                    result = self.fit()
                else:
                    result = getattr(self.tools, name)(**args)
                    if name == "get_status":
                        result = {**{k: result[k] for k in ("status", "spent", "remaining", "submission", "ledger")},
                                  "observations": result["observations"],
                                  "simulations": [{k: s.get(k) for k in ("result_id", "theta", "fidelity", "status")}
                                                  for s in result["simulations"]]}
                check_deadline(self.deadline)
                output = {"ok": result.get("status") not in ("invalid", "unaffordable", "failed", "closed"),
                          "result": result}
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            output = {"ok": False, "error": "invalid_arguments", "message": str(exc)}
        except (FloatingPointError, np.linalg.LinAlgError) as exc:
            output = {"ok": False, "error": "fit_numerical_failure", "message": str(exc)}
        finally:
            self.parent_call = None
        output["budget_after"] = self.budget_status()
        if call_id not in self.executed:
            self.executed[call_id] = (signature, deepcopy(output))
        self.log.event("tool_result", role="agent", call_id=call_id, name=name, output=output)
        return output

    def evaluate(self):
        result = self.environment.evaluate()
        status = self.tools.get_status()
        counts = {"low": 0, "high": 0, "measurement": 0}
        for entry in status["ledger"]:
            key = {"simulate_low": "low", "simulate_high": "high", "measure_target": "measurement"}[entry["kind"]]
            counts[key] += 1
        return {**result, "resource_counts": counts, "scientific_status": status}


def run_comparisons(config, instance, log):
    results = {}
    for policy in ("random", "adaptive"):
        started = time.monotonic()
        environment = Episode(instance.theta, log=environment_logger(log, policy, lambda: None))
        details, termination = None, "submitted"
        try:
            details = run_policy(environment.tools, policy=policy, seed=0,
                                 deadline=time.monotonic() + 300,
                                 log=lambda kind, **data: log.event("baseline_event", policy=policy,
                                                                 event_kind=kind, data=data))
        except Exception as exc:
            termination = "deadline" if isinstance(exc, TimeoutError) else "baseline_error"
            environment.abort(termination)
            log.event("baseline_error", policy=policy, error=log.redactor.error(exc))
        status = environment.tools.get_status()
        results[policy] = {"evaluation": environment.evaluate(), "scientific_status": status,
                           "termination_reason": termination, "policy_seed": 0, "details": details,
                           "elapsed_seconds": time.monotonic() - started}
        log.write_json(f"comparisons/{policy}.json", results[policy])
    return results


class ResourceAdapter:
    create_episode = staticmethod(ResourceEpisode)
    prompts = staticmethod(prompts)
    tool_definitions = staticmethod(tool_definitions)
    run_comparisons = staticmethod(run_comparisons)

    @staticmethod
    def regenerate(path):
        from .reporting import regenerate
        from .resource_reporting import write_report
        return regenerate(path, report_writer=write_report)

    @staticmethod
    def scripted_gateway():
        from .resource_fake import ResourceScriptedGateway
        return ResourceScriptedGateway()
