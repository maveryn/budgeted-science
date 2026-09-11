"""Campaign summaries exclusively from saved slot records."""

from decimal import Decimal
import json
from pathlib import Path

import numpy as np

from .records import json_text
from .reporting import _write

NAMES = {'gpt-5.6-sol': 'GPT-5.6 Sol (high)', 'gpt-5.6-luna': 'GPT-5.6 Luna (high)',
         'local': 'Local fitting', 'random_local': 'Random acquisition + local fit',
         'random': 'Random acquisition + GP', 'adaptive': 'Adaptive GP'}


def summarize(slots, new_only=False, *, names=None):
    groups = []
    for method, name in (NAMES if names is None else names).items():
        selected = [s for s in slots.values() if s['method'] == method and (not new_only or s['case_seed'] != 6000)]
        rows = [s['result'] for s in selected if 'result' in s]
        valid = [r for r in rows if r['evaluation'].get('valid') and r['termination_reason'] == 'submitted']
        errors = [r['evaluation']['parameter_error'] * 5 for r in valid]
        attempted = sum(s['status'] != 'pending' for s in selected)
        groups.append({'method': method, 'name': name, 'planned': len(selected), 'attempted': attempted,
                       'pending': len(selected) - attempted, 'valid_submissions': len(valid),
                       'incomplete': attempted - len(valid),
                       'successes': sum(bool(r['evaluation']['success']) for r in valid),
                       'median_max_relative_error_percent': float(np.median(errors)) if errors else None,
                       'mean_max_relative_error_percent': float(np.mean(errors)) if errors else None})
    return groups


def link(root, row):
    path = Path(row['path'])
    target = path if path.is_file() else path / ('transcript.md' if row['api_budget'] else 'events.jsonl')
    try:
        url = target.relative_to(root).as_posix()
    except ValueError:
        url = target.as_posix()
    return f'[logs]({url})'


def render_campaign(root, slots):
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    rows = [s['result'] for s in slots.values() if 'result' in s]
    imported_cost = sum((Decimal(r['api_budget']['committed_upper_usd']) for r in rows if r['imported'] and r['api_budget']), Decimal(0))
    new_cost = sum((Decimal(r['api_budget']['committed_upper_usd']) for r in rows if not r['imported'] and r['api_budget']), Decimal(0))
    orphan_reservation = sum(Decimal(3) for s in slots.values() if s['status'] == 'started' and s['method'].startswith('gpt-'))
    summary = {'rehearsal': manifest['rehearsal'], 'complete': all(s['status'] in ('imported', 'finished') for s in slots.values()),
               'all_five': summarize(slots), 'new_four': summarize(slots, True),
               'new_api_committed_upper_usd': str(new_cost + orphan_reservation),
               'unreconciled_slot_reservation_usd': str(orphan_reservation),
               'historical_imported_api_upper_usd': str(imported_cost),
               'new_spending_ceiling_usd': '24.00', 'rows': rows, 'slots': list(slots.values())}
    _write(root / 'summary.json', json_text(summary) + '\n')
    lines = ['# Five-case matched resource-planning evaluation', '',
             f'Complete: {summary["complete"]}. Scientific budget: 32 per method and case; tolerance: 5%.', '',
             'One previously explored case is imported unchanged; four new cases use preselected parameters and paired noise.',
             'Methods start independently. Prices, tools, full-budget requirement, and scientific prompt template are unchanged.', '']
    if manifest['rehearsal']:
        lines += ['**OFFLINE REHEARSAL: new agent rows are scripted fakes on development targets; no new API spending.**', '']
    for label, key in (('All five cases (including exploratory case)', 'all_five'), ('Four newly selected cases only', 'new_four')):
        lines += ['## ' + label, '', '| Method | Successes / attempts | Valid | Incomplete | Pending | Median largest error |',
                  '|---|---:|---:|---:|---:|---:|']
        for group in summary[key]:
            value = group['median_max_relative_error_percent']
            error = 'n/a' if value is None else f'{value:.4f}%'
            lines.append(f'| {group["name"]} | {group["successes"]}/{group["attempted"]} | {group["valid_submissions"]} | '
                         f'{group["incomplete"]} | {group["pending"]} | {error} |')
        lines += ['']
    lines += ['## Individual paired results', '',
              '| Case | Method | Status | Largest error | E_worst | Low/high/measurement | Credits | Seconds | API upper | Records |',
              '|---|---|---|---:|---:|---|---:|---:|---:|---|']
    for row in rows:
        ev, status = row['evaluation'], row['scientific_status']
        valid = ev.get('valid') and row['termination_reason'] == 'submitted'
        error, worst = (f'{ev["parameter_error"] * 5:.4f}%', f'{ev["parameter_error"]:.6f}') if valid else ('n/a', 'n/a')
        outcome = ('Pass' if ev['success'] else 'Fail') if valid else row['termination_reason']
        counts = [sum(e['kind'] == kind for e in status.get('ledger', [])) for kind in ('simulate_low', 'simulate_high', 'measure_target')]
        cost = row['api_budget']['committed_upper_usd'] if row['api_budget'] else '-'
        cohort = ' (exploratory)' if row['case_seed'] == 6000 else ''
        lines.append(f'| {row["case_seed"]}{cohort} | {NAMES[row["method"]]} | {outcome} | {error} | {worst} | '
                     f'{"/".join(map(str, counts))} | {status.get("spent", 0):g} | {row["elapsed_seconds"]:.3f} | {cost} | {link(root, row)} |')
    lines += ['', '## Accounting and interpretation', '',
              f'New API cost/reservation upper bound: ${new_cost + orphan_reservation}; maximum authorized: $24. '
              f'Historical imported upper bound ${imported_cost} is separate. Bounds are not invoices.', '',
              'Incomplete attempted episodes count as nonsuccesses; numerical-error summaries use valid submissions only. '
              'Pending slots are not attempts. The two GP methods are supplementary controls.', '',
              'Five physical targets do not establish general superiority. There is one rollout per model per case, '
              'not a measure of repeated-rollout consistency. The existing case influenced budget exploration.', '',
              'The random-local and random-GP policies share purchases but use different estimators. '
              'Local-policy versus random-local differences also involve acquisition locations and fitting trajectories; '
              'they do not isolate resource allocation as a causal mechanism. No early-stopping benefit is tested.', '',
              'The older 40-credit pilot is not pooled here. CPU and agent runtimes have different limits and are descriptive. '
              'Raw private records are local and ignored by Git. Offline regeneration performs no tool or API calls.', '']
    _write(root / 'report.md', '\n'.join(lines))
    return summary
