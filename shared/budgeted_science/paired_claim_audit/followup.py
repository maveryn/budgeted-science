"""CPU-only follow-up pilot: prepare, run, or regenerate saved reports."""
import argparse
from collections import defaultdict
from pathlib import Path
import time

from . import pilot as original
from .followup_core import VERSION,SPECS,Session,build_catalog
from .followup_policies import METHODS,run_policy
from ..agents.records import RunLog,digest,json_text,read_events


def prepare(root=original.RUNS):
    log=RunLog(root,'followup-prepared')
    try:
        catalog=build_catalog()
        log.write_json('catalog.json',catalog)
        log.write_json('manifest.json',{'version':VERSION,'catalog_hash':digest(catalog),
            'methods':list(METHODS),'budget':32,'specs':SPECS,
            'mode':'CPU commissioning; same six development worlds; no agents',
            'utility':{'correct':1,'wrong':-2,'abstain':0},**original.provenance()})
        log.event('prepared',case_count=6,method_count=len(METHODS),api_spending=0)
    finally:
        log.close()
    return log.path


def run_case(case,method,root):
    log=RunLog(root,'cpu-followup')
    started=time.monotonic()
    try:
        log.write_json('private/study.json',case['study'])
        session=Session(case['study'],32,log)
        public=session.environment.public
        log.write_json('public/input.json',session.environment.evidence())
        log.write_json('manifest.json',{'version':VERSION,'case_id':case['case_id'],
                                      'method':method,'budget':32,'api_spending':0})
        reason='submitted'
        try:
            run_policy(method,public,session.call,lambda kind,**data:log.event(kind,**data))
            if session.environment.submission is None: reason='no_submission'
        except Exception as exc:
            reason='incomplete'
            log.event('interruption',error=log.redactor.error(exc))
        events,_=read_events(log.path)
        purchases=[{'name':e['name'],'theta':e['result'].get('theta'),
                    'variable':e['result'].get('variable'),'time':e['result'].get('time'),
                    'charge':e['result']['charge']}
                   for e in events if e['kind']=='tool_result' and e['result'].get('charge',0)>0]
        result={**session.environment.evaluate(),'method':method,'case_id':case['case_id'],
            'pair':case['study']['private']['pair_index'],'member':case['study']['private']['member'],
            'budget':32,'termination':reason,'path':str(log.path),'api_spending':0,'purchases':purchases,
            'runtime_seconds':time.monotonic()-started,'tool_requests':session.calls}
        log.write_json('evaluation.json',result)
        log.event('finished',result=result)
    finally:
        log.close()
    original.render_case(log.path)
    return result


def total(rows):
    return {k:sum(r[k] for r in rows) for k in ('correct','wrong','abstained','utility')}


def commissioning(results):
    by_method=defaultdict(list)
    for r in results: by_method[r['method']].append(r)
    complete=set(by_method)==set(METHODS) and all(len(v)==6 for v in by_method.values())
    if not complete: return {'complete':False,'note':'partial pilot; no comparison gate'}
    fixed={k:v for k,v in by_method.items() if k.startswith('fixed:') or k=='corrected_x4_intervention'}
    key=lambda rows:(total(rows)['utility'],total(rows)['correct'],-total(rows)['wrong'],
                     -sum(r['scientific_status']['spent'] for r in rows))
    best=max(fixed,key=lambda k:key(fixed[k]))
    per_pair=[]
    branch=[]
    for pair in range(3):
        select=lambda rs:[r for r in rs if r['pair']==pair]
        best_pair=max(fixed,key=lambda k:key(select(fixed[k])))
        per_pair.append({'pair':pair,'method':best_pair,**total(select(fixed[best_pair]))})
        for r in select(by_method['adaptive_followup']):
            purchases=r['purchases']
            branch.append({'pair':pair,'member':r['member'],'after_measurement':purchases[3:],
                           **total([r]),'path':r['path']})
    adaptive=total(by_method['adaptive_followup'])
    switches=all(len([r for r in branch if r['pair']==i])==2 and
                 [r for r in branch if r['pair']==i][0]['after_measurement']!=
                 [r for r in branch if r['pair']==i][1]['after_measurement'] for i in range(3))
    pair_upper=sum(r['utility'] for r in per_pair)
    return {'complete':True,'best_fixed':{'method':best,**total(fixed[best])},
            'best_fixed_per_pair':per_pair,'adaptive_followup':adaptive,
            'adaptive_full':total(by_method['adaptive_full']),
            'followup_choices':branch,'switches_in_all_pairs':switches,
            'utility_gain_over_best_global_fixed':adaptive['utility']-total(fixed[best])['utility'],
            'utility_gain_over_hindsight_pair_specific_fixed':adaptive['utility']-pair_upper,
            'all_episodes_completed':all(r['completed'] for r in results),
            'interpretation':'Fixed winners selected in hindsight; restricted two-fit estimator/menu; not optimal policies or held-out evidence.'}


def run(prepared,root=original.RUNS):
    prepared=Path(prepared).resolve()
    frozen=original.read(prepared/'manifest.json'); catalog=original.read(prepared/'catalog.json')
    if (frozen['version']!=VERSION or frozen['catalog_hash']!=digest(catalog)
        or frozen['methods']!=list(METHODS) or frozen['budget']!=32
        or frozen['source_manifest_hash']!=original.provenance()['source_manifest_hash']):
        raise ValueError('frozen implementation, configuration, or catalog mismatch')
    log=RunLog(root,'followup-pilot')
    results=[]
    try:
        log.write_json('manifest.json',{**frozen,'prepared':str(prepared)})
        log.write_json('catalog.json',catalog)
        for case in catalog['cases']:
            for method in frozen['methods']:
                r=run_case(case,method,log.path/'episodes')
                results.append(r)
                log.event('episode_finished',case_id=case['case_id'],method=method,
                          correct=r['correct'],wrong=r['wrong'],abstained=r['abstained'],path=r['path'])
            log.write_json(f'checkpoints/completed-{len(results):04d}.json',results)
            print(f"Finished {case['case_id']}: {len(results)} CPU policy evaluations",flush=True)
    finally:
        log.write_json('results.json',results)
        log.close()
    render(log.path)
    return log.path


def render(path):
    path=Path(path).resolve()
    results=original.read(path/'results.json')
    summary=original.summarize(results)
    gates=commissioning(results)
    (path/'summary.json').write_text(json_text(summary)+'\n',encoding='utf-8')
    (path/'commissioning.json').write_text(json_text(gates)+'\n',encoding='utf-8')
    lines=['# Evidence-conditioned follow-up: CPU pilot','','Same six development worlds; 32 credits; 1/8/12 prices; no agents.',
           '','## Commissioning comparisons','','```json',json_text(gates),'```','',
           '## Every tested policy','','| Method | Correct | Wrong | Abstain | Utility | Mean credits | Incomplete |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for r in summary:
        lines.append(f"| {r['method']} | {r['correct']} | {r['wrong']} | {r['abstained']} | {r['utility']} | {r['mean_spent']:.2f} | {r['incomplete_episodes']} |")
    lines+=['','## Per-study results and traces','','| Case | Method | Correct | Wrong | Abstain | Credits | Transcript |',
            '|---|---|---:|---:|---:|---:|---|']
    for r in results:
        relative=Path(r['path']).relative_to(path).as_posix()
        lines.append(f"| {r['case_id']} | {r['method']} | {r['correct']} | {r['wrong']} | {r['abstained']} | {r['scientific_status']['spent']} | [trace]({relative}/transcript.md) |")
    lines+=['','All policies have independent ledgers. The acquisition policies share paid 9-credit initialization and '
             'the same two-fit estimator. Low-model uncertainty remains a heuristic; correct labels do not certify reasoning. '
             'Thresholds were chosen after inspecting the existing coarse/fine quantities. The fixed-policy search is an '
             'optimistic development comparison, not a learned baseline tested on unseen data. It covers the stated '
             'one-measurement and two named high-follow-up menu, not arbitrary code or all continuous parameter queries. '
             'Hypothetical outcomes and the cheap correction use purchased evidence only. No API charges.','']
    (path/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    return path/'report.md'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prepare','run','render'))
    parser.add_argument('directory',nargs='?')
    args=parser.parse_args()
    if args.command=='prepare': print(prepare())
    elif not args.directory: parser.error('directory required')
    elif args.command=='run': print(run(args.directory))
    else: print(render(args.directory))


if __name__=='__main__': main()
