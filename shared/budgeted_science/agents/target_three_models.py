"""Matched Sol/Terra extension; immutable three-claim science and Luna records."""
import argparse
import asyncio
from dataclasses import asdict, dataclass
from decimal import Decimal
import hashlib
import os
from pathlib import Path

from . import target_three_claims as luna
from .records import RunLog, digest, json_text, utc_now
from .reporting import _write
from .runner import provenance, run_episode
from .spending import pricing_for_model

ROOT, RUNS, read = luna.ROOT, luna.RUNS, luna.read
MODELS = ('gpt-5.6-sol', 'gpt-5.6-terra')
LUNA_PREPARED = RUNS / '20260913T085926Z-target-three-prepared-cdb738cbfa'
LUNA_RUN = LUNA_PREPARED / 'campaigns/20260913T090154Z-live-bb54d711bb'
CATALOG_HASH = '086f913625f20a5c49eac56ad8cdafeec19fa2ef5468fef2d9d8b24fca7f1d8b'


@dataclass(frozen=True)
class Config(luna.Config):
    model: str = 'gpt-5.6-sol'
    api_ceiling_usd: str = '3.00'

    def __post_init__(self):
        if self.model not in MODELS or self.api_ceiling_usd not in ('1.00', '3.00'):
            raise ValueError('exact Sol/Terra model and explicit $1/$3 ceiling required')
        luna.Config(**{**asdict(self), 'model': 'gpt-5.6-luna', 'api_ceiling_usd': '1.00'})


def prompts(config, episode):
    messages = luna.prompts(config, episode)
    phrase = 'a separate $1 API ceiling'
    if messages[1]['content'].count(phrase) != 1:
        raise ValueError('original prompt changed; review before freezing')
    messages[1]['content'] = messages[1]['content'].replace(
        phrase, f'a separate ${int(Decimal(config.api_ceiling_usd))} API ceiling')
    return messages


class Adapter(luna.Adapter):
    prompts = staticmethod(prompts)


def import_luna(prepared=LUNA_PREPARED, campaign=LUNA_RUN):
    prepared, campaign = Path(prepared).resolve(), Path(campaign).resolve()
    frozen, manifest = read(prepared / 'manifest.json'), read(campaign / 'manifest.json')
    catalog, results = read(prepared / 'catalog.json'), read(campaign / 'results.json')
    if (frozen['configuration'] != luna.Config().public() or len(frozen['slots']) != 6
            or len(results) != 6 or len({r['case_id'] for r in results}) != 6
            or frozen['catalog_hash'] != CATALOG_HASH or digest(catalog) != CATALOG_HASH
            or manifest['source_manifest_hash'] != frozen['source_manifest_hash']
            or manifest['configuration'] != frozen['configuration']
            or digest(luna.tool_definitions()) != frozen['tools_hash']):
        raise ValueError('expected original six-attempt three-claim Luna campaign')
    for relative, expected in frozen['source_hashes'].items():
        source = (ROOT / relative).resolve()
        if not source.is_relative_to(ROOT.resolve()) or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError('previously frozen source changed: ' + relative)
    by_case, payloads = {r['case_id']: r for r in results}, []
    for slot in frozen['slots']:
        directory = (prepared / 'slots' / slot['slot']).resolve()
        if not directory.is_relative_to(prepared):
            raise ValueError('imported slot outside preparation')
        payload = read(directory / 'payload.json')
        result = by_case[slot['case_id']]
        episode = Path(result['path']).resolve()
        if not episode.is_relative_to(campaign):
            raise ValueError('imported episode outside campaign')
        saved, private = read(episode / 'evaluation.json'), read(episode / 'private/study.json')
        # Preserve an incomplete original attempt as data, not a reason to rerun it.
        if (digest(payload) != slot['payload_hash'] or digest(private) != digest(payload['study'])
                or any(result[k] != v for k, v in saved.items())
                or result['evaluation']['total'] != 3
                or result['fixed_policy'] != payload['comparisons']):
            raise ValueError('Luna result, CPU comparison or study changed')
        public_episode = type('PublicEpisode', (), {'environment': luna.Audit(payload['study'])})()
        if (digest(luna.prompts(luna.Config(), public_episode)) != slot['prompt_hash']
                or digest(read(directory / 'prompts.json')) != slot['prompt_hash']):
            raise ValueError('original Luna prompt changed')
        payloads.append(payload)
    return frozen['slots'], payloads, results, {
        'prepared': str(prepared), 'campaign': str(campaign), 'manifest_hash': digest(frozen),
        'campaign_manifest_hash': digest(manifest), 'results_hash': digest(results),
        'catalog_hash': CATALOG_HASH, 'tools_hash': frozen['tools_hash']}


def prepare(root=RUNS, ceiling='3.00'):
    configs = {model: Config(model=model, api_ceiling_usd=ceiling) for model in MODELS}
    old_slots, payloads, prior, imported = import_luna()
    log, slots = RunLog(root, 'target-three-models-prepared'), []
    try:
        log.write_json('tools.json', luna.tool_definitions())
        log.write_json('luna_results.json', prior)
        for i, (old, payload) in enumerate(zip(old_slots, payloads)):
            # Case order is fixed. Alternate which model runs first within pairs.
            order = MODELS if i % 2 == 0 else tuple(reversed(MODELS))
            for model in order:
                slot = old['slot'] + '-' + model.rsplit('-', 1)[-1]
                public_episode = type('PublicEpisode', (), {'environment': luna.Audit(payload['study'])})()
                messages = prompts(configs[model], public_episode)
                log.write_json(f'slots/{slot}/payload.json', payload)
                log.write_json(f'slots/{slot}/prompts.json', messages)
                slots.append({'slot': slot, 'case_id': old['case_id'], 'source_slot': old['slot'], 'model': model,
                              'payload_hash': digest(payload), 'prompt_hash': digest(messages)})
        log.write_json('manifest.json', {'version': luna.VERSION, 'created': utc_now(),
            'configurations': {model: c.public() for model, c in configs.items()}, 'slots': slots,
            'tools_hash': digest(luna.tool_definitions()), 'luna_import': imported,
            'api_maximum_total_usd': str(12 * Decimal(ceiling)),
            'api_maximum_per_model_usd': str(6 * Decimal(ceiling)),
            'pricing_verified_utc_date': '2026-09-13',
            'pricing': {model: pricing_for_model(model) for model in MODELS},
            'initial_purchases': [], 'cpu_execution': 'import unchanged; do not rerun',
            'prompt_difference_from_luna': 'Only the declared API ceiling if different',
            'execution': '12 sequential unique slots; alternating first model; no automatic retry or resume',
            **provenance(ROOT)})
        log.event('prepared', slots=slots, api_expenditure=0)
    finally:
        log.close()
    return log.path


def load_prepared(path):
    path = Path(path).resolve()
    frozen = read(path / 'manifest.json')
    configs = {m: Config(**c) for m, c in frozen['configurations'].items()}
    slots = frozen['slots']
    if (set(configs) != set(MODELS) or any(configs[m].model != m for m in MODELS)
            or len({c.api_ceiling_usd for c in configs.values()}) != 1
            or frozen['version'] != luna.VERSION or len(slots) != 12
            or len({s['slot'] for s in slots}) != 12
            or len({(s['case_id'], s['model']) for s in slots}) != 12
            or any(sum(s['model'] == m for s in slots) != 6 for m in MODELS)
            or frozen['source_manifest_hash'] != provenance(ROOT)['source_manifest_hash']
            or frozen['tools_hash'] != digest(luna.tool_definitions())
            or frozen['tools_hash'] != digest(read(path / 'tools.json'))
            or frozen['api_maximum_total_usd'] != str(12 * Decimal(configs[MODELS[0]].api_ceiling_usd))
            or frozen['api_maximum_per_model_usd'] != str(6 * Decimal(configs[MODELS[0]].api_ceiling_usd))
            or frozen['luna_import']['results_hash'] != digest(read(path / 'luna_results.json'))):
        raise ValueError('frozen model campaign or imported results changed')
    prior = read(path / 'luna_results.json')
    prior_ids = {r['case_id'] for r in prior}
    if len(prior_ids) != 6 or any({s['case_id'] for s in slots if s['model'] == m} != prior_ids for m in MODELS):
        raise ValueError('model/case mapping differs from Luna')
    expected_order = [(r['slot'] + '-' + model.rsplit('-', 1)[-1], r['case_id'], r['slot'], model)
                      for i, r in enumerate(prior)
                      for model in (MODELS if i % 2 == 0 else tuple(reversed(MODELS)))]
    if [(s['slot'], s['case_id'], s['source_slot'], s['model']) for s in slots] != expected_order:
        raise ValueError('frozen execution order changed')
    payloads, paired = [], {}
    for slot in slots:
        directory = (path / 'slots' / slot['slot']).resolve()
        if not directory.is_relative_to(path):
            raise ValueError('slot outside campaign')
        payload = read(directory / 'payload.json')
        public_episode = type('PublicEpisode', (), {'environment': luna.Audit(payload['study'])})()
        if (digest(payload) != slot['payload_hash']
                or digest(prompts(configs[slot['model']], public_episode)) != slot['prompt_hash']
                or digest(read(directory / 'prompts.json')) != slot['prompt_hash']):
            raise ValueError('study or prompt changed')
        if slot['case_id'] in paired and paired[slot['case_id']] != payload:
            raise ValueError('models must receive identical scientific payloads')
        paired[slot['case_id']] = payload
        payloads.append(payload)
    return frozen, configs, payloads


async def run(prepared, mode, gateway_factory=None):
    if mode not in ('dry-run', 'live'):
        raise ValueError('explicit dry-run or live required')
    prepared = Path(prepared).resolve()
    frozen, configs, payloads = load_prepared(prepared)
    if mode == 'live':
        luna.previous.mark_attempt(prepared / 'live-attempt.json', {'started': utc_now(),
            'maximum_usd': frozen['api_maximum_total_usd'], 'configurations': frozen['configurations'],
            'policy': '12 authorized attempts only; no retries or transferred allowances'})
    log, results = RunLog(prepared / 'campaigns', mode), []
    try:
        log.write_json('manifest.json', {**frozen, 'mode': mode, 'prepared': str(prepared)})
        log.write_json('luna_results.json', read(prepared / 'luna_results.json'))
        for slot, payload in zip(frozen['slots'], payloads):
            config = configs[slot['model']]
            log.write_json(f'states/{slot["slot"]}-attempt.json', {'started': utc_now(), 'ceiling_usd': config.api_ceiling_usd})
            log.event('slot_started', slot=slot['slot'], model=config.model)
            print(f"Starting {mode} {slot['slot']}", flush=True)
            gateway = gateway_factory(config) if gateway_factory else None
            path, reason = await run_episode(ROOT, log.path / 'episodes', mode=mode, config=config,
                instance=luna.Instance(**payload), adapter=Adapter, gateway=gateway)
            result = {**slot, 'path': str(path), **read(path / 'evaluation.json')}
            results.append(result)
            log.write_json(f'states/{slot["slot"]}-result.json', result)
            log.write_json(f'states/results-through-{slot["slot"]}.json', results)
            log.event('slot_finished', slot=slot['slot'], termination=reason, path=str(path))
            r = result['evaluation']
            print(f"Finished {slot['slot']}: {reason}; correct={r['correct']} wrong={r['wrong']} "
                  f"abstain={r['abstained']} spent={r['scientific_status']['spent']}", flush=True)
            if reason not in {'submitted', 'api_ceiling', 'deadline', 'response_limit', 'tool_request_limit',
                              'no_submission', 'model_output_incomplete', 'refusal'}:
                log.event('campaign_halted', reason=reason)
                break
    finally:
        try:
            log.write_json('results.json', results)
        finally:
            log.close()
        render_campaign(log.path)
    return log.path


def totals(rows):
    evaluations = [r['evaluation'] for r in rows]
    return {**{k: sum(r[k] for r in evaluations) for k in ('correct', 'wrong', 'abstained', 'utility', 'incomplete_claims')},
            'attempted': len(rows), 'completed': sum(r['completed'] for r in evaluations),
            'credits': sum(r['scientific_status']['spent'] for r in evaluations),
            'api_committed_upper_usd': str(sum((Decimal(r['api_budget']['committed_upper_usd']) for r in rows), Decimal(0)))}


def render_campaign(path):
    path = Path(path).resolve()
    manifest, rows, prior = read(path / 'manifest.json'), read(path / 'results.json'), read(path / 'luna_results.json')
    summary = {m: {**totals([r for r in rows if r['model'] == m]), 'planned': 6} for m in MODELS}
    summary['gpt-5.6-luna'] = {**totals(prior), 'imported': True}
    cpu = [r['fixed_policy'][luna.COMPARISON] for r in prior]
    summary[luna.COMPARISON] = {**{k: sum(r[k] for r in cpu) for k in ('correct', 'wrong', 'abstained', 'utility', 'incomplete_claims')},
                              'completed': sum(r['completed'] for r in cpu), 'credits': sum(r['scientific_status']['spent'] for r in cpu)}
    summary['new_api_upper_usd'] = str(sum((Decimal(summary[m]['api_committed_upper_usd']) for m in MODELS), Decimal(0)))
    summary['actual_offline_api_usd'] = 0 if manifest['mode'] == 'dry-run' else None
    _write(path / 'summary.json', json_text(summary) + '\n')
    lines = ['# Three target claims: Sol/Terra matched extension', '', f"Mode: {manifest['mode']}.", '',
             'Six studies per model, three claims per study, 32 scientific credits each. High reasoning.', '',
             '| Method | Correct / 18 | Wrong | Abstain | Unsubmitted (attempted) | Completed | Credits |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for method in (*MODELS, 'gpt-5.6-luna', luna.COMPARISON):
        r = summary[method]
        lines.append(f"| {method} | {r['correct']} | {r['wrong']} | {r['abstained']} | {r['incomplete_claims']} | "
                     f"{r['completed']}/6 | {r['credits']} |")
    lines += ['', 'Unstarted slots are not attempts; see attempted/planned counts below. Incomplete attempts '
              'are not scored as wrong verdicts or abstentions. CPU and Luna records are imported unchanged.', '',
              '| Study | Model | Correct | Wrong | Abstain | Status | Credits | Transcript |',
              '|---|---|---:|---:|---:|---|---:|---|']
    for r in rows:
        e = r['evaluation']
        link = Path(os.path.relpath(Path(r['path']) / 'transcript.md', path)).as_posix()
        lines.append(f"| {r['source_slot']} | {r['model']} | {e['correct']} | {e['wrong']} | {e['abstained']} | "
                     f"{r['termination_reason']} | {e['scientific_status']['spent']} | [trace]({link}) |")
    lines += ['', '## Imported Luna and CPU traces', '']
    for r in prior:
        trace = Path(os.path.relpath(Path(r['path']) / 'transcript.md', path)).as_posix()
        cpu_trace = Path(os.path.relpath(Path(r['fixed_policy'][luna.COMPARISON]['path']) / 'transcript.md', path)).as_posix()
        lines.append(f"- {r['slot']}: [Luna]({trace}), [CPU]({cpu_trace}).")
    lines += ['', '## Accounting and counts', '', '```json', json_text(summary), '```', '',
              'Scientific prompts/tools are identical across Sol and Terra. Only the disclosed API-dollar '
              'cap may differ from Luna. Histories, ledgers and purchases are independent. These are three '
              'engineered development pairs, not independent random systems. No hidden-reference access '
              'or language-judge scoring. No retries or live crash-resume. Raw internal reasoning is not '
              'available; all API-visible material is retained locally. No general model ranking or '
              'causal allocation advantage is established by this small pilot.', '']
    _write(path / 'report.md', '\n'.join(lines))
    return path / 'report.md'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'dry-run', 'live', 'render', 'render-episode'))
    parser.add_argument('directory', nargs='?')
    parser.add_argument('--api-ceiling', choices=('1.00', '3.00'))
    args = parser.parse_args()
    if args.api_ceiling is not None and args.command != 'prepare':
        parser.error('ceiling is frozen at preparation, not launch')
    if args.command == 'prepare':
        print(prepare(ceiling=args.api_ceiling or '3.00'))
    elif not args.directory:
        parser.error('directory required')
    elif args.command == 'render':
        print(render_campaign(args.directory))
    elif args.command == 'render-episode':
        print(luna.regenerate(args.directory))
    else:
        print(asyncio.run(run(args.directory, args.command)))


if __name__ == '__main__':
    main()
