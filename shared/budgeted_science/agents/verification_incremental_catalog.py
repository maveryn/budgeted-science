"""Logged Luna/high evaluation on the 35 frozen fresh recalibrated studies."""
import argparse
import asyncio
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from ..claim_verification.studies import validate_study
from .records import RunLog, digest, json_text
from .runner import provenance, run_episode
from .spending import pricing_for_model
from .verification_catalog import result_row, summarize, must_halt
from .verification_incremental import (IncrementalConfig, IncrementalInstance, IncrementalAdapter,
                                      tool_definitions, prepare_resume)
from .verification_reporting import regenerate

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT/'demos/claim_verification/runs/20260912T021845Z-recalibrated-cpu-1f6f2893c3'


def read_catalog(path):
    path=Path(path).resolve()
    manifest=json.loads((path/'manifest.json').read_text(encoding='utf-8'))
    catalog=json.loads((path/'private/catalog.json').read_text(encoding='utf-8'))
    if manifest['version'] != 'claim-verification-recalibrated-v1' or manifest['budget'] != 8:
        raise ValueError('expected frozen eight-credit recalibrated catalog')
    for relative, expected in manifest['source_hashes'].items():
        if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest() != expected:
            raise ValueError('scientific implementation changed since CPU comparison: '+relative)
    studies=[validate_study(deepcopy(s)) for s in catalog['studies'] if s['private']['cohort']=='fresh']
    if len(studies)!=35 or len({s['case_id'] for s in studies})!=35:
        raise ValueError('expected exactly 35 unique generated fresh studies')
    files=[path/'manifest.json', path/'private/catalog.json']
    comparisons={s['case_id']:{} for s in studies}
    for file in sorted((path/'episodes').glob('*/result.json')):
        row=json.loads(file.read_text(encoding='utf-8'))
        if row['case_id'] not in comparisons:
            continue
        study=next(s for s in studies if s['case_id']==row['case_id'])
        e=row['evaluation']
        if (e['reported_q']!=study['reported_q'] or e['claim_valid']!=study['private']['claim_valid']
                or e['reference_q']!=study['private']['reference_q'] or not e['valid_submission']
                or e['verdict']!=row['diagnostics']['extrapolated_verdict'] or not 0<=e['spent']<=8):
            raise ValueError('saved CPU comparison mismatch')
        if row['policy'] in comparisons[row['case_id']]:
            raise ValueError('duplicate CPU comparison')
        comparisons[row['case_id']][row['policy']]=row
        files.append(file)
    expected={'fixed_IIS','fixed_ISS','random','adaptive_change'}
    if any(set(v)!=expected for v in comparisons.values()):
        raise ValueError('incomplete saved CPU comparison')
    hashes={f.relative_to(path).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    return studies, comparisons, {'path':str(path),'file_hashes':hashes,
        'catalog_digest':digest(catalog),'omitted_slots':catalog['failures'],
        'cpu_source_manifest_hash':manifest['source_manifest_hash']}


def render(path):
    path=Path(path)
    manifest=json.loads((path/'manifest.json').read_text(encoding='utf-8'))
    rows=[json.loads(f.read_text(encoding='utf-8')) for f in sorted((path/'results').glob('*.json'))]
    comparisons=json.loads((path/'cpu-comparisons.json').read_text(encoding='utf-8'))
    summary={'mode':manifest['mode'],'planned_cases':len(manifest['cases']),'overall':summarize(rows),
             'category':{},'cpu_comparisons':{},'omitted_slots':manifest['source_catalog']['omitted_slots']}
    for category in sorted({r['category'] for r in rows}):
        summary['category'][category]=summarize([r for r in rows if r['category']==category])
    for policy in ('fixed_IIS','fixed_ISS','random','adaptive_change'):
        evaluations=[v[policy]['evaluation'] for v in comparisons.values()]
        summary['cpu_comparisons'][policy]={'correct':sum(e['correct'] for e in evaluations),
            'cases':len(evaluations),'credits':sum(e['spent'] for e in evaluations)}
    total=summary['overall']
    lines=['# Luna: recalibrated incremental claim verification','',
        f"Mode: {manifest['mode']}; gpt-5.6-luna; high reasoning; eight audit credits per independent episode.",
        f"Attempts: {len(rows)}/{len(manifest['cases'])}; correct: {total['correct']}/{len(rows)}.",
        'Six fresh systems, 35 generated studies. One additional requested mixed-invalid study could not be generated.',
        'All attempts count; abstention is completed but not a correct binary verdict. No retries, savings bonus or full-budget requirement.','']
    if manifest['mode']=='dry-run':
        lines += ['Scripted fake responses; NOT model performance. Actual API expenditure is zero; ledger usage is synthetic.','']
    lines += ['## Aggregate','','```json',json_text(total),'```','',
        '## Matched saved CPU comparisons','','| Policy | Correct | Credits |','|---|---:|---:|']
    for policy,c in summary['cpu_comparisons'].items():
        lines.append(f"| {policy} | {c['correct']}/{c['cases']} | {c['credits']:g} |")
    lines += ['', '## Episodes','','| Case | Category | Verdict | Correct | Credits | Transcript |','|---|---|---|---|---:|---|']
    for r in rows:
        lines.append(f"| {r['case_id']} | {r['category']} | {r['verdict']} | {r['correct']} | {r['spent']:g} | [Read]({r['run']}/transcript.md) |")
    lines += ['', 'The CPU methods use their implemented extrapolation procedure. Luna has the same primitive audit tools',
              'but no Python execution or automatic extrapolation helper; it may reason over purchased results.',
              'No private references, labels, commissioning rules or baseline outcomes enter the model context.',
              'Costs are conservative bounds, not an invoice. Raw internal reasoning is unavailable;',
              'API-visible summaries and opaque encrypted reasoning items are preserved.','']
    (path/'summary.json').write_text(json_text(summary)+'\n',encoding='utf-8')
    (path/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    return summary


async def run_catalog(catalog_path, output_root, *, mode, gateway_factory=None):
    if mode not in ('dry-run','live') or (mode=='live' and gateway_factory is not None):
        raise ValueError('invalid mode or live gateway override')
    studies, comparisons, source=read_catalog(catalog_path)
    config=IncrementalConfig()
    log=RunLog(output_root,'luna-incremental-'+mode)
    frozen=provenance(ROOT)
    cases=[{'case_id':s['case_id'],'study_hash':digest(s),'system_seed':s['private']['seed'],
            'category':s['private']['category'],'format':s['format']} for s in studies]
    ceiling=Decimal(config.api_ceiling_usd)*len(studies)
    log.write_json('manifest.json',{'mode':mode,'config':config.public(),'cases':cases,
        'source_catalog':source,'max_live_slots':len(studies),'api_maximum_usd':str(ceiling),
        'pricing':pricing_for_model(config.model),'pricing_reverified':'2026-09-12',
        'pricing_source':'https://developers.openai.com/api/docs/models/gpt-5.6-luna',
        'tool_schema_hash':digest(tool_definitions(config)),
        'order':'existing fresh-cohort catalog order','automatic_retries':False,**frozen})
    log.write_json('cpu-comparisons.json',comparisons)
    print(log.path,flush=True)
    log.event('campaign_started',cases=len(studies),mode=mode)
    try:
        for index,study in enumerate(studies):
            current=provenance(ROOT)
            if current['source_hashes']!=frozen['source_hashes'] or current['dependencies']!=frozen['dependencies']:
                raise ValueError('implementation changed during frozen campaign')
            if digest(study)!=cases[index]['study_hash']:
                raise ValueError('frozen study changed')
            log.write_json(f'slots/{index:02d}.json',{'case_id':study['case_id'],'status':'attempted',
                            'api_ceiling_usd':config.api_ceiling_usd})
            log.event('case_started',index=index,case_id=study['case_id'])
            instance=IncrementalInstance(study,source['path'],source['catalog_digest'],
                'all generated fresh-cohort studies in frozen order',comparisons[study['case_id']]['fixed_IIS'])
            path,reason=await run_episode(ROOT,output_root,mode=mode,config=config,instance=instance,
                adapter=IncrementalAdapter(),gateway=gateway_factory(index) if gateway_factory else None)
            result=json.loads((path/'evaluation.json').read_text(encoding='utf-8'))
            row=result_row(study,path,log.path,result)
            if Decimal(row['api_upper_usd'])>Decimal(config.api_ceiling_usd):
                raise ValueError('episode spending exceeded ceiling')
            log.write_json(f'results/{index:02d}.json',row)
            log.event('case_finished',index=index,case_id=study['case_id'],result=row)
            summary=render(log.path)
            if Decimal(summary['overall']['api_committed_upper_usd'])>ceiling:
                raise ValueError('campaign spending exceeded ceiling')
            print(f"{index+1}/{len(studies)} {study['case_id']}: {reason}; verdict={row['verdict']}; "
                  f"correct={row['correct']}; credits={row['spent']:g}; API upper={row['api_upper_usd']}",flush=True)
            if must_halt(path,reason):
                log.event('campaign_halted',reason=reason,case_id=study['case_id'])
                break
        else:
            log.event('campaign_finished',cases=len(studies))
    finally:
        render(log.path)
        log.close()
    return log.path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--dry-run',action='store_true')
    modes.add_argument('--live',action='store_true')
    modes.add_argument('--render',type=Path)
    parser.add_argument('--resume',type=Path,help='Explicit continuation of ONE finalized unsubmitted episode')
    parser.add_argument('--catalog',type=Path)
    parser.add_argument('--output-root',type=Path,default=ROOT/'demos/claim_verification/runs')
    args=parser.parse_args()
    if args.render:
        if args.resume or args.catalog:
            parser.error('render does not accept instance overrides')
        if (args.render/'cpu-comparisons.json').exists():
            print(json_text(render(args.render)))
        else:
            print(regenerate(args.render))
        return
    mode='live' if args.live else 'dry-run'
    if args.resume:
        if args.catalog:
            parser.error('resume restores its original study; no catalog override')
        saved=prepare_resume(args.resume,mode)
        print(asyncio.run(run_episode(ROOT,args.output_root,mode=mode,config=saved['config'],
            instance=saved['instance'],adapter=IncrementalAdapter(),resume=saved)))
    else:
        asyncio.run(run_catalog(args.catalog or CATALOG,args.output_root,mode=mode))


if __name__=='__main__':
    main()
