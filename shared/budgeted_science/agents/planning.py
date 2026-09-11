"""Logged adapter around the existing planning facade; no numerical changes."""

from copy import deepcopy
import json
import math

import numpy as np

from budgeted_science.burgers.budget import BudgetExceeded, Ledger, WORK_PER_CREDIT
from budgeted_science.burgers.cache import SimulationService
from budgeted_science.burgers.config import FORECAST_POSITIONS, LENGTH, RECORD_TIMES, SENSOR_POSITIONS
from budgeted_science.burgers.observations import ObservationService
from budgeted_science.burgers.reference import ReferenceOracle
from budgeted_science.burgers.scoring import score_planning
from budgeted_science.burgers.tools import AmplitudePlanningTools, PlanningTools

from .records import digest


def tool_definitions(config=None):
    number = {"type": "number", "minimum": 0.1, "maximum": 0.3}
    resolution = {"type": "integer", "enum": [32, 64, 128]}
    definitions = [
        ("observe", "Buy new five-time calibration trials at one sensor of the fixed target. Each replicate costs the disclosed record price.",
         {"sensor_id": {"type": "integer", "enum": [0, 1, 2]}, "replicates": {"type": "integer", "minimum": 1}}),
        ("record", "Retrieve a previously acquired observation record for free.", {"record_id": {"type": "string"}}),
        ("simulate", "Compute a candidate-parameter trajectory at the chosen grid. Return compact predictions and a result_id; full results are retrievable for free. This is not an observation of the target.",
         {"viscosity": number, "resolution": resolution, "protocol": {"type": "string", "enum": ["calibration", "forecast"]}}),
        ("fit", "Fit acquired records with a bounded scalar optimizer using the chosen numerical resolution. Starts with both parameter endpoints; max_evaluations bounds all underlying predictor attempts, not credits. Each distinct solve is charged. Returns the best completed fit on interruption. A repeated fit restarts; identical purchased solves are reused for free.",
         {"record_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
          "resolution": resolution, "max_evaluations": {"type": "integer", "minimum": 1}}),
        ("budget", "Inspect the remaining scientific budget for free.", {}),
        ("simulation_record", "Retrieve the full numerical result of an earlier obtained result_id for free; no new solve is performed.",
         {"result_id": {"type": "string"}}),
        ("submit", "Submit the actual forecast values at the 16 specified positions. The first valid submission ends the episode; no private score is returned.",
         {"profile": {"type": "array", "items": {"type": "number"}, "minItems": 16, "maxItems": 16}}),
    ]
    tools = [{"type": "function", "name": name, "description": description, "strict": True,
             "parameters": {"type": "object", "properties": deepcopy(properties),
                            "required": list(properties), "additionalProperties": False}}
            for name, description, properties in definitions]
    if config is not None and config.task_variant == "viscosity_amplitude":
        for tool in tools:
            if tool["name"] == "simulate":
                tool["parameters"]["properties"]["initial_amplitude"] = {
                    "type": "number", "minimum": 0.8, "maximum": 1.2}
                tool["parameters"]["required"].append("initial_amplitude")
                tool["description"] += " Specify candidate calibration amplitude A; forecast uses 1.5*A."
            elif tool["name"] == "fit":
                tool["description"] = (
                    "Jointly fit viscosity and initial amplitude to acquired records with bounded least squares "
                    "at the chosen resolution, starting at the public midpoint (nu=0.2, A=1.0). "
                    "max_evaluations bounds ALL underlying predictor attempts, including finite-difference "
                    "Jacobian calls, not credits. Every distinct solve is charged. Returns the best completed "
                    "fit if interrupted; evaluation_limit does not mean convergence. A repeated fit restarts; "
                    "identical purchased solves are reused for free.")
    return tools


def prompts(config):
    joint = config.task_variant == "viscosity_amplitude"
    unknown = ("unknown dimensionless viscosity coefficient in [0.1, 0.3] and unknown initial amplitude A in [0.8, 1.2]"
               if joint else "unknown dimensionless viscosity coefficient in [0.1, 0.3]")
    initial_conditions = (
        "Calibration initial condition: A*sin(x). Forecast initial condition: 1.5*A*sin(x). "
        "The same unknown A applies to both experiments; the relative factor 1.5 is known."
        if joint else "Calibration initial condition: sin(x). Forecast initial condition: 1.5*sin(x).")
    candidate_parameters = "viscosity and initial amplitude A" if joint else "viscosity"
    developer = (
        "You are performing one budgeted scientific investigation through the supplied tools. "
        "Choose your own workflow to minimize final forecast error within the scientific budget. "
        "Tool observations are the available evidence about the fixed target. Use submit to finish; "
        "a prose-only final response without submission is incomplete. No browser, shell, filesystem, "
        "or exact-target/reference tool is available. No lengthy initial plan is required."
    )
    user = f"""Task: forecast the final profile of a fixed system with {unknown}.

Equation: u_t + u*u_x = nu*u_xx, periodic x in [0, 2*pi), final time T=1.
{initial_conditions}
Observation sensors 0,1,2 are at {list(SENSOR_POSITIONS)}.
One acquisition returns the calibration values at times {list(RECORD_TIMES)} from one sensor. Independent Gaussian noise has standard deviation {config.noise_std}. Replicates are fresh trials with the same fixed target. Acquisition cannot choose target parameters or access the forecast experiment.

Candidate simulations accept your chosen {candidate_parameters} and grids 32,64,128. They use Rusanov flux, centered diffusion and SSP-RK2, with dt=min(time to next record, 0.4/(max(abs(u))/dx + 2*nu/dx**2)). Numerical approximation errors can remain even when fitting observed data well. The sinusoidal periodic family also admits Cole-Hopf analysis; this is a restricted tool-use toy, not intrinsically expensive physics.

Scientific budget: {config.scientific_credits} shared credits for observations and computation.
One sensor record costs {config.record_price} credits. A solver's work proxy is grid points times RHS evaluations, divided by {WORK_PER_CREDIT} for credits. The normalizer is the public nu=0.2, A=1, N=64 calibration solve; this is not measured FLOPs or dollars. Actual solve cost varies with the candidate and protocol. All solves inside fit are charged. Invalid requests are uncharged; attempted work on interrupted/failed calculations remains charged. Only complete deterministic results are reused free within this episode. Repeated observations cost again; record retrieval is free. Incomplete solves are not resumable.

Submit 16 finite forecast values for T=1 at positions {list(FORECAST_POSITIONS)}.
Score: RMSE of YOUR SUBMITTED PROFILE against the private noise-free target forecast, divided by the fixed amplitude scale 1.5. Lower is better. Parameter estimation alone is not the submitted answer. There is no correctness feedback, success tolerance, or separate reward for spending all credits or stopping early. You can submit your best answer even after scientific credits are exhausted.

Execution limits: at most {config.max_responses} model responses, {config.max_output_tokens} output tokens per response including reasoning, and {config.deadline_seconds:g} seconds. Model API expenditure has a separate ${config.api_ceiling_usd} ceiling; it is not exchangeable with scientific credits.
"""
    return [{"role": "developer", "content": developer}, {"role": "user", "content": user}]


def validate_arguments(value, schema):
    kind = schema["type"]
    valid = {"object": isinstance(value, dict), "array": isinstance(value, list),
             "string": isinstance(value, str), "integer": type(value) is int,
             "number": type(value) in (int, float) and math.isfinite(value)}.get(kind, False)
    if not valid:
        raise ValueError(f"expected {kind}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError("value is outside the allowed choices")
    if kind in ("integer", "number"):
        if "minimum" in schema and value < schema["minimum"] or "maximum" in schema and value > schema["maximum"]:
            raise ValueError("number is outside the allowed range")
    if kind == "object":
        if set(value) != set(schema["required"]):
            raise ValueError("supply exactly the declared arguments")
        for key, item in value.items():
            validate_arguments(item, schema["properties"][key])
    if kind == "array":
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", math.inf):
            raise ValueError("array length is outside the allowed range")
        for item in value:
            validate_arguments(item, schema["items"])


class LoggedSimulations:
    def __init__(self, ledger, log, role):
        self.ledger, self.log, self.role = ledger, log, role
        self._base = SimulationService(ledger)
        self.results = {}
        self.parent_call = None
        self.last_result_id = None
        self.spending = {"calibration_and_fitting": 0.0, "forecasting": 0.0}

    def run(self, config):
        result_id = f"sim-{len(self.results) + 1:05d}"
        self.log.event("simulation_started", role=self.role, parent_call=self.parent_call,
                       result_id=result_id, configuration=config.identity())
        result = self._base.run(config)
        full = result.public()
        artifact = self.log.write_json(f"numerical/{self.role}/{result_id}.json", full)
        self.results[result_id] = full
        self.last_result_id = result_id
        activity = "forecasting" if config.protocol == "forecast" else "calibration_and_fitting"
        self.spending[activity] += full["charged_credits"]
        self.log.event("simulation_finished", role=self.role, parent_call=self.parent_call,
                       result_id=result_id, artifact=artifact, activity=activity,
                       status=result.status, charged_work_units=result.charged_work_units,
                       work_units=result.work_units,
                       reused_purchased_result=result.status == "completed" and result.charged_work_units == 0,
                       budget_after=self.ledger.status())
        return result


class PlanningEpisode:
    def __init__(self, config, instance, log, role="agent"):
        if config.task_variant == "viscosity" and instance.target_amplitude != 1.0:
            raise ValueError("one-parameter task requires target amplitude 1")
        self.config, self.instance, self.log, self.role = config, instance, log, role
        self.ledger = Ledger.shared(config.scientific_credits)
        self.observations = ObservationService(ReferenceOracle(instance.target_viscosity,
                                                               initial_amplitude=instance.target_amplitude), self.ledger,
                                               seed=instance.seed, noise_std=config.noise_std,
                                               record_price=config.record_price)
        self.simulations = LoggedSimulations(self.ledger, log, role)
        tool_class = AmplitudePlanningTools if config.task_variant == "viscosity_amplitude" else PlanningTools
        self.tools = tool_class(self.observations, self.simulations, self.ledger)
        self.schemas = {t["name"]: t["parameters"] for t in tool_definitions(config)}
        self.executed = {}

    @property
    def submission(self):
        return self.tools.submission

    def execute(self, call_id, name, arguments):
        signature = digest([name, arguments])
        self.log.event("tool_requested", role=self.role, call_id=call_id, name=name, arguments=arguments)
        if not isinstance(call_id, str) or not call_id:
            output = {"ok": False, "error": "invalid_call_id", "budget_after": self.ledger.status()}
            self.log.event("tool_result", role=self.role, call_id=call_id, name=name, output=output)
            return output
        if call_id in self.executed:
            old_signature, old_result = self.executed[call_id]
            if old_signature != signature:
                output = {"ok": False, "error": "call_id_conflict", "budget_after": self.ledger.status()}
            else:
                output = deepcopy(old_result)
                output.update(replayed_call=True, budget_after=self.ledger.status())
            self.log.event("tool_result", role=self.role, call_id=call_id, name=name, output=output)
            return output
        self.simulations.parent_call = call_id
        try:
            if not isinstance(call_id, str) or not call_id or name not in self.schemas:
                raise ValueError("unknown tool or invalid call_id")
            if self.submission is not None:
                raise ValueError("episode has already been submitted")
            def reject_constant(value):
                raise ValueError("nonfinite JSON constant")
            args = json.loads(arguments, parse_constant=reject_constant)
            validate_arguments(args, self.schemas[name])
            if name == "simulation_record":
                if args["result_id"] not in self.simulations.results:
                    raise ValueError("unknown previously obtained result_id")
                result = deepcopy(self.simulations.results[args["result_id"]])
            else:
                result = self.tools.dispatch(name, **args)
            if name == "simulate":
                full = result
                result = {k: v for k, v in full.items() if k not in ("fields", "positions")}
                result["result_id"] = self.simulations.last_result_id
                if full["status"] == "completed":
                    field = np.array(full["fields"])
                    if full["protocol"] == "forecast":
                        indices = np.rint(np.array(FORECAST_POSITIONS) / LENGTH * full["resolution"]).astype(int)
                        result.update(forecast_positions=list(FORECAST_POSITIONS), forecast_profile=field[-1, indices].tolist())
                    else:
                        indices = np.rint(np.array(SENSOR_POSITIONS) / LENGTH * full["resolution"]).astype(int)
                        result.update(sensor_positions=list(SENSOR_POSITIONS), calibration_times=list(RECORD_TIMES),
                                      calibration_predictions=field[1:, indices].T.tolist())
            if name == "observe":
                for record in result:
                    self.log.write_json(f"observations/{self.role}/{record['record_id']}.json", record)
            output = {"ok": True, "result": result, "budget_after": self.ledger.status()}
        except BudgetExceeded as exc:
            output = {"ok": False, "error": "scientific_budget_exhausted", "message": str(exc),
                      "budget_after": self.ledger.status()}
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            output = {"ok": False, "error": "invalid_arguments", "message": str(exc),
                      "budget_after": self.ledger.status()}
        finally:
            self.simulations.parent_call = None
        self.executed[call_id] = (signature, deepcopy(output))
        self.log.event("tool_result", role=self.role, call_id=call_id, name=name, output=output)
        return output

    def evaluate(self):
        profile = None if self.submission is None else list(self.submission)
        return {"submitted_profile": profile,
                "reference_profile": ReferenceOracle(self.instance.target_viscosity,
                    initial_amplitude=self.instance.target_amplitude).forecast_profile().tolist(),
                "score": None if profile is None else score_planning(profile, self.instance.target_viscosity,
                    target_amplitude=self.instance.target_amplitude),
                "scientific_budget": self.ledger.status(),
                "spending_by_activity": {"observations": self.ledger.status()["spent"]["observation"],
                                         **self.simulations.spending}}


def run_fixed_policy(config, instance, log):
    episode = PlanningEpisode(config, instance, log, role="fixed_policy")
    def call(name, args):
        result = episode.execute(f"fixed-{len(episode.executed) + 1}", name, json.dumps(args))
        if not result["ok"]:
            raise RuntimeError("fixed policy could not complete a requested tool action")
        return result["result"]
    joint = config.task_variant == "viscosity_amplitude"
    records = [call("observe", {"sensor_id": sensor, "replicates": 1})[0]
               for sensor in ((0, 1, 2) if joint else (2,))]
    fitted = call("fit", {"record_ids": [r["record_id"] for r in records],
                          "resolution": 64 if joint else 32, "max_evaluations": 12 if joint else 16})
    if fitted["viscosity"] is None:
        raise RuntimeError("fixed policy has no completed fit")
    forecast_args = {"viscosity": fitted["viscosity"], "resolution": 64, "protocol": "forecast"}
    if joint:
        forecast_args["initial_amplitude"] = fitted["initial_amplitude"]
    forecast = call("simulate", forecast_args)
    if forecast["status"] != "completed":
        raise RuntimeError("fixed policy has no completed forecast")
    call("submit", {"profile": forecast["forecast_profile"]})
    result = episode.evaluate()
    result["description"] = (
        "One record from each sensor; N=64 joint fit (max 12 predictions); N=64 forecast. "
        "Development-selected recipe from the CPU trial, not an optimal or held-out-tuned baseline."
        if joint else "One sensor-2 record; N=32 fit (max 16 predictions); N=64 forecast. Not an optimal baseline.")
    result["fit"] = fitted
    log.event("fixed_policy_finished", evaluation=result)
    log.write_json("fixed_policy_evaluation.json", result)
    return result
