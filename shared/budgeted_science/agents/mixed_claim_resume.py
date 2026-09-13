"""Explicit continuation of the SAME finalized mixed-claim audit; never retry."""
import argparse
import asyncio
from copy import deepcopy
from dataclasses import asdict, dataclass
from decimal import Decimal
import hashlib
from importlib.metadata import version
import json
from pathlib import Path

from ..resource_planning.checkpoint import export_episode, restore_episode
from ..resource_planning.environment import _SOLVER_KEY
from ..resource_planning.config import harder_config
from . import mixed_claim_audit as audit
from .records import digest, read_events
from .resume import read_json
from .runner import replay_output_item, run_episode
from .spending import ApiBudget, pricing_for_model

# Reviewed migration changes only checkpoint/restore wiring in this module's
# adapter. All pre-existing other shared implementation hashes must still match.
MIGRATION_SOURCE = 'shared/budgeted_science/agents/mixed_claim_audit.py'
MIGRATION_HASH = '6682dcaf519a5ba7349cc77816da082b42591b1368db33d26115484132e8f862'


@dataclass(frozen=True)
class ResumeConfig(audit.Config):
    def __post_init__(self):
        original = asdict(self)
        original['api_ceiling_usd'] = '1.00'
        audit.Config(**original)
        ceiling = Decimal(self.api_ceiling_usd)
        if (self.model != 'gpt-5.6-sol' or self.scientific_budget != 32
                or not ceiling.is_finite() or not Decimal('1') <= ceiling <= Decimal('1.50')):
            raise ValueError('resume supports Sol/32 with cumulative API ceiling at most $1.50')

    @property
    def require_full_budget(self):
        return False


def checkpoint(episode):
    return {'version': 1, 'environment': export_episode(episode.environment._environment),
            'submission': deepcopy(episode.submission), 'executed': deepcopy(episode.executed),
            'request_count': episode.request_count, 'artifact_number': episode.artifact_number,
            'study_hash': digest(episode.instance.study)}


def restore(config, instance, log, deadline, saved):
    """Restore JSON arrays and purchases, without running any physical solver."""
    if saved['version'] != 1 or saved['submission'] is not None or saved['study_hash'] != digest(instance.study):
        raise ValueError('incompatible, submitted or wrong-study checkpoint')
    ep = audit.Episode.__new__(audit.Episode)
    ep.config, ep.instance, ep.log, ep.deadline = config, instance, log, deadline
    ep.parent_call, ep.submission = None, None
    ep.request_count, ep.artifact_number = saved['request_count'], saved['artifact_number']
    ep.executed = deepcopy(saved['executed'])
    ep.schemas = {t['name']: t['parameters'] for t in audit.tool_definitions(config)}
    env = audit.Audit.__new__(audit.Audit)
    env._study, env.public = deepcopy(instance.study), deepcopy(instance.study['public'])
    env._environment = restore_episode(saved['environment'], log=ep._event if log else None)
    env._tools, env.submission = env._environment.tools, None
    ep.environment = env
    if (env._environment._config.public() != harder_config(budget=32).public()
            or list(env._environment._theta_true) != instance.study['private']['target_parameters']
            or env._environment._noise_seed != instance.study['private']['noise_seed']):
        raise ValueError('restored scientific configuration or target differs')
    if log:
        log.write_json('public/study.json', instance.study['public'])
        log.event('mixed_state_restored', role='harness', scientific_status=env.status(),
                  prior_tool_requests=ep.request_count, solver_calls=0)
    return ep


def migrate_legacy(parent, events, final, saved, study):
    """Import the first inspection-only checkpoint from complete durable events."""
    starts = [e['data'] for e in events if e['kind'] == 'environment_event'
              and e.get('event_kind') == 'episode_started']
    if len(starts) != 1 or saved.get('submission') is not None:
        raise ValueError('ambiguous legacy scientific state')
    start = starts[0]
    artifacts = {e['result_id']: e['artifact'] for e in events if e['kind'] == 'simulation_finished'}
    simulations, observations = {}, {(r['variable'], r['time']): deepcopy(r) for r in start['observations']}
    for e in events:
        if e['kind'] != 'environment_event':
            continue
        data = e['data']
        if e['event_kind'] == 'simulation':
            r = data['result']
            if r['result_id'] not in simulations:
                simulations[r['result_id']] = {
                    **{k: r[k] for k in ('theta', 'fidelity', 'charge', 'remaining', 'status', 'result_id')},
                    'baseline_values': r.get('values', []),
                    'trajectory': read_json(parent, artifacts[r['result_id']]) if r['status'] == 'success' else None}
        elif e['event_kind'] == 'measurement':
            r = data['result']
            observations.setdefault((r['variable'], r['time']), deepcopy(r))
    scientific = final['evaluation']['scientific_status']
    if saved['scientific_status'] != scientific:
        raise ValueError('legacy checkpoint and final scientific budget differ')
    state = {'version': 1, 'solver_key': list(_SOLVER_KEY), 'config': start['config'],
             'theta_true': start['theta_true'], 'target': start['target_artifact'],
             'noise_seed': study['private']['noise_seed'], 'state': 'active', 'submission': None,
             'ledger': scientific['ledger'], 'observations': list(observations.values()),
             'cache': list(simulations.values())}
    return {'version': 1, 'environment': state, 'submission': None, 'executed': saved['executed'],
            'request_count': final['evaluation']['tool_requests'], 'artifact_number': len(artifacts),
            'study_hash': digest(study)}


def prepare_resume(parent, *, mode, api_ceiling_usd=None):
    """Read-only preflight. Ambiguous activity fails closed before credentials."""
    parent = Path(parent).resolve()
    manifest = read_json(parent, 'manifest.json')
    if (manifest.get('termination_reason') in (None, 'running') or manifest['mode'] != mode
            or (parent/'resume_claim.json').exists()):
        raise ValueError('active attempt, changed mode or already continued parent')
    public = manifest['public_configuration']
    values = deepcopy(public)
    if api_ceiling_usd is not None:
        values['api_ceiling_usd'] = api_ceiling_usd
    config = ResumeConfig(**values)
    if Decimal(config.api_ceiling_usd) < Decimal(public['api_ceiling_usd']):
        raise ValueError('cumulative ceiling cannot decrease')
    if manifest['pricing'] != pricing_for_model(config.model):
        raise ValueError('pricing changed')
    for name in ('numpy', 'scipy'):
        if manifest['dependencies'][name] != version(name):
            raise ValueError('numerical dependency changed')
    for relative, expected in manifest['source_hashes'].items():
        if not relative.startswith('shared/'):
            continue
        actual = hashlib.sha256((audit.ROOT/relative).read_bytes()).hexdigest()
        if actual != expected and not (relative == MIGRATION_SOURCE and expected == MIGRATION_HASH):
            raise ValueError(f'prior scientific/API implementation changed: {relative}')
    messages, tools = read_json(parent, 'prompts.json'), read_json(parent, 'tools.json')
    if (digest(messages) != manifest['prompt_hash'] or digest(tools) != manifest['tool_schema_hash']
            or tools != audit.tool_definitions(config)):
        raise ValueError('frozen prompt or tool schema changed')
    events, torn = read_events(parent)
    if torn:
        raise ValueError('torn journal requires manual audit')
    final = next((e for e in reversed(events) if e['kind'] == 'run_finished'), None)
    if not final or final['evaluation']['completed']:
        raise ValueError('only finalized unsubmitted attempts can resume')
    study = read_json(parent, 'private/study.json')
    instance = audit.Instance(study, final['fixed_policy'])
    if instance.private() != manifest['PRIVATE_harness_instance_not_agent_input']:
        raise ValueError('private study identity changed')
    cp = read_json(parent, 'checkpoint.json')
    saved = cp['payload']
    if (digest(saved) != cp['payload_hash'] or not 0 <= cp['last_sequence'] <= len(events)
            or any(e['sequence'] > cp['last_sequence'] and e['kind'] == 'tool_requested' for e in events)):
        raise ValueError('checkpoint integrity or unfinished tool activity')
    if saved.get('inspection_only'):
        saved = migrate_legacy(parent, events, final, saved, study)
    restored = restore(config, instance, None, None, saved)
    if restored.environment.status() != final['evaluation']['scientific_status']:
        raise ValueError('restored budget disagrees with final ledger')
    history, sequences, pending, ids, executed, requests = deepcopy(messages), [], {}, [], {}, {}
    attempted, request_count = 0, 0
    for e in events:
        kind = e['kind']
        if kind == 'resume_started':
            history.append(deepcopy(e['message']))
        elif kind == 'token_count_requested':
            ids.append(int(e['request_id'].split('-')[-1]))
        elif kind == 'api_request_sent':
            attempted += 1
        elif kind == 'api_response' and e['response'].get('status') == 'completed':
            response = e['response']
            if response.get('model') != config.model or response.get('service_tier') != 'default':
                raise ValueError('unexpected prior model or tier')
            for item in response['output']:
                history.append(replay_output_item(item))
                if item['type'] == 'function_call':
                    if item['call_id'] in pending:
                        raise ValueError('ambiguous pending call ID')
                    pending[item['call_id']] = item
        elif kind == 'tool_requested' and e.get('role') == 'agent':
            request_count += 1
            requests[e['call_id']] = [e['name'], e['arguments']]
        elif kind == 'tool_result' and e.get('role') == 'agent':
            call = pending.pop(e['call_id'], None)
            if call is None or requests.get(e['call_id']) != [call['name'], call['arguments']]:
                raise ValueError('unmatched tool result')
            executed.setdefault(e['call_id'], [digest(requests[e['call_id']]), deepcopy(e['output'])])
            history.append({'type': 'function_call_output', 'call_id': e['call_id'],
                            'output': json.dumps(e['output'], ensure_ascii=False, allow_nan=False)})
            sequences.append(e['sequence'])
    if pending or digest(executed) != digest(saved['executed']) or request_count != saved['request_count']:
        raise ValueError('pending tool or deduplication state mismatch')
    status, reservations = final['api_budget'], {}
    for name in status['unsettled_requests']:
        count = read_json(parent, f'api/{name}-count-response.json')
        body = parent/f'api/{name}-request.json'
        limit = read_json(parent, body.relative_to(parent))['max_output_tokens'] if body.exists() else config.max_output_tokens
        reservations[name] = {'input_tokens': count['input_tokens'], 'max_output_tokens': limit}
    money = ApiBudget.restore(status, reservations, model=config.model)
    if money.ceiling != Decimal(public['api_ceiling_usd']):
        raise ValueError('saved API ceiling mismatch')
    money.ceiling = Decimal(config.api_ceiling_usd)
    elapsed = final['elapsed_seconds']
    if (attempted != final['model_responses'] or attempted >= config.max_responses
            or elapsed >= config.deadline_seconds or request_count >= config.max_tool_requests):
        raise ValueError('inconsistent or exhausted cumulative limits')
    remaining = restored.environment.status()['remaining']
    message = {'role': 'user', 'content':
        f'Continue this SAME interrupted audit, retaining the conversation and all purchased evidence. '
        f'{remaining:g} of the original 32 scientific credits remain. The user authorized a cumulative '
        f'API ceiling of ${config.api_ceiling_usd}, including earlier usage and reservations, not a new allowance. '
        'All other settings and cumulative limits are unchanged. Submission is allowed at any spend; '
        'there is no full-budget requirement. Do not start over.'}
    history.append(message)
    return {'parent': parent, 'manifest': manifest, 'events': events, 'config': config, 'instance': instance,
            'saved': saved, 'history': history, 'messages': messages, 'tools': tools,
            'output_sequences': sequences, 'money': money, 'responses': attempted,
            'next_generation': max(ids, default=0)+1, 'elapsed': elapsed,
            'comparisons': final['fixed_policy'], 'message': message}


async def run(parent, *, mode, api_ceiling_usd=None, root=audit.RUNS, gateway=None):
    resume = prepare_resume(parent, mode=mode, api_ceiling_usd=api_ceiling_usd)
    path, reason = await run_episode(audit.ROOT, root, mode=mode, config=resume['config'],
        instance=resume['instance'], adapter=audit.Adapter, gateway=gateway, resume=resume)
    print(f'{mode} continuation: {reason}; {path}', flush=True)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('check', 'dry-run', 'live'))
    parser.add_argument('parent')
    parser.add_argument('--api-ceiling-usd')
    args = parser.parse_args()
    if args.command == 'check':
        mode = read_json(Path(args.parent).resolve(), 'manifest.json')['mode']
        r = prepare_resume(args.parent, mode=mode, api_ceiling_usd=args.api_ceiling_usd)
        print(json.dumps({'resume_ready': True, 'prior_responses': r['responses'],
                          'scientific_remaining': 32-sum(x['charge'] for x in r['saved']['environment']['ledger']),
                          'api_budget': r['money'].status(), 'next_generation': r['next_generation']}, indent=2))
    else:
        asyncio.run(run(args.parent, mode=args.command, api_ceiling_usd=args.api_ceiling_usd))


if __name__ == '__main__':
    main()
