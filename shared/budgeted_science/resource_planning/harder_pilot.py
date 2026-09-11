"""CPU-only harder-toy development, frozen evaluation, and offline reports.

Commands: development; pilot --freeze DEVELOPMENT_DIR; render RUN_DIR.
No agent integration or credentials. Each run has a unique ignored directory.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import json
import os
import time

from budgeted_science.agents.records import RunLog, digest, read_events, utc_now
from .experiment import source_hashes, versions, REPO

OUTPUT = REPO / 'demos/planning/runs/resource_planning_v2'
DESIGN = {'development_targets': list(range(5000, 5008)), 'evaluation_targets': list(range(6000, 6020)),
          'noise_replicates': [0, 1], 'policy_seed': 0, 'budgets': [40, 32, 24],
          'policies': ['local', 'random', 'adaptive'], 'episode_seconds': 300,
          'selection': 'Keep 40 unless local development success >=90%; then try 32, then 24. Never select using evaluation targets.'}


def run_random(tools, seed, deadline, emit):
    """Original fixed policy at 40; fewer high solves below 40, then cheap fill."""
    import numpy as np
    from scipy.stats import qmc
    from .policies import run_policy, fit_evidence
    from .emulator import GPSettings, check_deadline
    config = tools.public_config
    if config['budget'] == 40:
        return run_policy(tools, 'random', seed, log=emit, deadline=deadline)
    nlow = int((config['budget'] - config['costs']['high'] - config['costs']['measurement']) / config['costs']['low'])
    bounds = np.array(config['bounds'])
    points = qmc.Sobol(3, scramble=True, seed=seed).random_base2(5)
    locations = bounds[:, 0] + points * np.diff(bounds).ravel()
    menu = [(v, t) for v in ('x', 'y') for t in config['working_times'] if t not in (0, 1)]
    rng = np.random.default_rng(seed + 71)
    selected = menu[int(rng.integers(len(menu)))]
    emit('fixed_plan', low_locations=locations[:nlow].tolist(), measurement=list(selected), high=locations[0].tolist())
    for theta in locations[:nlow]:
        check_deadline(deadline)
        tools.simulate_low(theta.tolist())
    tools.simulate_high(locations[0].tolist())
    tools.measure_target(*selected)
    fitted = fit_evidence(tools.evidence(), config, seed, GPSettings(), deadline)
    emit('inference', **fitted.diagnostics())
    return {'submission': tools.submit(fitted.estimate())}


def worker(spec, root):
    # Spawned processes set thread limits before importing NumPy/SciPy.
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '1'
    import numpy as np
    from .config import harder_config
    from .environment import Episode
    from .local_policy import run_local_policy
    from .policies import run_policy
    log = RunLog(Path(root) / 'episodes', spec['policy'])
    config = harder_config(spec['budget'])
    bounds = np.array(config.bounds)
    theta = np.random.default_rng(spec['target_seed']).uniform(bounds[:, 0], bounds[:, 1])
    noise_seed = spec['target_seed'] * 10 + spec['noise_replicate']
    log.write_json('manifest.json', {**spec, 'public_configuration': config.public(),
                                    'PRIVATE_instance': {'theta': theta.tolist(), 'noise_seed': noise_seed}})
    def emit(kind, **data):
        for field in ('artifact', 'target_artifact'):
            if data.get(field) is not None:
                data[field + '_path'] = log.write_json(f'numerical/{log._sequence + 1:06d}-{field}.json', data.pop(field))
        log.event(kind, **data)
    episode, reason, details = None, 'failed', None
    started = time.monotonic()
    try:
        episode = Episode(theta, config, log=emit, noise_seed=noise_seed)
        deadline = started + DESIGN['episode_seconds']
        if spec['policy'] == 'local':
            details = run_local_policy(episode.tools, seed=0, log=emit, deadline=deadline)
        elif spec['policy'] == 'random':
            details = run_random(episode.tools, 0, deadline, emit)
        else:
            details = run_policy(episode.tools, 'adaptive', seed=0, log=emit, deadline=deadline)
        reason = 'submitted' if episode.evaluate()['valid'] else 'no_submission'
    except Exception as exc:
        emit('failure', error=log.redactor.error(exc))
        if episode:
            episode.abort(type(exc).__name__)
        reason = 'timeout' if isinstance(exc, TimeoutError) else 'failed'
    status = episode.tools.get_status() if episode else None
    result = {**spec, 'path': str(log.path), 'termination': reason,
              'evaluation': episode.evaluate() if episode else None,
              'scientific_status': status, 'details': details,
              'elapsed_seconds': time.monotonic() - started}
    log.write_json('result.json', result)
    log.event('episode_finished', result=result)
    log.close()
    return result


def select_budget(rows):
    selected = 40
    for budget in (40, 32):
        group = [r for r in rows if r['budget'] == budget and r['policy'] == 'local']
        if not group or sum(bool(r.get('evaluation') and r['evaluation']['success']) for r in group) / len(group) < .9:
            break
        selected = 32 if budget == 40 else 24
    return selected


def aggregate(rows):
    import numpy as np
    groups = []
    for budget, policy in sorted({(r['budget'], r['policy']) for r in rows}):
        group = [r for r in rows if r['budget'] == budget and r['policy'] == policy]
        valid = [r for r in group if r.get('evaluation') and r['evaluation']['valid']]
        errors = [r['evaluation']['parameter_error'] for r in valid]
        allocations = []
        for r in valid:
            ledger = r['scientific_status']['ledger']
            allocations.append([sum(e['kind'] == kind for e in ledger) for kind in ('simulate_low', 'simulate_high', 'measure_target')])
        groups.append({'budget': budget, 'policy': policy, 'attempts': len(group),
                       'successes': sum(r['evaluation']['success'] for r in valid),
                       'incomplete': len(group) - len(valid),
                       'median_error': float(np.median(errors)) if errors else None,
                       'mean_error': float(np.mean(errors)) if errors else None,
                       'mean_relative_percent': (np.mean([r['evaluation']['errors'] for r in valid], axis=0) * 5).tolist() if valid else None,
                       'mean_purchases': np.mean(allocations, axis=0).tolist() if valid else None,
                       'median_seconds': float(np.median([r['elapsed_seconds'] for r in group]))})
    paired = {}
    for other in ('random', 'adaptive'):
        a = {(r['target_seed'],r['noise_replicate']): r for r in rows if r['policy'] == 'local'}
        b = {(r['target_seed'],r['noise_replicate']): r for r in rows if r['policy'] == other}
        if a.keys() != b.keys() or not a:
            continue
        differences = []
        for target in sorted({key[0] for key in a}):
            delta = []
            for key in a:
                if key[0] == target:
                    success = lambda r: bool(r.get('evaluation') and r['evaluation']['success'])
                    delta.append(int(success(a[key])) - int(success(b[key])))
            differences.append(np.mean(delta))
        samples = np.random.default_rng(934).choice(differences, (2000,len(differences)), replace=True).mean(axis=1)
        paired[other] = {'local_minus_other_success': float(np.mean(differences)),
                         'target_bootstrap_95': np.quantile(samples,[.025,.975]).tolist(),
                         'targets': len(differences)}
    return {'groups': groups, 'paired_success_differences': paired}


def render(root):
    root = Path(root)
    events, torn = read_events(root)
    rows = [e['result'] for e in events if e['kind'] == 'result']
    manifest = json.loads((root / 'manifest.json').read_text())
    summary = aggregate(rows)
    summary.update(phase=manifest['phase'], selected_budget=select_budget(rows) if manifest['phase'] == 'development' else manifest['selected_budget'],
                   complete=bool(events and events[-1]['kind'] == 'finished' and not torn))
    (root / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    lines = ['# Harder resource-planning CPU pilot', '', f"Phase: {summary['phase']}; selected budget: {summary['selected_budget']}; complete: {summary['complete']}.", '',
             '| Budget | Policy | Successes / attempts | Median worst error | Mean worst error | Incomplete |',
             '|---:|---|---:|---:|---:|---:|']
    for g in summary['groups']:
        lines.append(f"| {g['budget']} | {g['policy']} | {g['successes']} / {g['attempts']} | {g['median_error']} | {g['mean_error']} | {g['incomplete']} |")
    lines += ['', 'Errors are normalized by the 5% tolerance; passing requires <=1 for every parameter.',
              'Budgets are selected using development targets only. Noise replicates share targets; paired uncertainty resamples targets.',
              'The local method uses purchased-data affine approximations and a locally constant high/low correction; it is not an optimal policy.',
              'No LLM was evaluated. Local analysis is scientifically free; every actual simulation or new observation is charged.',
              'Logs contain private targets; review before sharing.', '']
    (root / 'report.md').write_text('\n'.join(lines), encoding='utf-8')
    return summary


def campaign(phase, freeze=None, workers=2, output=OUTPUT):
    from .config import harder_config
    from .local_policy import SETTINGS
    hashes = source_hashes()
    selected = 40
    if phase == 'pilot':
        parent = Path(freeze)
        lock = json.loads((parent / 'freeze.json').read_text())
        if (lock['source_hashes'] != hashes or lock['versions'] != versions()
                or lock['design'] != DESIGN or lock['settings'] != SETTINGS):
            raise ValueError('code, numerical runtime, or design changed since development; rerun development')
        if lock['public_configuration'] != harder_config(lock['selected_budget']).public():
            raise ValueError('configuration changed since development')
        selected = lock['selected_budget']
    elif phase != 'development':
        raise ValueError('unknown phase')
    log = RunLog(output, phase)
    manifest = {'phase': phase, 'created_utc': utc_now(), 'design': DESIGN, 'settings': SETTINGS,
                'source_hashes': hashes, 'versions': versions(), 'selected_budget': selected,
                'public_configuration': harder_config(selected).public(), 'development': str(freeze) if freeze else None}
    log.write_json('manifest.json', manifest)
    specs = [{'policy': policy, 'budget': budget, 'target_seed': target, 'noise_replicate': noise}
             for budget in (DESIGN['budgets'] if phase == 'development' else [selected])
             for target in DESIGN['development_targets' if phase == 'development' else 'evaluation_targets']
             for noise in DESIGN['noise_replicates']
             for policy in (['local'] if phase == 'development' else DESIGN['policies'])]
    log.event('started', attempts=len(specs))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(worker, spec, str(log.path)): spec for spec in specs}
        for i, future in enumerate(as_completed(futures), 1):
            try:
                result = future.result()
            except Exception as exc:
                result = {**futures[future], 'termination': 'worker_error', 'evaluation': None,
                          'elapsed_seconds': 0, 'error': type(exc).__name__}
            log.event('result', result=result)
            print(f"{phase} {i}/{len(specs)} {result['policy']} B={result['budget']} {result['termination']}", flush=True)
    unchanged = hashes == source_hashes()
    log.event('finished', source_unchanged=unchanged)
    summary = render(log.path)
    if phase == 'development' and unchanged and not any(g['incomplete'] for g in summary['groups']):
        selected = summary['selected_budget']
        log.write_json('freeze.json', {**manifest, 'selected_budget': selected,
                                      'public_configuration': harder_config(selected).public()})
    log.close()
    print(str(log.path), flush=True)
    return log.path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('development', 'pilot', 'render'))
    parser.add_argument('run_dir', nargs='?', type=Path)
    parser.add_argument('--freeze', type=Path)
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    if args.phase == 'render':
        print(json.dumps(render(args.run_dir), indent=2))
    elif args.phase == 'pilot' and not args.freeze:
        parser.error('pilot requires --freeze DEVELOPMENT_DIR')
    elif not 1 <= args.workers <= 4:
        parser.error('workers must be between 1 and 4')
    else:
        campaign(args.phase, args.freeze, args.workers)


if __name__ == '__main__':
    main()
