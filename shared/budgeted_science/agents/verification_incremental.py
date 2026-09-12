"""Opt-in eight-credit adapter; original verification defaults stay unchanged."""
from copy import deepcopy
from dataclasses import asdict, dataclass, field

from ..claim_verification_incremental.environment import IncrementalEpisode
from .verification import (VerificationConfig, VerificationInstance, VerificationEpisode,
                           tool_definitions as original_tools, prompts as original_prompts)
from .verification_fake import VerificationGateway
from .verification_reporting import regenerate


@dataclass(frozen=True)
class IncrementalConfig(VerificationConfig):
    model: str = 'gpt-5.6-luna'
    scientific_budget: int = 8
    task_variant: str = 'claim_verification_incremental'

    def __post_init__(self):
        if (self.model != 'gpt-5.6-luna' or self.scientific_budget != 8
                or self.task_variant != 'claim_verification_incremental'):
            raise ValueError('incremental Luna evaluation contract cannot change')
        original = asdict(self)
        original.update(scientific_budget=5, task_variant='claim_verification')
        VerificationConfig(**original)  # Preserve existing limits and validation.


@dataclass(frozen=True)
class IncrementalInstance(VerificationInstance):
    comparison: dict = field(default_factory=dict)


def tool_definitions(config=None):
    result = original_tools(config)
    descriptions = {
        'refine_integration': 'Cost 3: halve this run\'s current Euler timestep, preserving all output times. Incremental, not an exact solve. Identical purchased configuration is free.',
        'refine_sampling': 'Cost 2: bisect every interval between this run\'s output times, retaining old nodes and the current Euler timestep. Evaluate the numerical trajectory at new times. Identical purchased configuration is free.'}
    for tool in result:
        if tool['name'] in descriptions:
            tool['description'] = descriptions[tool['name']]
    return result


def prompts(config, episode):
    messages = original_prompts(config, episode)
    messages[1]['content'] = messages[1]['content'].replace('You have 5 audit credits.', 'You have 8 audit credits.')
    marker = 'A successful tool call does not itself certify the report.'
    messages[1]['content'] = messages[1]['content'].replace(marker,
        'Each integration refinement halves the current Euler timestep. Each sampling refinement '
        'bisects the current output intervals. Checks can be repeated or chained, but neither '
        'returns a high-accuracy reference automatically. ' + marker)
    return messages


class IncrementalAgentEpisode(VerificationEpisode):
    environment_class = IncrementalEpisode


class IncrementalAdapter:
    create_episode = staticmethod(IncrementalAgentEpisode)
    restore_episode = staticmethod(IncrementalAgentEpisode.restore)
    prompts = staticmethod(prompts)
    tool_definitions = staticmethod(tool_definitions)
    regenerate = staticmethod(regenerate)

    @staticmethod
    def run_comparisons(config, instance, log):
        if not instance.comparison:
            raise ValueError('verified saved comparison required')
        log.write_json('comparisons/saved-fixed-IIS.json', instance.comparison)
        return deepcopy(instance.comparison)

    @staticmethod
    def scripted_gateway(config=None):
        return VerificationGateway()  # IS then predetermined ACCEPT: logging fixture only.


def prepare_resume(path, mode):
    from .verification_resume import prepare_resume as prepare
    return prepare(path, mode=mode, config_type=IncrementalConfig,
                   instance_type=IncrementalInstance, episode_type=IncrementalAgentEpisode,
                   definitions=tool_definitions)
