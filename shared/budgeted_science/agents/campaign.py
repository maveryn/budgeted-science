"""Frozen five-case campaign. No credentials or network access on import."""

import argparse
import asyncio
from contextlib import contextmanager
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import time
from types import SimpleNamespace

import numpy as np

from .records import RunLog, digest, read_events, utc_now
from .resource import (ResourceAdapter, ResourceInstance, ResourceRunConfig,
                       environment_logger, prompts, tool_definitions)
from .runner import provenance, run_episode
from .spending import pricing_for_model

REPO = Path(__file__).resolve().parents[3]
OUTPUT = REPO / 'demos/planning/runs/resource_five_case'
MODELS = ('gpt-5.6-sol', 'gpt-5.6-luna')
POLICIES = ('local', 'random_local', 'random', 'adaptive')
METHODS = MODELS + POLICIES
SEEDS = (6000, 6020, 6021, 6022, 6023)
ANCHORS = {
    MODELS[0]: REPO / 'demos/planning/runs/resource_agent_v2/20260911T134140Z-live-084f45e206',
    MODELS[1]: REPO / 'demos/planning/runs/resource_agent_v2/20260911T141328Z-live-c76209f003',
}


def configuration(model=MODELS[0]):
    return ResourceRunConfig(model=model, environment_version='v2', scientific_budget=32,
                             api_ceiling_usd='3.00', require_full_budget=True)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def tree_hashes(path):
    path = Path(path).resolve()
    result = {}
    for file in sorted(path.rglob('*')):
        if file.is_symlink() or not file.resolve().is_relative_to(path):
            raise ValueError('linked run artifacts are not supported')
        if file.is_file():
            result[file.relative_to(path).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
    return result


def validate_scoring(evaluation, instance):
    if not evaluation.get('valid'):
        return
    truth = np.asarray(instance.theta)
    estimate = np.asarray(evaluation['theta_hat'])
    errors = np.abs(estimate - truth) / (.05 * np.abs(truth))
    if (estimate.shape != (3,) or not np.all(np.isfinite(estimate))
            or not np.array_equal(evaluation['theta_true'], truth)
            or not np.allclose(evaluation['errors'], errors, atol=1e-12, rtol=1e-12)
            or not np.isclose(evaluation['parameter_error'], errors.max(), atol=1e-12, rtol=1e-12)
            or evaluation['success'] != bool(errors.max() <= 1)):
        raise ValueError('saved scoring disagrees with instance or submission')


def result_row(seed, method, payload, path, *, imported=False, agent=False):
    evaluation = payload['evaluation']
    return {'case_seed': seed, 'noise_replicate': 0, 'method': method,
            'cohort': 'exploratory' if seed == 6000 else 'new', 'imported': imported,
            'evaluation': evaluation,
            'scientific_status': evaluation['scientific_status'] if agent else payload['scientific_status'],
            'termination_reason': payload['termination_reason'],
            'elapsed_seconds': payload['elapsed_seconds'], 'api_budget': payload.get('api_budget'),
            'model_responses': payload.get('model_responses'), 'path': str(Path(path).resolve())}


def validate_anchor(path, model):
    """Read-only import validation; never rerun the imported experiment."""
    path = Path(path).resolve()
    manifest, payload = read_json(path / 'manifest.json'), read_json(path / 'evaluation.json')
    config, instance = configuration(model), ResourceInstance.from_seed(6000)
    if (manifest['mode'] != 'live' or manifest['termination_reason'] != 'submitted'
            or manifest['public_configuration'] != config.public()
            or manifest['pricing'] != pricing_for_model(model)):
        raise ValueError('anchor model/settings/outcome do not match frozen campaign')
    private = manifest['PRIVATE_harness_instance_not_agent_input']
    if (private['target_parameters'] != list(instance.theta)
            or private['target_seed'] != 6000 or private['noise_seed'] != 60000):
        raise ValueError('anchor instance mismatch')
    events, torn = read_events(path)
    if torn:
        raise ValueError('anchor log has a torn tail')
    final = next(e for e in reversed(events) if e['kind'] == 'run_finished')
    if final['evaluation'] != payload['evaluation'] or final['api_budget'] != payload['api_budget']:
        raise ValueError('anchor evaluation differs from authoritative events')
    initial = next(e['data']['observations'] for e in events if e['kind'] == 'environment_event'
                   and e.get('role') == 'agent' and e.get('event_kind') == 'episode_started')
    expected_prompt = prompts(config, SimpleNamespace(initial_observations=initial))
    if (read_json(path / 'prompts.json') != expected_prompt
            or digest(expected_prompt) != manifest['prompt_hash']
            or read_json(path / 'tools.json') != tool_definitions(config)):
        raise ValueError('anchor scientific prompt or schema changed')
    for name in ('config.py', 'environment.py', 'emulator.py', 'policies.py', 'local_policy.py', 'harder_pilot.py'):
        relative = 'shared/budgeted_science/resource_planning/' + name
        if hashlib.sha256((REPO / relative).read_bytes()).hexdigest() != manifest['source_hashes'][relative]:
            raise ValueError('anchor scientific code changed: ' + name)
    validate_scoring(payload['evaluation'], instance)
    if payload['evaluation']['spent'] != 32 or payload['api_budget']['unsettled_requests']:
        raise ValueError('anchor is not a complete, settled 32-credit run')
    rows = [result_row(6000, model, payload, path, imported=True, agent=True)]
    if model == MODELS[0]:
        for policy in ('local', 'random', 'adaptive'):
            comparison = read_json(path / 'comparisons' / (policy + '.json'))
            if comparison != payload['comparisons'][policy] or comparison != final['fixed_policy'][policy]:
                raise ValueError('anchor baseline record mismatch')
            validate_scoring(comparison['evaluation'], instance)
            rows.append(result_row(6000, policy, comparison, path / 'comparisons' / (policy + '.json'), imported=True))
    return rows, {'path': str(path), 'hashes': tree_hashes(path)}


def slot_id(seed, method):
    return f'{seed}-{method}'


def prepared_manifest(*, rehearsal=False):
    seeds = (6000, 5000, 5001, 5002, 5003) if rehearsal else SEEDS
    order = []
    for i, seed in enumerate(seeds[1:]):
        order += [slot_id(seed, m) for m in (MODELS if i % 2 == 0 else MODELS[::-1])]
    return {'schema_version': 1, 'created_utc': utc_now(), 'rehearsal': rehearsal,
            'seeds': list(seeds), 'noise_replicate': 0, 'policy_seed': 0,
            'models': list(MODELS), 'policies': list(POLICIES), 'live_order': order,
            'live_slots': 8, 'api_ceiling_usd': '24.00', 'episode_ceiling_usd': '3.00',
            'configurations': {m: configuration(m).public() for m in MODELS},
            'pricing': {m: pricing_for_model(m) for m in MODELS},
            'PRIVATE_cases': {str(s): ResourceInstance.from_seed(s).private() for s in seeds},
            'cohorts': {'exploratory': [6000], 'new': list(seeds[1:])},
            **provenance(REPO)}


def prepare(output=OUTPUT, *, rehearsal=False):
    rows, imports = [], {}
    for model, path in ANCHORS.items():
        imported, reference = validate_anchor(path, model)
        rows += imported
        imports[model] = reference
    manifest = prepared_manifest(rehearsal=rehearsal)
    manifest['imports'] = imports
    manifest['slots'] = [{'id': slot_id(s, m), 'case_seed': s, 'method': m}
                         for s in manifest['seeds'] for m in METHODS]
    log = RunLog(output, 'rehearsal' if rehearsal else 'prepared')
    try:
        log.write_json('manifest.json', manifest)
        log.write_json('freeze.json', {'manifest_hash': digest(manifest)})
        log.event('prepared', manifest_hash=digest(manifest))
        for row in rows:
            log.event('slot_imported', slot_id=slot_id(row['case_seed'], row['method']), result=row)
        log._stream.flush()
        os.fsync(log._stream.fileno())
    finally:
        log.close()
    render(log.path)
    return log.path


def verify(root):
    root = Path(root).resolve()
    manifest = read_json(root / 'manifest.json')
    if digest(manifest) != read_json(root / 'freeze.json')['manifest_hash']:
        raise ValueError('frozen campaign manifest changed')
    current = provenance(REPO)
    for key in ('source_hashes', 'dependencies'):
        if current[key] != manifest[key]:
            raise ValueError('campaign provenance changed: ' + key)
    for model, reference in manifest['imports'].items():
        if tree_hashes(reference['path']) != reference['hashes']:
            raise ValueError('imported artifacts changed: ' + model)
    for model in MODELS:
        if manifest['configurations'][model] != configuration(model).public() or manifest['pricing'][model] != pricing_for_model(model):
            raise ValueError('campaign settings or pricing changed')
    expected = {slot_id(s, m) for s in manifest['seeds'] for m in METHODS}
    if len(manifest['slots']) != 30 or {s['id'] for s in manifest['slots']} != expected:
        raise ValueError('invalid campaign slots')
    return manifest


def state(root):
    manifest = read_json(Path(root) / 'manifest.json')
    events, torn = read_events(root)
    if torn:
        raise ValueError('torn campaign journal requires inspection')
    slots = {s['id']: {**s, 'status': 'pending'} for s in manifest['slots']}
    for event in events:
        kind = event['kind']
        if kind not in ('slot_imported', 'slot_started', 'slot_finished'):
            continue
        slot = slots[event['slot_id']]
        expected = 'started' if kind == 'slot_finished' else 'pending'
        if slot['status'] != expected:
            raise ValueError('duplicate or out-of-order campaign slot')
        slot.update(status={'slot_imported': 'imported', 'slot_started': 'started', 'slot_finished': 'finished'}[kind])
        if 'result' in event:
            slot['result'] = event['result']
        if 'output_root' in event:
            slot['output_root'] = event['output_root']
    return slots


@contextmanager
def journal(root):
    """OS-held writer lock releases on process exit; started slots remain spent."""
    root = Path(root).resolve()
    lock = (root / 'writer.lock').open('a+b')
    if lock.tell() == 0:
        lock.write(b'0')
        lock.flush()
    lock.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        events, torn = read_events(root)
        if torn:
            raise ValueError('torn campaign journal requires inspection')
        log = RunLog.__new__(RunLog)
        from .records import Redactor
        log.path, log.redactor = root, Redactor()
        log._sequence = len(events)
        log._stream = (root / 'events.jsonl').open('a', encoding='utf-8')
        try:
            yield log
        finally:
            log.close()
    finally:
        lock.close()


def durable_event(log, kind, **data):
    log.event(kind, **data)
    log._stream.flush()
    os.fsync(log._stream.fileno())


def cpu_episode(seed, method, output):
    from budgeted_science.resource_planning.environment import Episode
    from budgeted_science.resource_planning.harder_pilot import run_random
    from budgeted_science.resource_planning.local_policy import run_local_policy
    from budgeted_science.resource_planning.random_local import run_random_local
    from budgeted_science.resource_planning.policies import run_policy
    log = RunLog(output, method)
    instance, config = ResourceInstance.from_seed(seed), configuration()
    started, details, reason, episode = time.monotonic(), None, 'submitted', None
    log.write_json('manifest.json', {'method': method, 'case_seed': seed, 'policy_seed': 0,
                                    'public_configuration': config.environment_config().public(),
                                    'PRIVATE_instance': instance.private(), **provenance(REPO)})
    try:
        episode = Episode(instance.theta, config.environment_config(), noise_seed=instance.noise_seed,
                          log=environment_logger(log, method, lambda: None))
        options = {'seed': 0, 'deadline': started + 300, 'log': lambda kind, **data: log.event(kind, **data)}
        if method == 'local':
            details = run_local_policy(episode.tools, **options)
        elif method == 'random_local':
            details = run_random_local(episode.tools, **options)
        elif method == 'random':
            details = run_random(episode.tools, 0, options['deadline'], options['log'])
        elif method == 'adaptive':
            details = run_policy(episode.tools, policy='adaptive', **options)
        else:
            raise ValueError('unknown CPU policy')
    except Exception as exc:
        reason = 'deadline' if isinstance(exc, TimeoutError) else 'baseline_error'
        log.event('baseline_error', error=log.redactor.error(exc))
        if episode:
            episode.abort(reason)
    evaluation = episode.evaluate() if episode else {'valid': False, 'success': False}
    status = episode.tools.get_status() if episode else {}
    payload = {'evaluation': evaluation, 'scientific_status': status, 'termination_reason': reason,
               'policy_seed': 0, 'details': details, 'elapsed_seconds': time.monotonic() - started}
    log.write_json('result.json', payload)
    log.event('cpu_finished', result=payload)
    log.close()
    validate_scoring(evaluation, instance)
    return result_row(seed, method, payload, log.path)


class CampaignAdapter(ResourceAdapter):
    """Private CPU snapshots are linked, never inserted into model history."""
    def __init__(self, instance, comparisons):
        self.instance, self.comparisons = instance, deepcopy(comparisons)

    def run_comparisons(self, config, instance, log):
        if instance != self.instance or config.environment_config() != configuration().environment_config():
            raise ValueError('comparison snapshot instance/config mismatch')
        for policy, payload in self.comparisons.items():
            validate_scoring(payload['evaluation'], instance)
            log.write_json('comparisons/' + policy + '.json', payload)
        log.event('campaign_comparisons_reused', policies=list(self.comparisons))
        return deepcopy(self.comparisons)


def comparison_snapshots(root, seed):
    snapshots = {}
    for policy in POLICIES:
        slot = state(root)[slot_id(seed, policy)]
        if slot['status'] not in ('imported', 'finished'):
            raise ValueError('CPU comparison is not ready')
        row = slot['result']
        path = Path(row['path'])
        payload = read_json(path if path.is_file() else path / 'result.json')
        if result_row(seed, policy, payload, path, imported=row['imported']) != row:
            raise ValueError('CPU snapshot changed after recording')
        snapshots[policy] = payload
    return snapshots


def agent_row(seed, method, path):
    path = Path(path).resolve()
    manifest, payload = read_json(path / 'manifest.json'), read_json(path / 'evaluation.json')
    private, instance = manifest['PRIVATE_harness_instance_not_agent_input'], ResourceInstance.from_seed(seed)
    if (manifest['public_configuration'] != configuration(method).public()
            or private['target_parameters'] != list(instance.theta)
            or private['target_seed'] != seed or private['noise_seed'] != 10 * seed):
        raise ValueError('agent result does not match campaign slot')
    events, torn = read_events(path)
    final = next((e for e in reversed(events) if e['kind'] == 'run_finished'), None)
    if torn or final is None or manifest['termination_reason'] == 'running':
        raise ValueError('unfinished agent attempt requires inspection; not restarting')
    if payload['evaluation'] != final['evaluation'] or payload['api_budget'] != final['api_budget']:
        raise ValueError('agent report differs from authoritative records')
    validate_scoring(payload['evaluation'], instance)
    budget = payload['api_budget']
    committed = Decimal(budget['committed_upper_usd'])
    if not committed.is_finite() or not 0 <= committed <= 3 or Decimal(budget['ceiling_usd']) != 3:
        raise ValueError('episode API spending exceeded frozen ceiling')
    return result_row(seed, method, payload, path, agent=True)


def fatal_agent_error(path):
    events, _ = read_events(path)
    reason = read_json(Path(path) / 'manifest.json')['termination_reason']
    fatal = reason in ('usage_exceeded_reservation', 'missing_or_invalid_usage',
                       'invalid_token_count_response', 'unexpected_model_or_service_tier')
    for event in events:
        if event['kind'] == 'run_error':
            error = event.get('error', {})
            fatal |= error.get('status_code') in (401, 403)
            fatal |= error.get('class') in ('ValueError', 'AssertionError', 'AccountingUnavailable')
    return fatal


def charge_bound(slots):
    """Reserve the whole $3 for orphaned launches; never redistribute it."""
    total = Decimal(0)
    for slot in slots.values():
        if slot['method'] not in MODELS or slot['status'] == 'imported':
            continue
        if slot['status'] == 'started':
            total += Decimal(3)
        elif slot['status'] == 'finished':
            total += Decimal(slot['result']['api_budget']['committed_upper_usd'])
    return total


def recover_finalized(log):
    """Recover journal gaps after finalization, never repeat model or tool work."""
    for slot in state(log.path).values():
        if slot['status'] != 'started':
            continue
        directory = Path(slot['output_root'])
        children = sorted(p for p in directory.iterdir() if p.is_dir()) if directory.exists() else []
        if len(children) != 1:
            raise ValueError('ambiguous started slot; manual inspection required: ' + slot['id'])
        path = children[0]
        if slot['method'] in MODELS:
            seen = set()
            while (path / 'resume_claim.json').exists():
                if str(path) in seen:
                    raise ValueError('cycle in explicit resume chain')
                seen.add(str(path))
                path = Path(read_json(path / 'resume_claim.json')['child']).resolve()
            row = agent_row(slot['case_seed'], slot['method'], path)
        else:
            row = result_row(slot['case_seed'], slot['method'], read_json(path / 'result.json'), path)
            validate_scoring(row['evaluation'], ResourceInstance.from_seed(slot['case_seed']))
        durable_event(log, 'slot_finished', slot_id=slot['id'], result=row, recovered=True)
        if slot['method'] in MODELS and fatal_agent_error(path):
            durable_event(log, 'campaign_halted', reason='recovered systemic API/accounting failure')
            raise RuntimeError('recovered systemic failure requires inspection')


async def execute(root, *, mode, continuation=False, key_file=None, gateway_factory=None):
    root = Path(root).resolve()
    manifest = verify(root)
    if mode not in ('live', 'dry-run') or (mode == 'dry-run') != manifest['rehearsal']:
        raise ValueError('rehearsal/live campaign mode mismatch')
    if mode == 'live' and gateway_factory is not None:
        raise ValueError('live campaign cannot substitute a fake gateway')
    with journal(root) as log:
        old = read_events(root)[0]
        if not continuation and any(e['kind'] == 'slot_started' for e in old):
            raise ValueError('campaign already attempted; use explicit continue')
        if any(e['kind'] == 'campaign_halted' for e in old):
            raise ValueError('campaign halted on systemic failure; inspect before further execution')
        recover_finalized(log)
        durable_event(log, 'campaign_execution', mode=mode, continuation=continuation)
        for seed in manifest['seeds']:
            for method in POLICIES:
                identifier = slot_id(seed, method)
                if state(root)[identifier]['status'] != 'pending':
                    continue
                output = root / 'episodes' / identifier
                durable_event(log, 'slot_started', slot_id=identifier, output_root=str(output))
                row = cpu_episode(seed, method, output)
                durable_event(log, 'slot_finished', slot_id=identifier, result=row)
                print(f'CPU {identifier}: {row["termination_reason"]}', flush=True)
        for identifier in manifest['live_order']:
            slots = state(root)
            slot = slots[identifier]
            if slot['status'] != 'pending':
                continue
            verify(root)
            launched = sum(s['method'] in MODELS and s['status'] in ('started', 'finished') for s in slots.values())
            if launched >= 8 or charge_bound(slots) + 3 > Decimal(manifest['api_ceiling_usd']):
                raise ValueError('campaign launch ceiling reached')
            seed, method = slot['case_seed'], slot['method']
            instance = ResourceInstance.from_seed(seed)
            adapter = CampaignAdapter(instance, comparison_snapshots(root, seed))
            output = root / 'episodes' / identifier
            durable_event(log, 'slot_started', slot_id=identifier, output_root=str(output), reserved_usd='3.00')
            print(f'Starting {mode} {identifier}', flush=True)
            try:
                gateway = gateway_factory(method, seed) if gateway_factory else None
                path, reason = await run_episode(REPO, output, mode=mode, config=configuration(method),
                    instance=instance, adapter=adapter, key_file=key_file, gateway=gateway)
                row = agent_row(seed, method, path)
                durable_event(log, 'slot_finished', slot_id=identifier, result=row)
                render(root)
                print(f'Finished {identifier}: {reason}; success={row["evaluation"].get("success", False)}; '
                      f'API upper=${row["api_budget"]["committed_upper_usd"]}', flush=True)
                if fatal_agent_error(path):
                    raise RuntimeError('systemic API/accounting failure')
            except Exception as exc:
                durable_event(log, 'campaign_halted', reason=log.redactor.error(exc))
                render(root)
                raise
        verify(root)
        durable_event(log, 'campaign_finished', new_api_committed_upper_usd=str(charge_bound(state(root))))
    return render(root)


def render(root):
    from .campaign_reporting import render_campaign
    return render_campaign(Path(root), state(root))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('prepare', 'dry-run', 'live', 'continue', 'render'))
    parser.add_argument('run_dir', nargs='?', type=Path)
    parser.add_argument('--output-root', type=Path, default=OUTPUT)
    parser.add_argument('--api-key-file', type=Path)
    args = parser.parse_args()
    if args.api_key_file and args.operation not in ('live', 'continue'):
        parser.error('credentials are only accepted for live execution')
    if args.operation in ('prepare', 'dry-run'):
        if args.run_dir:
            parser.error('prepare/dry-run create a new campaign, not an existing run directory')
        root = prepare(args.output_root, rehearsal=args.operation == 'dry-run')
        print(f'Campaign: {root}', flush=True)
        if args.operation == 'dry-run':
            asyncio.run(execute(root, mode='dry-run'))
    else:
        if args.run_dir is None:
            parser.error('this operation requires a campaign directory')
        root = args.run_dir
        if args.operation == 'render':
            render(root)
        else:
            mode = 'dry-run' if read_json(root / 'manifest.json')['rehearsal'] else 'live'
            if args.operation == 'live' and mode != 'live':
                parser.error('cannot run a rehearsal as live')
            asyncio.run(execute(root, mode=mode, continuation=args.operation == 'continue', key_file=args.api_key_file))
    print(f'Report: {root / "report.md"}', flush=True)


if __name__ == '__main__':
    main()
