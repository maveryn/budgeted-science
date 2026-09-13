"""Freeze six development studies, run CPU controls, regenerate saved reports."""
import argparse
from collections import defaultdict
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess
import time

from ..agents.records import RunLog,digest,json_text,read_events
from .core import VERSION,Session,build_catalog
from .policies import METHODS,LOW_RELATIVE_SD,run_policy

ROOT=Path(__file__).resolve().parents[3]
RUNS=ROOT/'demos/paired_claim_audit/runs'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def provenance():
    files=sorted((ROOT/'shared/budgeted_science').rglob('*.py'))
    files+=sorted((ROOT/'tests').glob('test_paired_claim*.py'))
    hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    return {'source_hashes':hashes,'source_manifest_hash':digest(hashes),
            'versions':{'python':platform.python_version(),**{p:version(p) for p in ('numpy','scipy')}},
            'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()}


def prepare(root=RUNS):
    log=RunLog(root,'paired-prepared')
    try:
        catalog=build_catalog()
        log.write_json('catalog.json',catalog)
        log.write_json('manifest.json',{'version':VERSION,'mode':'CPU-only development',
            'catalog_hash':digest(catalog),'budgets':[24,32],'methods':list(METHODS),
            'utility':{'correct':1,'wrong':-2,'abstain':0},'low_relative_sd':LOW_RELATIVE_SD,
            'noise_replicates_per_pair':1,**provenance()})
        log.event('prepared',case_count=len(catalog['cases']),catalog_hash=digest(catalog),api_spending=0)
    finally:
        log.close()
    return log.path


def run_case(case,budget,method,root):
    log=RunLog(root,'cpu')
    started=time.monotonic()
    result=None
    try:
        log.write_json('private/study.json',case['study'])
        session=Session(case['study'],budget,log)
        public=session.environment.public
        log.write_json('public/input.json',session.environment.evidence())
        log.write_json('manifest.json',{'version':VERSION,'mode':'CPU','case_id':case['case_id'],
                                     'budget':budget,'method':method,'api_spending':0})
        reason='submitted'
        try:
            run_policy(method,public,session.call,lambda kind,**data:log.event(kind,**data))
            if session.environment.submission is None:
                reason='no_submission'
        except Exception as exc:
            reason='incomplete'
            log.event('interruption',error=log.redactor.error(exc))
        result={**session.environment.evaluate(),'method':method,'case_id':case['case_id'],
                'pair':case['study']['private']['pair_index'],'member':case['study']['private']['member'],
                'budget':budget,'termination':reason,'runtime_seconds':time.monotonic()-started,
                'path':str(log.path),'api_spending':0,'tool_requests':session.calls}
        log.write_json('evaluation.json',result)
        log.event('finished',result=result)
    finally:
        log.close()
    render_case(log.path)
    return result


def summarize(results):
    groups=defaultdict(list)
    for r in results:
        groups[r['budget'],r['method']].append(r)
    rows=[]
    for (budget,method),items in sorted(groups.items()):
        rows.append({'budget':budget,'method':method,'episodes':len(items),'claims':sum(x['total'] for x in items),
                     **{k:sum(x[k] for x in items) for k in ('correct','wrong','abstained','incomplete_claims','utility')},
                     'incomplete_episodes':sum(not x['completed'] for x in items),
                     'mean_spent':sum(x['scientific_status']['spent'] for x in items)/len(items),
                     'runtime_seconds':sum(x['runtime_seconds'] for x in items)})
    return rows


def pilot(prepared,root=RUNS):
    prepared=Path(prepared).resolve()
    frozen,catalog=read(prepared/'manifest.json'),read(prepared/'catalog.json')
    if (frozen['version']!=VERSION or digest(catalog)!=frozen['catalog_hash']
            or frozen['source_manifest_hash']!=provenance()['source_manifest_hash']
            or frozen['methods']!=list(METHODS) or frozen['low_relative_sd']!=LOW_RELATIVE_SD):
        raise ValueError('frozen catalog or implementation changed')
    log=RunLog(root,'paired-pilot')
    results=[]
    try:
        log.write_json('manifest.json',{**frozen,'prepared':str(prepared),'kind':'96 CPU episodes, six studies, no agents'})
        log.write_json('catalog.json',catalog)
        for budget in frozen['budgets']:
            for case in catalog['cases']:
                for method in frozen['methods']:
                    result=run_case(case,budget,method,log.path/'episodes')
                    results.append(result)
                    log.event('episode_finished',case_id=case['case_id'],budget=budget,method=method,
                              correct=result['correct'],wrong=result['wrong'],abstained=result['abstained'],path=result['path'])
                print(f"CPU budget={budget}, case={case['case_id']} complete",flush=True)
        log.write_json('results.json',results)
        log.write_json('summary.json',summarize(results))
    finally:
        log.close()
    render(log.path)
    return log.path


def _write(path,text):
    Path(path).write_text(text,encoding='utf-8')


def render_case(path):
    path=Path(path)
    events,torn=read_events(path)
    lines=['# Paired claim CPU transcript','','Scripted classical policy; zero API expenditure.','',
           '## Public input','','```json',json_text(read(path/'public/input.json')),'```','']
    for e in events:
        if e['kind'] in ('tool_requested','tool_result','final_belief','interruption'):
            lines += ['## '+e['kind'],'','```json',json_text(e),'```','']
        elif e['kind']=='action_scores':
            lines += ['## Candidate acquisition scores','','```json',json_text(e),'```','']
    if torn:
        lines+=['Unfinished last log line preserved.','']
    lines+=['[Private evaluation](evaluation.json) | [Complete journal](events.jsonl)','']
    _write(path/'transcript.md','\n'.join(lines))


def render(path):
    path=Path(path).resolve()
    results=read(path/'results.json')
    summary=summarize(results)
    lines=['# Paired claim verification: CPU commissioning','','Six designed development studies: three paired worlds, one noise realization per pair. '
           'No live agents. Each method has an independent scientific ledger.','',
           '| Budget | Method | Correct / 36 | Wrong | Abstain | +1/-2/0 | Mean spent | Incomplete |',
           '|---:|---|---:|---:|---:|---:|---:|---:|']
    for r in summary:
        lines.append(f"| {r['budget']} | {r['method']} | {r['correct']} | {r['wrong']} | {r['abstained']} | {r['utility']} | {r['mean_spent']:.2f} | {r['incomplete_episodes']} |")
    lines+=['','## Individual results','','| Case | Budget | Method | Correct | Wrong | Abstain | Utility | Spent | Transcript |',
            '|---|---:|---|---:|---:|---:|---:|---:|---|']
    for r in results:
        relative=Path(r['path']).relative_to(path).as_posix()
        lines.append(f"| {r['case_id']} | {r['budget']} | {r['method']} | {r['correct']} | {r['wrong']} | {r['abstained']} | {r['utility']} | {r['scientific_status']['spent']:g} | [trace]({relative}/transcript.md) |")
    lines+=['','## Interpretation limits','',
        'All acquisition policies share the same two-fit estimator and paid 9-credit initialization. '
        'The supplied fits are not an exhaustive-model guarantee in the public task, but cover the hidden targets in these development cases. '
        'The policies assume that small model set is sufficient; their 10% low-fidelity discrepancy model and Gaussian/delta approximations are unvalidated. '
        'High-probability verdicts are not certificates. Cases and tolerances were selected for commissioning, not held-out evaluation. '
        'The best fixed control among those tested is not an optimal fixed policy. No statistical significance, general agent superiority, '
        'or adaptive advantage should be inferred unless supported by the actual comparisons.','',
        'The new utility is reported alongside raw verdict counts; earlier runs used raw correctness and are not rescored here. '
        'No savings bonus or full-budget requirement. Real observations are still simulated.','']
    _write(path/'report.md','\n'.join(lines))
    _write(path/'summary.json',json_text(summary)+'\n')
    return path/'report.md'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prepare','pilot','render'))
    parser.add_argument('directory',nargs='?')
    args=parser.parse_args()
    if args.command=='prepare':
        print(prepare())
    elif not args.directory:
        parser.error('directory required')
    elif args.command=='pilot':
        print(pilot(args.directory))
    else:
        print(render(args.directory))


if __name__=='__main__':
    main()
