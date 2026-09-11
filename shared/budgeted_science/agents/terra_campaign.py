"""Five Terra/high episodes extending, but never mutating, the completed campaign."""

import argparse
import asyncio
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

from . import campaign as c
from .campaign_reporting import NAMES, summarize, link
from .records import RunLog, digest, json_text, read_events
from .reporting import _write
from .resource import prompts as scientific_prompts
from .runner import provenance, run_episode
from .spending import pricing_for_model

MODEL = 'gpt-5.6-terra'
PARENT = c.REPO / 'demos/planning/runs/resource_five_case/20260911T144803Z-prepared-24ca583c0a'
OUTPUT = c.REPO / 'demos/planning/runs/resource_terra_five_case'
DISPLAY = {c.MODELS[0]: NAMES[c.MODELS[0]], MODEL: 'GPT-5.6 Terra (high)',
           **{m: n for m, n in NAMES.items() if m != c.MODELS[0]}}


def validate_parent(parent=PARENT):
    parent = Path(parent).resolve()
    manifest = c.read_json(parent / 'manifest.json')
    if manifest['rehearsal'] or digest(manifest) != c.read_json(parent / 'freeze.json')['manifest_hash']:
        raise ValueError('parent is not an intact live campaign')
    slots = c.state(parent)
    if ({(s['case_seed'], s['method']) for s in slots.values()} != {(s,m) for s in c.SEEDS for m in c.METHODS}
            or not all(s['status'] in ('imported', 'finished') for s in slots.values())):
        raise ValueError('parent campaign is not complete or has different cases')
    current = provenance(c.REPO)
    for name, checksum in manifest['source_hashes'].items():
        if name.startswith('shared/budgeted_science/resource_planning/') and current['source_hashes'].get(name) != checksum:
            raise ValueError('scientific implementation changed: ' + name)
    if manifest['dependencies'] != current['dependencies']:
        raise ValueError('dependencies changed since parent campaign')
    for model, entry in manifest['imports'].items():
        if c.tree_hashes(entry['path']) != entry['hashes']:
            raise ValueError('parent imported artifacts changed')
        c.validate_anchor(entry['path'], model)
    rows = []
    for slot in slots.values():
        row = deepcopy(slot['result'])
        c.validate_scoring(row['evaluation'], c.ResourceInstance.from_seed(row['case_seed']))
        if row['scientific_status']['spent'] != 32:
            raise ValueError('parent budget mismatch')
        if row['method'] in c.MODELS:
            original = c.agent_row(row['case_seed'], row['method'], row['path'])
            original['imported'] = row['imported']
            if original != row:
                raise ValueError('parent model result changed')
        row['imported'] = True
        rows.append(row)
    comparisons = {str(seed): c.comparison_snapshots(parent, seed) for seed in c.SEEDS}
    prompts = {str(seed): c.read_json(Path(next(r['path'] for r in rows if r['case_seed']==seed and r['method']==c.MODELS[0])) / 'prompts.json')
               for seed in c.SEEDS}
    references = {'campaign': {'path': str(parent), 'hashes': c.tree_hashes(parent)},
                  **manifest['imports']}
    return rows, comparisons, prompts, references


def prepare(output=OUTPUT, *, rehearsal=False):
    rows, comparisons, prompts, references = validate_parent()
    config = c.configuration(MODEL)
    manifest = {'kind': 'terra_five_case_extension', 'rehearsal': rehearsal,
                'model': MODEL, 'seeds': list(c.SEEDS), 'config': config.public(),
                'episode_api_ceiling_usd': '3.00', 'new_api_ceiling_usd': '15.00',
                'pricing': pricing_for_model(MODEL), 'parent_references': references,
                'parent_rows': rows, 'comparisons': comparisons, 'expected_prompts': prompts,
                'slots': [{'id': c.slot_id(s, MODEL), 'case_seed': s, 'method': MODEL} for s in c.SEEDS],
                **provenance(c.REPO)}
    log = RunLog(output, 'rehearsal' if rehearsal else 'prepared')
    try:
        log.write_json('manifest.json', manifest)
        log.write_json('freeze.json', {'manifest_hash': digest(manifest)})
        c.durable_event(log, 'prepared', manifest_hash=digest(manifest))
    finally:
        log.close()
    render(log.path)
    return log.path


def verify(root):
    root = Path(root).resolve()
    manifest = c.read_json(root / 'manifest.json')
    if digest(manifest) != c.read_json(root / 'freeze.json')['manifest_hash']:
        raise ValueError('Terra manifest changed')
    current = provenance(c.REPO)
    if any(manifest[k] != current[k] for k in ('dependencies','source_hashes')):
        raise ValueError('Terra code/dependencies changed since freeze')
    if manifest['config'] != c.configuration(MODEL).public() or manifest['pricing'] != pricing_for_model(MODEL):
        raise ValueError('Terra configuration/pricing changed')
    if manifest['seeds'] != list(c.SEEDS) or len(manifest['slots']) != 5:
        raise ValueError('Terra case count changed')
    for reference in manifest['parent_references'].values():
        if c.tree_hashes(reference['path']) != reference['hashes']:
            raise ValueError('prior results changed; refusing to continue')
    return manifest


class TerraAdapter(c.CampaignAdapter):
    def __init__(self, instance, comparisons, expected_prompt):
        super().__init__(instance, comparisons)
        self.expected_prompt = expected_prompt

    def prompts(self, config, episode):
        result = scientific_prompts(config, episode)
        if result != self.expected_prompt:
            raise ValueError('Terra scientific prompt differs from previous paired model prompt')
        return result


def spending(slots):
    return sum((Decimal(3) if s['status']=='started' else
                Decimal(s['result']['api_budget']['committed_upper_usd']) if s['status']=='finished' else Decimal(0)
                for s in slots.values()), Decimal(0))


def recover(log):
    for slot in c.state(log.path).values():
        if slot['status'] != 'started':
            continue
        directory = Path(slot['output_root'])
        children = [p for p in directory.iterdir() if p.is_dir()] if directory.exists() else []
        if len(children) != 1:
            raise ValueError('ambiguous launched Terra slot; inspect without restarting')
        path, seen = children[0], set()
        while (path / 'resume_claim.json').exists():
            if str(path) in seen:
                raise ValueError('resume cycle')
            seen.add(str(path))
            path = Path(c.read_json(path / 'resume_claim.json')['child']).resolve()
        row = c.agent_row(slot['case_seed'], MODEL, path)
        c.durable_event(log, 'slot_finished', slot_id=slot['id'], result=row, recovered=True)
        if c.fatal_agent_error(path):
            c.durable_event(log, 'campaign_halted', reason='recovered systemic failure')
            raise ValueError('systemic failure requires inspection')


async def execute(root, *, mode, continuation=False, gateway_factory=None, key_file=None):
    root = Path(root).resolve()
    manifest = verify(root)
    if mode not in ('live','dry-run') or (mode=='dry-run') != manifest['rehearsal']:
        raise ValueError('Terra rehearsal/live mismatch')
    if mode=='live' and gateway_factory is not None:
        raise ValueError('no substitute gateway in live mode')
    with c.journal(root) as log:
        events = read_events(root)[0]
        if any(e['kind']=='campaign_halted' for e in events):
            raise ValueError('halted Terra campaign requires inspection')
        if not continuation and any(e['kind']=='slot_started' for e in events):
            raise ValueError('already attempted; use explicit continue')
        recover(log)
        for seed in c.SEEDS:
            slots = c.state(root)
            identifier = c.slot_id(seed, MODEL)
            if slots[identifier]['status'] != 'pending':
                continue
            verify(root)
            if spending(slots) + 3 > 15:
                raise ValueError('Terra campaign ceiling reached')
            instance = c.ResourceInstance.from_seed(seed)
            adapter = TerraAdapter(instance, manifest['comparisons'][str(seed)], manifest['expected_prompts'][str(seed)])
            output = root / 'episodes' / identifier
            c.durable_event(log, 'slot_started', slot_id=identifier, output_root=str(output), reserved_usd='3.00')
            print(f'Starting {mode} Terra case {seed}', flush=True)
            try:
                path, reason = await run_episode(c.REPO, output, mode=mode, config=c.configuration(MODEL), instance=instance,
                    adapter=adapter, gateway=gateway_factory(seed) if gateway_factory else None, key_file=key_file)
                row = c.agent_row(seed, MODEL, path)
                c.durable_event(log, 'slot_finished', slot_id=identifier, result=row)
                render(root)
                print(f'Finished {seed}: {reason}; success={row["evaluation"].get("success",False)}; '
                      f'API upper=${row["api_budget"]["committed_upper_usd"]}', flush=True)
                if c.fatal_agent_error(path):
                    raise ValueError('systemic API/accounting failure')
            except Exception as exc:
                c.durable_event(log, 'campaign_halted', reason=log.redactor.error(exc))
                render(root)
                raise
        verify(root)
        c.durable_event(log, 'campaign_finished', new_api_upper_usd=str(spending(c.state(root))))
    return render(root)


def render(root):
    root = Path(root).resolve()
    manifest = c.read_json(root / 'manifest.json')
    terra = c.state(root)
    combined = {c.slot_id(r['case_seed'],r['method']): {'method':r['method'],'case_seed':r['case_seed'],
                'status':'imported','result':r} for r in manifest['parent_rows']}
    combined.update(terra)
    summary = {'complete':all(s['status']=='finished' for s in terra.values()), 'rehearsal':manifest['rehearsal'],
               'all_five':summarize(combined,names=DISPLAY), 'four_nonanchor_cases':summarize(combined,True,names=DISPLAY),
               'new_api_upper_usd':str(spending(terra)), 'new_api_ceiling_usd':'15.00',
               'rows':[s['result'] for s in combined.values() if 'result' in s]}
    _write(root / 'summary.json', json_text(summary)+'\n')
    lines=['# Terra/high extension: matched five-case comparison','',f'Complete: {summary["complete"]}.', '',
           'Terra uses the same five cases, noise, tools, prompts, 32 credits, and 5% tolerance as the completed Sol/Luna campaign. '
           'The 30 prior model/baseline results are imported unchanged, not rerun. All Terra investigations start fresh.','']
    if manifest['rehearsal']:
        lines += ['**OFFLINE REHEARSAL: Terra rows are scripted fixtures; actual new API spending is zero.**','']
    for title,key in (('All five cases','all_five'),('Four non-anchor cases (6020-6023)','four_nonanchor_cases')):
        lines += ['## '+title,'','| Method | Passes / attempts | Incomplete | Median largest error |', '|---|---:|---:|---:|']
        for g in summary[key]:
            error='n/a' if g['median_max_relative_error_percent'] is None else f'{g["median_max_relative_error_percent"]:.4f}%'
            lines.append(f'| {g["name"]} | {g["successes"]}/{g["attempted"]} | {g["incomplete"]} | {error} |')
        lines += ['']
    lines += ['## Terra episodes','','| Case | Outcome | Largest error | Low/high/measurement | Credits | Seconds | API upper | Transcript |',
              '|---|---|---:|---|---:|---:|---:|---|']
    for slot in terra.values():
        if 'result' not in slot: continue
        r=slot['result']; ev=r['evaluation']; scientific=r['scientific_status']
        valid=ev.get('valid') and r['termination_reason']=='submitted'
        outcome=('Pass' if ev['success'] else 'Fail') if valid else r['termination_reason']
        error=f'{ev["parameter_error"]*5:.4f}%' if valid else 'n/a'
        counts=[sum(e['kind']==k for e in scientific['ledger']) for k in ('simulate_low','simulate_high','measure_target')]
        lines.append(f'| {r["case_seed"]} | {outcome} | {error} | {"/".join(map(str,counts))} | {scientific["spent"]:g} | '
                     f'{r["elapsed_seconds"]:.3f} | {r["api_budget"]["committed_upper_usd"]} | {link(root,r)} |')
    lines += ['',f'New Terra API cost/reservation upper bound: ${summary["new_api_upper_usd"]}; maximum $15 ($3 per episode). '
              'Historical model costs are excluded. Upper bounds are not invoices.','',
              'Incomplete attempts count as nonsuccesses; error summaries include valid submissions only. '
              'All-five results include the previously explored anchor 6000. Terra was added after reviewing other models; '
              'these are matched case comparisons, not a new held-out sample or general model ranking. '
              'Allocation and fitting differences do not establish causal explanations. Raw internal reasoning is not exposed; '
              'available summaries, opaque replay items, requests, responses, and tool records are preserved.','']
    _write(root / 'report.md','\n'.join(lines))
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('prepare','dry-run','live','continue','render'))
    parser.add_argument('run_dir',nargs='?',type=Path)
    parser.add_argument('--output-root',type=Path,default=OUTPUT)
    parser.add_argument('--api-key-file',type=Path)
    args=parser.parse_args()
    if args.api_key_file and args.operation not in ('live','continue'):
        parser.error('credential path is accepted only for live execution')
    if args.operation in ('prepare','dry-run'):
        if args.run_dir: parser.error('prepare and dry-run create new campaigns')
        root=prepare(args.output_root,rehearsal=args.operation=='dry-run')
        print(f'Campaign: {root}',flush=True)
        if args.operation=='dry-run': asyncio.run(execute(root,mode='dry-run'))
    else:
        if not args.run_dir: parser.error('campaign directory required')
        root=args.run_dir
        if args.operation=='render': render(root)
        else:
            mode='dry-run' if c.read_json(root/'manifest.json')['rehearsal'] else 'live'
            if args.operation=='live' and mode!='live': parser.error('cannot execute rehearsal as live')
            asyncio.run(execute(root,mode=mode,continuation=args.operation=='continue',key_file=args.api_key_file))
    print(f'Report: {root / "report.md"}',flush=True)


if __name__=='__main__':
    main()
