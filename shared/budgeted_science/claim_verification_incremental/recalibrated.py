"""Severity-recalibrated CPU experiment; no model transport or credentials.

Freeze selection rules and policies before either cohort is computed. Preserve
missing categories and failures. Never choose studies by policy performance.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np

from ..agents.records import RunLog, digest, json_text, read_events
from ..claim_verification.numerics import (
    Backend, BOUNDS, configuration, output_grid, peak, reference, reported_value)
from ..claim_verification.studies import make_study, validate_study
from .pilot import ROOT, POLICIES, source_provenance, evaluate_policy, refine_config, check_diagnostic

VERSION = "claim-verification-recalibrated-v1"
COHORTS = {"development": tuple(range(7100, 7106)), "fresh": tuple(range(7200, 7206))}
STEPS = (.005, .01, .02, .04, .08, .16, .32)
SPACINGS = (.1, .25, .5, 1., 2., 4.)
PHASES = (0., .25, .5, .75)
MIXED_STEPS = (.04, .08, .16, .32)
MIXED_SPACINGS = (.5, 1., 2., 4.)
SLOTS = tuple((family, label) for family in ("integration", "sampling", "mixed")
              for label in ("valid", "invalid"))
BANDS = {"valid": (.005, .04, .02), "invalid": (.06, .15, .08)}
COMPONENT_MIN = .01


def protocol():
    return {"version": VERSION, "cohorts": COHORTS, "steps": STEPS,
            "spacings": SPACINGS, "phases": PHASES, "mixed_steps": MIXED_STEPS,
            "mixed_spacings": MIXED_SPACINGS, "slots": SLOTS, "bands": BANDS,
            "component_min": COMPONENT_MIN, "budget": 8, "tolerance": .05,
            "policies": POLICIES, "estimator": "extrapolation",
            "random_seed_rule": "10000 + case ordinal across both cohorts",
            "selection": "nearest target error inside inclusive severity band; ties by configuration order; never by policy result",
            "fresh_rule": "same frozen rules; no replacements, widened bands or retuning",
            "diagnostic_budgets": (8, 10, 12), "api_calls": 0, "api_usd": 0}


def candidate_configs():
    rows = [("integration", configuration("Euler", dt=dt)) for dt in STEPS]
    rows += [("sampling", configuration("Euler", dt=.005, times=output_grid(s, p)))
             for s in SPACINGS for p in PHASES]
    rows += [("mixed", configuration("Euler", dt=dt, times=output_grid(s, p)))
             for dt in MIXED_STEPS for s in MIXED_SPACINGS for p in PHASES]
    return rows


def select_candidate(sweep, family, label):
    lo, hi, target = BANDS[label]
    candidates = [r for r in sweep if r['family'] == family and r['status'] == 'success'
                  and lo <= r['relative_error'] <= hi
                  and (family != 'mixed' or
                       (abs(r['integration_component']) >= COMPONENT_MIN
                        and abs(r['sampling_component']) >= COMPONENT_MIN))]
    return min(candidates, key=lambda r: (abs(r['relative_error']-target), r['order'])) if candidates else None


def commission_system(log, backend, cohort, seed, system_index):
    bounds = np.asarray(BOUNDS)
    theta = np.random.default_rng(seed).uniform(bounds[:, 0], bounds[:, 1])
    ref = reference(theta)
    log.write_json(f"private/references/{seed}.json", {"theta": theta.tolist(), **ref})
    sweep = []
    for order, (family, config) in enumerate(candidate_configs()):
        run, hit = backend.get(theta, config)
        row = {"order": order, "family": family, "config": config,
               "status": run['status'], "backend_cache_hit": hit, "run": run}
        if run['status'] == 'success':
            q = reported_value(run)
            # Max over ALL Euler nodes is exact for its piecewise-linear curve.
            # This private decomposition is for commissioning, never a tool reply.
            dense_q = float(np.max(np.asarray(run['internal']['node_values'])[:, 0]))
            row.update(reported_q=q, relative_error=abs(q-ref['q'])/ref['q'],
                       integration_component=(dense_q-ref['q'])/ref['q'],
                       sampling_component=(peak(run)['q']-dense_q)/ref['q'])
        sweep.append(row)
    studies, failures, selections = [], [], []
    for slot_index, (family, label) in enumerate(SLOTS):
        chosen = select_candidate(sweep, family, label)
        if chosen is None:
            failures.append({"cohort": cohort, "seed": seed, "family": family,
                             "label": label, "reason": "no eligible configuration"})
            continue
        identity = VERSION + ':' + digest(chosen['config'])[:16]
        study = make_study(seed, theta, identity, chosen['run'], ref,
                           (system_index+slot_index) % 3)
        study['private'].update(cohort=cohort, family=family, profile=f'{family}_{label}',
            category=f'{family}_{label}', selection_order=chosen['order'],
            integration_component=chosen['integration_component'],
            sampling_component=chosen['sampling_component'])
        validate_study(study)
        studies.append(study)
        selections.append({"case_id": study['case_id'], "slot": [family, label], "order": chosen['order']})
        log.write_json(f"private/studies/{study['case_id']}.json", study)
        log.write_json(f"public/{study['case_id']}.json", study['artifacts'])
    log.write_json(f"private/sweeps/{seed}.json", {"cohort": cohort, "seed": seed,
                   "sweep": sweep, "selections": selections, "failures": failures})
    log.event('system_commissioned', cohort=cohort, seed=seed,
              studies=len(studies), failures=failures)
    return studies, failures


def reachable(study, backend):
    rows = []
    for i in range(5):
        for s in range(7):
            cost = 3*i + 2*s
            if cost > 12:
                continue
            run, _ = backend.get(study['private']['theta'], refine_config(study['run']['config'], i, s))
            row = {"case_id": study['case_id'], "i": i, "s": s, "cost": cost, "status": run['status']}
            if run['status'] == 'success':
                row.update(q=peak(run)['q'], **check_diagnostic(study, peak(run)['q']))
            rows.append(row)
    return rows


def aggregate(studies, rows, failures, cells):
    ids = {s['case_id'] for s in studies}
    truth = {s['case_id']: s['private']['claim_valid'] for s in studies}
    result = {"studies": len(studies), "systems": len({s['private']['seed'] for s in studies}),
              "valid": sum(truth.values()), "invalid": sum(not t for t in truth.values()),
              "commissioning_failures": failures, "policies": {}, "reachability": {}}
    for policy in POLICIES:
        subset = [r for r in rows if r['policy'] == policy and r['case_id'] in ids]
        ev = [r['evaluation'] for r in subset]
        by_family = {}
        for family in ('integration', 'sampling', 'mixed'):
            group = [s['case_id'] for s in studies if s['private']['family'] == family]
            group_ev = [r['evaluation'] for r in subset if r['case_id'] in group]
            by_family[family] = {"studies":len(group), "correct":sum(e['correct'] for e in group_ev)}
        result['policies'][policy] = {
            "episodes": len(ev), "correct": sum(e['correct'] for e in ev),
            "false_accept": sum(e['false_accept'] for e in ev),
            "false_reject": sum(e['false_reject'] for e in ev),
            "abstained": sum(e['abstained'] for e in ev),
            "incomplete": sum(e['incomplete'] for e in ev),
            "credits": sum(e['spent'] for e in ev), "by_family": by_family,
            "actions": dict(Counter(''.join(r['diagnostics']['actions']) for r in subset if r['diagnostics'])),
            "last_run_correct": sum(
                (abs(r['evaluation']['reported_q']-r['diagnostics']['last_run_q'])/abs(r['diagnostics']['last_run_q']) <= .05)
                == truth[r['case_id']] for r in subset if r['diagnostics'] and not r['diagnostics']['failure'])}
    for budget in (8,10,12):
        pool = [c for c in cells if c['case_id'] in ids and c['cost']<=budget and c['status']=='success']
        result['reachability'][str(budget)] = {
            "margin_resolving": len({c['case_id'] for c in pool if c['margin_resolving']}),
            "within_one_percent": len({c['case_id'] for c in pool if c['within_one_percent']})}
    # Complementarity describes observed outcomes, NOT a deployable oracle.
    fixed = {p:{r['case_id']:r['evaluation']['correct'] for r in rows
                if r['policy']==p and r['case_id'] in ids} for p in ('fixed_IIS','fixed_ISS')}
    result['fixed_recipe_disagreement'] = {
        "IIS_only_correct": sum(fixed['fixed_IIS'].get(k,False) and not fixed['fixed_ISS'].get(k,False) for k in ids),
        "ISS_only_correct": sum(fixed['fixed_ISS'].get(k,False) and not fixed['fixed_IIS'].get(k,False) for k in ids)}
    result['one_sampling_direct_correct'] = sum(
        (c['direct_verdict']=='ACCEPT')==truth[c['case_id']]
        for c in cells if c['case_id'] in ids and c['i']==0 and c['s']==1 and c['status']=='success')
    return result


def metadata_features(study):
    config = study['run']['config']
    return [config['dt'], max(np.diff(config['output_times']))]


def metadata_control(development, fresh):
    """Small zero-purchase threshold control trained ONLY on development labels."""
    x = np.asarray([metadata_features(s) for s in development])
    y = np.asarray([s['private']['claim_valid'] for s in development])
    if not len(x):
        return {"status":"no development studies"}
    candidates = []
    # A stump, not a tuned general learner: one dt OR output-gap threshold.
    for axis in range(2):
        values = np.unique(x[:,axis])
        for threshold in values:
            left = x[:,axis] <= threshold
            labels = [bool(np.sum(y[mask]) >= np.sum(~y[mask])) if np.any(mask) else True
                      for mask in (left,~left)]
            prediction = np.where(left,labels[0],labels[1])
            candidates.append((int(np.sum(prediction==y)),axis,float(threshold),labels))
    best = max(candidates, key=lambda t:t[0])
    def score(studies):
        return sum(best[3][0 if metadata_features(s)[best[1]] <= best[2] else 1]
                   == s['private']['claim_valid'] for s in studies)
    return {"status":"fitted on development only", "feature":('dt','max_output_gap')[best[1]],
            "threshold":best[2], "left_accept":best[3][0], "right_accept":best[3][1],
            "development_correct":score(development), "fresh_correct":score(fresh),
            "development_n":len(development), "fresh_n":len(fresh)}


def render(path):
    path = Path(path)
    manifest = json.loads((path/'manifest.json').read_text(encoding='utf-8'))
    catalog = json.loads((path/'private/catalog.json').read_text(encoding='utf-8'))
    cells = json.loads((path/'private/reachable.json').read_text(encoding='utf-8'))
    rows = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((path/'episodes').glob('*/result.json'))]
    summary = {"version":manifest['version'], "api_calls":0, "cohorts":{}}
    for cohort in manifest['cohorts']:
        selected = [s for s in catalog['studies'] if s['private']['cohort']==cohort]
        failures = [f for f in catalog['failures'] if f['cohort']==cohort]
        summary['cohorts'][cohort] = aggregate(selected,rows,failures,cells)
    summary['metadata_control'] = json.loads((path/'metadata_control.json').read_text(encoding='utf-8'))
    lines = ['# Recalibrated incremental verification CPU pilot','',
             'Eight credits; 5% claim tolerance; extrapolation is the submitted estimator for every policy.',
             'No model/API calls. Fresh systems use the same frozen commissioning rules, without retuning.','',
             '| Cohort | Policy | Correct | False accept | False reject | Abstain | Incomplete | Credits |',
             '|---|---|---:|---:|---:|---:|---:|---:|']
    for cohort, group in summary['cohorts'].items():
        for policy,p in group['policies'].items():
            lines.append(f"| {cohort} | {policy} | {p['correct']}/{p['episodes']} | {p['false_accept']} | {p['false_reject']} | {p['abstained']} | {p['incomplete']} | {p['credits']:g} |")
    lines += ['', '## Per-study submitted results','',
              '| Cohort | Case | Profile | Policy | Verdict | Correct | Trace |','|---|---|---|---|---|---|---|']
    cohort_by_id = {s['case_id']:s['private']['cohort'] for s in catalog['studies']}
    for row in rows:
        prefix=f"episodes/{row['episode']:03d}"
        lines.append(f"| {cohort_by_id[row['case_id']]} | {row['case_id']} | {row['profile']} | {row['policy']} | {row['evaluation']['verdict']} | {row['evaluation']['correct']} | [Trace]({prefix}/transcript.md) |")
    lines += ['', 'Numerical severity and component requirements use private references only for case construction.',
              'No policy has reference access. Extrapolation is an approximation, not a certified error bound.',
              'See summary.json for class counts, commissioning failures, reachability and metadata-only controls.','']
    (path/'summary.json').write_text(json_text(summary)+'\n',encoding='utf-8')
    (path/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    events,_ = read_events(path)
    by_episode = {}
    for event in events:
        if event['kind']=='episode_event':
            by_episode.setdefault(event['episode'],[]).append(event)
    for row in rows:
        transcript = ['# CPU audit trace','',f"Policy: {row['policy']}; submitted estimator: extrapolation.",
                      f"Case: {row['case_id']}",'']
        for event in by_episode.get(row['episode'],[]):
            if event['event_kind'] in ('tool_call','tool_result','charged'):
                public = {k:v for k,v in event.items() if k not in ('utc','sequence','kind','episode')}
                transcript.extend(['```json',json_text(public),'```',''])
        (path/f"episodes/{row['episode']:03d}/transcript.md").write_text('\n'.join(transcript),encoding='utf-8')
    return summary


def run(root):
    log = RunLog(root,'recalibrated-cpu')
    manifest = {**protocol(), **source_provenance()}
    log.write_json('manifest.json',manifest)
    print(log.path,flush=True)
    studies, failures, cells, episode_index = [], [], [], 0
    try:
        for cohort,seeds in COHORTS.items():
            for system_index,seed in enumerate(seeds):
                backend=Backend()  # Bound memory; budgets remain episode-specific.
                selected,missing=commission_system(log,backend,cohort,seed,system_index)
                studies.extend(selected); failures.extend(missing)
                for study in selected:
                    for policy in POLICIES:
                        evaluate_policy(log,study,policy,episode_index,backend,estimator='extrapolation')
                        episode_index += 1
                    # Run reference-based endpoint diagnostics AFTER policies; never feed them back.
                    cells.extend(reachable(study,backend))
                print(f"{cohort} {seed}: {len(selected)}/{len(SLOTS)} studies, {len(missing)} missing",flush=True)
            log.event('cohort_completed',cohort=cohort)
        log.write_json('private/catalog.json',{'studies':studies,'failures':failures})
        log.write_json('private/reachable.json',cells)
        dev=[s for s in studies if s['private']['cohort']=='development']
        fresh=[s for s in studies if s['private']['cohort']=='fresh']
        log.write_json('metadata_control.json',metadata_control(dev,fresh))
        summary=render(log.path)
        log.event('pilot_finished',summary=summary)
        print(json_text(summary),flush=True)
    finally:
        log.close()
    return log.path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    command=sub.add_parser('run')
    command.add_argument('--output-root',type=Path,default=ROOT/'demos/claim_verification/runs')
    command=sub.add_parser('render'); command.add_argument('path',type=Path)
    args=parser.parse_args()
    if args.command=='run':
        run(args.output_root)
    else:
        print(json_text(render(args.path)))


if __name__=='__main__':
    main()
