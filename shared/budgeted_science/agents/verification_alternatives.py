"""Matched original/expanded-menu predator-prey verification adapter."""
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from decimal import Decimal

from ..claim_verification.alternatives import AlternativeEpisode as ExpandedEnvironment
from ..claim_verification.environment import Episode as OriginalEnvironment
from .verification import (VerificationConfig, VerificationInstance, VerificationEpisode,
                           prompts as original_prompts, tool_definitions as original_tools)
from .verification_fake import VerificationGateway
from .verification_reporting import regenerate


@dataclass(frozen=True)
class AlternativesConfig(VerificationConfig):
    model: str = "gpt-5.6-luna"
    api_ceiling_usd: str = "2.00"
    deadline_seconds: float = 300.0
    task_variant: str = "claim_verification_alternatives"
    menu: str = "expanded"

    def __post_init__(self):
        if (self.menu not in ("original", "expanded") or self.model != "gpt-5.6-luna"
                or self.deadline_seconds != 300 or self.max_responses != 30
                or self.max_output_tokens != 32768 or Decimal(self.api_ceiling_usd) > 2
                or self.task_variant != "claim_verification_alternatives"):
            raise ValueError("frozen alternative-menu contract cannot change")
        values = asdict(self)
        values.pop("menu")
        values["task_variant"] = "claim_verification"
        VerificationConfig(**values)


@dataclass(frozen=True)
class AlternativesInstance(VerificationInstance):
    comparison: dict = field(default_factory=dict)
    batch_scope: dict = field(default_factory=dict)

    def private(self):
        return {**super().private(), "batch_scope": deepcopy(self.batch_scope)}


def tool_definitions(config):
    tools = original_tools(config)
    if config.menu == "original":
        return tools
    extra = [
        ("tighten_integration", "Cost 1: halve Euler's integration timestep, or divide an adaptive integrator's rtol and atol by ten. Preserve this run's output times. Returns the maximum of stored x samples. May operate on a purchased run; identical purchased configurations are free."),
        ("bisect_output", "Cost 1: insert one midpoint into each output interval, preserving integration settings. Rerun/evaluate the numerical trajectory at these times. Returns the maximum of stored x samples. May operate on a purchased run; identical purchased configurations are free."),
        ("crosscheck_integrator", "Cost 3: rerun the same physical problem with the implicit Radau integrator, rtol=1e-10 and atol=1e-12. Preserve this run's output times. Returns the maximum of stored x samples. May operate on a purchased run; identical purchased configurations are free."),
    ]
    # Sorted in both conditions: original tools keep their relative order, with
    # no privileged placement or 'distractor' tag for the extra operations.
    tools += [{"type": "function", "name": name, "description": text, "strict": True,
               "parameters": {"type": "object", "properties": {"run_id": {"type": "string"}},
                              "required": ["run_id"], "additionalProperties": False}}
              for name, text in extra]
    return sorted(tools, key=lambda t: t["name"])


def prompts(config, episode):
    messages = original_prompts(config, episode)
    text = messages[1]["content"]
    start, end = text.index("You have 5 audit credits."), text.index("Submit a verdict,")
    common = """You have 5 audit credits. Each tool description states its price and numerical
settings. Inspection, recomputation of stored-sample peaks, comparisons and
submission are free. Reuse of purchased configurations is free. Invalid or
unaffordable calls are uncharged; executed failed checks retain their charge.
A successful tool call does not itself certify the report. No new target
measurements, parameter changes, or reference-query action exists.

"""
    messages[1]["content"] = text[:start] + common + text[end:]
    # Scientific prompt is identical for both menus and does not disclose the
    # campaign's remaining funds or condition. Actual API caps stay in manifests.
    messages[1]["content"] = messages[1]["content"].replace(
        f"USD {config.api_ceiling_usd}\ncumulative API usage",
        "a separately enforced API spending ceiling")
    return messages


class AlternativesEpisode(VerificationEpisode):
    def __init__(self, config, instance, log, deadline=None, *, archive=True):
        self.environment_class = ExpandedEnvironment if config.menu == "expanded" else OriginalEnvironment
        super().__init__(config, instance, log, deadline, archive=archive)
        self.schemas = {t["name"]: t["parameters"] for t in tool_definitions(config)}

    def checkpoint(self):
        return {**super().checkpoint(), "inspection_only": True, "menu": self.config.menu}

    @classmethod
    def restore(cls, *args, **kwargs):
        raise ValueError("batch-funded alternative-menu episodes cannot resume independently")


class AlternativesAdapter:
    create_episode = staticmethod(AlternativesEpisode)
    restore_episode = staticmethod(AlternativesEpisode.restore)
    prompts = staticmethod(prompts)
    regenerate = staticmethod(regenerate)

    @staticmethod
    def tool_definitions(config):
        return sorted(tool_definitions(config), key=lambda t: t["name"])

    @staticmethod
    def run_comparisons(config, instance, log):
        if not instance.comparison or instance.comparison["case_id"] != instance.study["case_id"]:
            raise ValueError("matching CPU comparison required")
        log.write_json("comparisons/saved-cpu.json", instance.comparison)
        return deepcopy(instance.comparison)

    @staticmethod
    def scripted_gateway(config=None):
        return VerificationGateway()
