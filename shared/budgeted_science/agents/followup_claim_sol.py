"""Matched Sol/high follow-up; preserve the frozen Luna implementation and runs."""
import argparse
import asyncio
from dataclasses import asdict, dataclass
from decimal import Decimal
import hashlib
from pathlib import Path

from . import followup_claim_audit as luna
from .records import RunLog, digest, json_text, utc_now
from .reporting import _write, regenerate as generic_regenerate
from .runner import provenance, run_episode
from .spending import pricing_for_model

ROOT, RUNS, read = luna.ROOT, luna.RUNS, luna.read
LUNA_PREPARED = RUNS / '20260913T051751Z-followup-luna-prepared-db46c28d52'
LUNA_RUN = LUNA_PREPARED / 'campaigns/20260913T051840Z-live-e24616a723'


@dataclass(frozen=True)
class Config(luna.Config):
    model: str = 'gpt-5.6-sol'
    api_ceiling_usd: str = '3.00'

    def __post_init__(self):
        if self.model != 'gpt-5.6-sol' or self.api_ceiling_usd not in ('1.00', '3.00'):
            raise ValueError('Exact Sol model and explicitly selected $1/$3 episode ceiling required')
        original = {**asdict(self), 'model': 'gpt-5.6-luna', 'api_ceiling_usd': '1.00'}
        luna.Config(**original)


def prompts(config, episode):
    messages = luna.prompts(config, episode)
    messages[1]['content'] = messages[1]['content'].replace(
        'a separate $1 API ceiling', f'a separate ${int(Decimal(config.api_ceiling_usd))} API ceiling')
    return messages


def write_report(path, manifest, events, finished, status):
    result = luna.write_report(path, manifest, events, finished, status)
    report = path / 'report.md'
    _write(report, report.read_text(encoding='utf-8').replace('Luna chooses freely', 'Sol chooses freely'))
    return result


def regenerate(path):
    return generic_regenerate(Path(path), report_writer=write_report)


class Adapter(luna.Adapter):
    prompts = staticmethod(prompts)
    regenerate = staticmethod(regenerate)
    scripted_gateway = staticmethod(lambda config: luna.mixed.SolFake())


def import_luna(prepared=LUNA_PREPARED, campaign=LUNA_RUN):
    prepared, campaign = Path(prepared).resolve(), Path(campaign).resolve()
    frozen = read(prepared / 'manifest.json')
    results = read(campaign / 'results.json')
    if (frozen['configuration'] != luna.Config().public() or len(results) != 6
            or frozen['imports']['catalog_hash'] != luna.CATALOG_HASH):
        raise ValueError('Expected original six-study Luna/high campaign')
    for relative, expected in frozen['source_hashes'].items():
        source = (ROOT / relative).resolve()
        if not source.is_relative_to(ROOT.resolve()) or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError('Previously frozen source changed: ' + relative)
    if len({r['case_id'] for r in results}) != 6:
        raise ValueError('Duplicate Luna case')
    by_case = {r['case_id']: r for r in results}
    payloads = []
    for slot in frozen['slots']:
        directory = (prepared / 'slots' / slot['slot']).resolve()
        if not directory.is_relative_to(prepared):
            raise ValueError('Invalid original slot path')
        payload = read(directory / 'payload.json')
        result = by_case[slot['case_id']]
        episode = Path(result['path']).resolve()
        if not episode.is_relative_to(campaign):
            raise ValueError('Imported episode outside Luna campaign')
        saved = read(episode / 'evaluation.json')
        if (digest(payload) != slot['payload_hash'] or not result['evaluation']['completed']
                or result['termination_reason'] != 'submitted'
                or any(result[k] != value for k, value in saved.items())
                or digest(read(episode / 'private/study.json')) != digest(payload['study'])):
            raise ValueError('Luna result or study mismatch')
        public_episode = type('PublicEpisode', (), {'environment': luna.Audit(payload['study'], budget=32)})()
        if (digest(luna.prompts(luna.Config(), public_episode)) != slot['prompt_hash']
                or digest(read(directory / 'prompts.json')) != slot['prompt_hash']):
            raise ValueError('Luna prompt mismatch')
        payloads.append(payload)
    return frozen['slots'], payloads, results, {
        'prepared': str(prepared), 'campaign': str(campaign), 'manifest_hash': digest(frozen),
        'results_hash': digest(results), 'catalog_hash': luna.CATALOG_HASH,
        'tools_hash': frozen['tools_hash']}


def prepare(root=RUNS, config=None):
    config = config or Config()
    old_slots, payloads, results, imported = import_luna()
    log, slots = RunLog(root, 'followup-sol-prepared'), []
    try:
        log.write_json('tools.json', luna.tool_definitions(config))
        if digest(luna.tool_definitions(config)) != imported['tools_hash']:
            raise ValueError('Tool definitions must match Luna exactly')
        log.write_json('luna_results.json', results)
        for old, payload in zip(old_slots, payloads):
            public_episode = type('PublicEpisode', (), {'environment': luna.Audit(payload['study'], budget=32)})()
            messages = prompts(config, public_episode)
            log.write_json(f"slots/{old['slot']}/payload.json", payload)
            log.write_json(f"slots/{old['slot']}/prompts.json", messages)
            slots.append({**old, 'payload_hash': digest(payload), 'prompt_hash': digest(messages)})
        log.write_json('manifest.json', {'version': luna.VERSION, 'created': utc_now(),
            'configuration': config.public(), 'slots': slots, 'tools_hash': digest(luna.tool_definitions(config)),
            'luna_import': imported, 'api_maximum_total_usd': str(6 * Decimal(config.api_ceiling_usd)),
            'pricing_verified_utc_date': '2026-09-13', 'pricing': pricing_for_model(config.model),
            'initial_purchases': [], 'utility': {'correct': 1, 'wrong': -2, 'abstain': 0},
            'prompt_difference_from_luna': 'Only the declared API ceiling, if different; no scientific changes',
            'execution': 'Six sequential slots; no retries, substitutions, resume or automatic ceiling increases',
            **provenance(ROOT)})
        log.event('prepared', slots=slots, api_expenditure=0)
    finally:
        log.close()
    return log.path


def load_prepared(path):
    path = Path(path).resolve()
    frozen = read(path / 'manifest.json')
    config = Config(**frozen['configuration'])
    slots = frozen['slots']
    if (frozen['version'] != luna.VERSION or len(slots) != 6
            or len({s['case_id'] for s in slots}) != 6 or len({s['slot'] for s in slots}) != 6
            or frozen['source_manifest_hash'] != provenance(ROOT)['source_manifest_hash']
            or frozen['tools_hash'] != digest(luna.tool_definitions(config))
            or frozen['tools_hash'] != digest(read(path / 'tools.json'))
            or frozen['api_maximum_total_usd'] != str(6 * Decimal(config.api_ceiling_usd))
            or frozen['luna_import']['results_hash'] != digest(read(path / 'luna_results.json'))):
        raise ValueError('Frozen Sol campaign or imported results changed')
    payloads = []
    for slot in slots:
        directory = (path / 'slots' / slot['slot']).resolve()
        if not directory.is_relative_to(path):
            raise ValueError('Slot outside campaign')
        payload = read(directory / 'payload.json')
        public_episode = type('PublicEpisode', (), {'environment': luna.Audit(payload['study'], budget=32)})()
        if (digest(payload) != slot['payload_hash'] or digest(prompts(config, public_episode)) != slot['prompt_hash']
                or digest(read(directory / 'prompts.json')) != slot['prompt_hash']):
            raise ValueError('Frozen study or prompt changed')
        payloads.append(payload)
    return frozen, config, payloads


async def run(prepared, mode, gateway_factory=None):
    if mode not in ('dry-run', 'live'):
        raise ValueError('Explicit dry-run or live required')
    prepared = Path(prepared).resolve()
    frozen, config, payloads = load_prepared(prepared)
    if mode == 'live':
        luna.mark_attempt(prepared / 'live-attempt.json', {'started': utc_now(),
            'maximum_usd': frozen['api_maximum_total_usd'], 'per_episode_usd': config.api_ceiling_usd,
            'policy': 'Six authorized attempts only; no repeats or transferred allowances'})
    log, results = RunLog(prepared / 'campaigns', mode), []
    try:
        log.write_json('manifest.json', {**frozen, 'mode': mode, 'prepared': str(prepared)})
        log.write_json('luna_results.json', read(prepared / 'luna_results.json'))
        for slot, payload in zip(frozen['slots'], payloads):
            marker = {'slot': slot['slot'], 'started': utc_now(), 'ceiling_usd': config.api_ceiling_usd}
            log.write_json(f"states/{slot['slot']}-attempt.json", marker)
            log.event('slot_started', **marker)
            print(f"Starting Sol {mode} study {slot['slot']}", flush=True)
            gateway = gateway_factory() if gateway_factory else None
            path, reason = await run_episode(ROOT, log.path / 'episodes', mode=mode, config=config,
                instance=luna.Instance(**payload), adapter=Adapter, gateway=gateway)
            result = {'slot': slot['slot'], 'case_id': slot['case_id'], 'path': str(path),
                      **read(path / 'evaluation.json')}
            results.append(result)
            log.write_json(f"states/{slot['slot']}-result.json", result)
            log.event('slot_finished', slot=slot['slot'], path=str(path), termination=reason)
            r = result['evaluation']
            print(f"Finished {slot['slot']}: {reason}; correct={r['correct']} wrong={r['wrong']} "
                  f"abstain={r['abstained']} credits={r['scientific_status']['spent']}", flush=True)
            if reason not in {'submitted', 'api_ceiling', 'deadline', 'response_limit', 'tool_request_limit',
                              'no_submission', 'model_output_incomplete', 'refusal'}:
                log.event('campaign_halted', reason=reason)
                break
    finally:
        log.write_json('results.json', results)
        log.close()
        render_campaign(log.path)
    return log.path


def render_campaign(path):
    path = Path(path).resolve()
    report = luna.render_campaign(path)
    text = report.read_text(encoding='utf-8').replace('# Luna/high:', '# Sol/high:').replace(
        'not imposed on Luna', 'not imposed on Sol')
    results, prior = read(path / 'results.json'), read(path / 'luna_results.json')
    text += '\n## Matched saved Luna outcomes\n\n'
    text += '| Study | Sol correct / wrong / abstain | Luna correct / wrong / abstain | Luna transcript |\n'
    text += '|---|---|---|---|\n'
    by_case = {r['case_id']: r for r in prior}
    for r in results:
        old = by_case[r['case_id']]
        counts = lambda value: ' / '.join(str(value[k]) for k in ('correct', 'wrong', 'abstained'))
        target = (Path(old['path']) / 'transcript.md').as_posix()
        text += f"| {r['slot']} | {counts(r['evaluation'])} | {counts(old['evaluation'])} | [trace]({target}) |\n"
    text += ('\nLuna records are imported unchanged. Independent conversations, purchases and API ledgers; '
             'identical public science and tools. Only the model and, if approved, API-dollar cap differ. '
             'All planned studies remain in the protocol; incomplete or unstarted episodes are not silently dropped.\n')
    _write(report, text)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'dry-run', 'live', 'render', 'render-episode'))
    parser.add_argument('directory', nargs='?')
    parser.add_argument('--api-ceiling', choices=('1.00', '3.00'))
    args = parser.parse_args()
    if args.api_ceiling is not None and args.command != 'prepare':
        parser.error('Ceiling is frozen at preparation and cannot be overridden at launch')
    if args.command == 'prepare':
        print(prepare(config=Config(api_ceiling_usd=args.api_ceiling or '3.00')))
    elif not args.directory:
        parser.error('Directory required')
    elif args.command == 'render':
        print(render_campaign(args.directory))
    elif args.command == 'render-episode':
        print(regenerate(args.directory))
    else:
        print(asyncio.run(run(args.directory, args.command)))


if __name__ == '__main__':
    main()
