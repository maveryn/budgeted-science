"""Matched original/expanded MMS menus using the existing durable API runner."""
from copy import deepcopy
from dataclasses import asdict, dataclass

from ..mms_verification.alternatives import AlternativeAudit
from .mms_verification import (MMSConfig, MMSEpisode, MMSAdapter, MMSGateway,
                               prompts as original_prompts, tool_definitions as original_tools)


@dataclass(frozen=True)
class MenuConfig(MMSConfig):
    task_variant: str = "mms_alternatives"
    menu: str = "expanded"

    def __post_init__(self):
        if self.menu not in ("original", "expanded") or self.task_variant != "mms_alternatives":
            raise ValueError("unknown MMS menu configuration")
        values = asdict(self)
        values.pop("menu")
        values["task_variant"] = "mms_verification"
        MMSConfig(**values)


def tool_definitions(config):
    tools = original_tools(config)
    if config.menu == "expanded":
        string = {"type": "string"}
        extras = [
            ("run_affine_mms", "Solve a manufactured affine profile u=1.1+0.2*x+0.35*y on a selected family/grid/kernel, with analytically manufactured source and boundary data. Returns exact diagnostic error norms for this profile. Costs (grid+1)^2/289 per new solve; reuse free.",
             {"family": {"type": "string", "enum": ["diffusion", "advection", "mixed"]},
              "grid": {"type": "integer", "enum": [8,16,32,64]},
              "kernel": {"type": "string", "enum": ["audited", "independent"]}}),
            ("crosscheck_linear_solver", "Re-solve a purchased numerical run using ILU-preconditioned GMRES (rtol=1e-12, atol=1e-13), preserving its grid, physical problem, source, boundary data and selected discrete kernel. Returns the point value, residual, iterations and point-value difference from that record. Costs (grid+1)^2/289 per new solve; identical iterative results reused free.",
             {"result_id": string}),
            ("richardson", "Free Richardson point-value extrapolation from two successful purchased original-study runs at increasing resolutions using the same discrete kernel. Supply the assumed positive order p. Assumes leading error C*h^p; returns extrapolated value and estimated fine-grid error, not a certified bound or measured convergence order. Does not execute a solver.",
             {"coarse_id": string, "fine_id": string, "assumed_order": {"type": "number", "minimum": .1, "maximum": 8}}),
        ]
        tools += [{"type": "function", "name": name, "description": description, "strict": True,
                   "parameters": {"type": "object", "properties": deepcopy(properties),
                                  "required": list(properties), "additionalProperties": False}}
                  for name, description, properties in extras]
    return sorted(tools, key=lambda t: t["name"])


def prompts(config, episode):
    messages = original_prompts(config, episode)
    messages[1]["content"] = messages[1]["content"].replace(
        "All manufactured diagnostics use the public profile", "The original run_mms diagnostics use the public profile").replace(
        f"and USD {config.api_ceiling_usd}\nmaximum API expenditure from the separately limited batch allowance.",
        "and a separately enforced API spending ceiling within the batch allowance.")
    return messages


class MenuEpisode(MMSEpisode):
    def __init__(self, config, instance, log, deadline=None):
        super().__init__(config, instance, log, deadline)
        if config.menu == "expanded":
            self.environment = AlternativeAudit(instance.study, config.scientific_budget, sink=self._event)
        self.schemas = {t["name"]: t["parameters"] for t in tool_definitions(config)}

    def checkpoint(self):
        return {**super().checkpoint(), "menu": self.config.menu}


class MenuGateway(MMSGateway):
    """Offline expanded-menu fixture also exercises each additional action."""
    async def stream(self, body, metadata):
        async for event in super().stream(body, metadata):
            if event["type"] == "response.completed":
                import json
                turn = len(self.requests)
                actions = [
                    ("run_affine_mms", {"family":"advection", "grid":8, "kernel":"audited"}),
                    ("crosscheck_linear_solver", {"result_id":"original"}),
                    ("run_study", {"grid":32, "kernel":"audited"}),
                    ("richardson", {"coarse_id":"original", "fine_id":"run-003", "assumed_order":2}),
                    ("submit", {"qoi":"ABSTAIN", "order":"ABSTAIN", "evidence_ids":["original"], "explanation":"Offline fixture."}),
                ]
                name, args = actions[min(turn-1, len(actions)-1)]
                call = next(i for i in event["response"]["output"] if i["type"] == "function_call")
                call.update(name=name, arguments=json.dumps(args))
            yield event


class MenuAdapter(MMSAdapter):
    create_episode = staticmethod(MenuEpisode)
    tool_definitions = staticmethod(tool_definitions)
    prompts = staticmethod(prompts)

    @staticmethod
    def scripted_gateway(config=None):
        return MenuGateway() if config and config.menu == "expanded" else MMSGateway()
