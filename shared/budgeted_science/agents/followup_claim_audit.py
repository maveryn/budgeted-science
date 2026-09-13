"""Six frozen follow-up studies; independently logged Luna/high episodes."""
import argparse
import asyncio
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from ..paired_claim_audit.followup_core import Audit, VERSION
from . import mixed_claim_audit as mixed
from . import multi_claim_audit as legacy
from .records import RunLog, digest, json_text, read_events, utc_now
from .reporting import _write, regenerate as generic_regenerate
from .runner import provenance, run_episode
from .spending import pricing_for_model

ROOT = legacy.ROOT
RUNS = ROOT / 'demos/paired_claim_audit/runs'
PREPARED = RUNS / '20260913T044814Z-followup-prepared-3e6ff0218b'
CPU = RUNS / '20260913T044853Z-followup-pilot-a183dde9e0'
CATALOG_HASH = '79543b99a111c52c25aff7d851b5a6e99b6cb3c9e660387fc4dcfd47908c6b3d'
COMPARISONS = ('adaptive_followup', 'fixed:x:4:fit', 'fixed:x:4:fit_reject',
               'fixed:none:0:intervention', 'adaptive_full')
read = legacy.read_json


@dataclass(frozen=True)
class Config:
    model: str = 'gpt-5.6-luna'
    reasoning_effort: str = 'high'
    scientific_budget: int = 32
    api_ceiling_usd: str = '1.00'
    max_responses: int = 30
    max_output_tokens: int = 32768
    max_tool_requests: int = 60
    deadline_seconds: float = 1200.0
    task_variant: str = VERSION

    def __post_init__(self):
        if tuple(asdict(self).values()) != ('gpt-5.6-luna', 'high', 32, '1.00', 30, 32768, 60, 1200., VERSION):
            raise ValueError('Frozen Luna/high protocol; no settings overrides')

    def public(self):
        return asdict(self)


@dataclass(frozen=True)
class Instance:
    study: dict
    comparisons: dict = field(default_factory=dict)

    def private(self):
        return {'study_hash': digest(self.study), 'noise_seed': self.study['private']['noise_seed'],
                'pair_index': self.study['private']['pair_index'], 'member': self.study['private']['member']}


tool_definitions = mixed.tool_definitions


def prompts(config, episode):
    messages = mixed.prompts(config, episode)
    original = ('Score: correct verdicts out of six; wrong verdicts, abstentions and coverage\n'
                'are reported separately. Abstentions are not correct binary verdicts.')
    replacement = ('Score: +1 for a correct verdict, -2 for a wrong verdict, and 0 for ABSTAIN.\n'
                   'Maximize total score across the six claims. Correct verdicts, wrong verdicts,\n'
                   'abstentions and coverage are also reported separately. Abstentions are not\n'
                   'correct binary verdicts.')
    if original not in messages[1]['content']:
        raise ValueError('Upstream prompt changed; review before freezing')
    messages[1]['content'] = messages[1]['content'].replace(original, replacement)
    messages[1]['content'] = messages[1]['content'].replace(
        'Read the definitions in each claim carefully.',
        'Read the definitions in each claim carefully. Fractional grid-peak reduction\n'
        'means (baseline peak - intervention peak) / baseline peak. The baseline\n'
        'and intervention use the report parameters, not estimated target parameters.')
    return messages


class Episode(legacy.Episode):
    def __init__(self, config, instance, log, deadline=None):
        self.config, self.instance, self.log, self.deadline = config, instance, log, deadline
        self.parent_call, self.request_count, self.submission = None, 0, None
        self.executed = {}
        self.schemas = {t['name']: t['parameters'] for t in tool_definitions(config)}
        self.artifact_number = 0
        log.write_json('private/study.json', instance.study)
        log.write_json('public/study.json', instance.study['public'])
        self.environment = Audit(instance.study, self._event, budget=config.scientific_budget)


def write_report(path, manifest, events, finished, status):
    lines = ['# Follow-up claim audit episode', '', f"Mode: {manifest['mode']}; termination: {status}.", '',
             '32 scientific credits; 1/8/12 prices; +1 correct / -2 wrong / 0 abstain.', '']
    if finished:
        data = {k: finished[k] for k in ('termination_reason', 'evaluation', 'fixed_policy', 'api_budget',
                                       'model_responses', 'elapsed_seconds')}
        _write(path / 'evaluation.json', json_text(data) + '\n')
        lines += ['| Investigator | Correct | Wrong | Abstain | Utility | Credits |',
                  '|---|---:|---:|---:|---:|---:|']
        investigators = [(manifest['public_configuration']['model'] if manifest['mode'] == 'live'
                          else 'Scripted fixture', data['evaluation'])]
        investigators += list((data['fixed_policy'] or {}).items())
        for name, r in investigators:
            lines.append(f"| {name} | {r['correct']} | {r['wrong']} | {r['abstained']} | {r['utility']} | {r['scientific_status']['spent']} |")
        lines += ['', '| Claim | Kind | Reference | Truth | Submitted |', '|---|---|---:|---|---|']
        for r in data['evaluation']['rows']:
            lines.append(f"| {r['id']} | {r['kind']} | {r['reference_value']:.10g} | {r['truth']} | {r['verdict']} |")
        lines += ['', '## Submission', '', '```json', json_text(data['evaluation']['submission']), '```', '',
                  '## API accounting', '', 'Conservative bound, not an invoice. Offline fixture spending is zero.',
                  '', '```json', json_text(data['api_budget']), '```', '']
    lines += ['[Transcript](transcript.md) | [Events](events.jsonl) | [Prompts](prompts.json) | [Tools](tools.json)', '',
              'One engineered development study. Correct verdicts do not certify explanations. The CPU policies '
              'use a restricted two-fit estimator and paid initialization; Luna chooses freely from the same tools. '
              'No arbitrary code or physical validation. Checkpoints support inspection, not live crash-resume.', '']
    _write(path / 'report.md', '\n'.join(lines))
    return path / 'transcript.md', path / 'report.md'


def regenerate(path):
    return generic_regenerate(Path(path), report_writer=write_report)


class Adapter:
    create_episode = staticmethod(Episode)
    prompts = staticmethod(prompts)
    tool_definitions = staticmethod(tool_definitions)
    regenerate = staticmethod(regenerate)
    scripted_gateway = staticmethod(lambda config: legacy.Fake())
    run_comparisons = staticmethod(legacy.Adapter.run_comparisons)


def import_catalog(prepared, cpu):
    frozen, catalog = read(Path(prepared) / 'manifest.json'), read(Path(prepared) / 'catalog.json')
    cpu_manifest = read(Path(cpu) / 'manifest.json')
    results = read(Path(cpu) / 'results.json')
    if (frozen['version'] != VERSION or digest(catalog) != CATALOG_HASH
            or frozen['catalog_hash'] != CATALOG_HASH or cpu_manifest['catalog_hash'] != CATALOG_HASH
            or digest(read(Path(cpu) / 'catalog.json')) != CATALOG_HASH):
        raise ValueError('Wrong or modified frozen six-study catalog')
    # Added runner files need not have existed in the CPU snapshot. Every
    # previously frozen file must remain identical; do not regenerate cases.
    for relative, expected in frozen['source_hashes'].items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Imported CPU source changed: ' + relative)
    cases = catalog['cases']
    if len(cases) != 6 or len({c['case_id'] for c in cases}) != 6:
        raise ValueError('Expected six unique studies')
    snapshots = {}
    for case in cases:
        ident = case['case_id']
        selected = [r for r in results if r['case_id'] == ident and r['method'] in COMPARISONS]
        if len(selected) != len(COMPARISONS) or {r['method'] for r in selected} != set(COMPARISONS):
            raise ValueError('Missing or duplicate imported CPU comparison')
        for r in selected:
            if not r['completed'] or r['budget'] != 32:
                raise ValueError('Incomplete or mismatched CPU snapshot')
        snapshots[ident] = {r['method']: r for r in selected}
    imports = {'prepared': str(Path(prepared).resolve()), 'cpu': str(Path(cpu).resolve()),
               'catalog_hash': CATALOG_HASH, 'cpu_results_hash': digest(results),
               'cpu_manifest_hash': digest(cpu_manifest), 'prepared_manifest_hash': digest(frozen)}
    return cases, snapshots, imports


def prepare(root=RUNS, prepared=PREPARED, cpu=CPU):
    cases, comparisons, imports = import_catalog(prepared, cpu)
    config, log = Config(), RunLog(root, 'followup-luna-prepared')
    slots = []
    try:
        log.write_json('tools.json', tool_definitions(config))
        for i, case in enumerate(cases):
            slot = f'{i+1:02d}-{case["case_id"]}'
            payload = {'study': case['study'], 'comparisons': comparisons[case['case_id']]}
            public_episode = type('PublicEpisode', (), {'environment': Audit(case['study'], budget=32)})()
            messages = prompts(config, public_episode)
            log.write_json(f'slots/{slot}/payload.json', payload)
            log.write_json(f'slots/{slot}/prompts.json', messages)
            slots.append({'slot': slot, 'case_id': case['case_id'], 'payload_hash': digest(payload),
                          'prompt_hash': digest(messages)})
        log.write_json('manifest.json', {'version': VERSION, 'created': utc_now(), 'configuration': config.public(),
            'slots': slots, 'tools_hash': digest(tool_definitions(config)), 'imports': imports,
            'api_maximum_total_usd': '6.00', 'pricing_verified_utc_date': '2026-09-13',
            'pricing': pricing_for_model(config.model), 'utility': {'correct': 1, 'wrong': -2, 'abstain': 0},
            'initial_purchases': [], 'sample_status': 'six existing engineered development studies',
            'execution': 'sequential; one attempt per slot; no automatic retry or substitution', **provenance(ROOT)})
        log.event('prepared', slots=slots, api_expenditure=0)
    finally:
        log.close()
    return log.path


def load_prepared(path):
    path = Path(path).resolve()
    manifest = read(path / 'manifest.json')
    config = Config(**manifest['configuration'])
    if (manifest['version'] != VERSION or len(manifest['slots']) != 6
            or len({s['slot'] for s in manifest['slots']}) != 6
            or manifest['source_manifest_hash'] != provenance(ROOT)['source_manifest_hash']
            or manifest['tools_hash'] != digest(tool_definitions(config))
            or manifest['tools_hash'] != digest(read(path / 'tools.json'))
            or manifest['api_maximum_total_usd'] != '6.00'):
        raise ValueError('Frozen campaign settings, source or schema changed')
    payloads = []
    for slot in manifest['slots']:
        directory = (path / 'slots' / slot['slot']).resolve()
        if not directory.is_relative_to(path):
            raise ValueError('Slot path outside campaign')
        payload = read(directory / 'payload.json')
        public_episode = type('PublicEpisode', (), {'environment': Audit(payload['study'], budget=32)})()
        if (digest(payload) != slot['payload_hash'] or digest(prompts(config, public_episode)) != slot['prompt_hash']
                or digest(read(directory / 'prompts.json')) != slot['prompt_hash']):
            raise ValueError('Frozen case or prompt changed')
        payloads.append(payload)
    return manifest, config, payloads


def mark_attempt(path, data):
    """Exclusive durable slot marker precedes any possibly billed request."""
    import os
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(json_text(data) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


async def run(prepared, mode, gateway_factory=None):
    if mode not in ('dry-run', 'live'):
        raise ValueError('Explicit dry-run or live required')
    prepared = Path(prepared).resolve()
    frozen, config, payloads = load_prepared(prepared)
    if mode == 'live':
        mark_attempt(prepared / 'live-attempt.json', {'started': utc_now(), 'maximum_usd': '6.00',
                     'policy': 'six slots, $1 each; no automatic repeats; failed slots remain attempts'})
    log, results = RunLog(prepared / 'campaigns', mode), []
    try:
        log.write_json('manifest.json', {**frozen, 'mode': mode, 'prepared': str(prepared)})
        for slot, payload in zip(frozen['slots'], payloads):
            marker = {'slot': slot['slot'], 'started': utc_now(), 'ceiling_usd': '1.00'}
            log.write_json(f'states/{slot["slot"]}-attempt.json', marker)
            log.event('slot_started', **marker)
            print(f"Starting {mode} study {slot['slot']}", flush=True)
            gateway = gateway_factory() if gateway_factory else None
            path, reason = await run_episode(ROOT, log.path / 'episodes', mode=mode, config=config,
                instance=Instance(**payload), adapter=Adapter, gateway=gateway)
            data = read(path / 'evaluation.json')
            result = {'slot': slot['slot'], 'case_id': slot['case_id'], 'path': str(path), **data}
            results.append(result)
            log.write_json(f'states/{slot["slot"]}-result.json', result)
            log.event('slot_finished', slot=slot['slot'], path=str(path), termination=reason)
            r = data['evaluation']
            print(f"Finished {slot['slot']}: {reason}; correct={r['correct']} wrong={r['wrong']} "
                  f"abstain={r['abstained']} credits={r['scientific_status']['spent']}", flush=True)
            # Expected episode limits are retained while untouched slots proceed.
            # Infrastructure/accounting failures need inspection, not more calls.
            expected = {'submitted', 'api_ceiling', 'deadline', 'response_limit', 'tool_request_limit',
                        'no_submission', 'model_output_incomplete', 'refusal'}
            if reason not in expected:
                log.event('campaign_halted', reason=reason)
                break
    finally:
        log.write_json('results.json', results)
        log.close()
        render_campaign(log.path)
    return log.path


def render_campaign(path):
    path = Path(path).resolve()
    manifest, results = read(path / 'manifest.json'), read(path / 'results.json')
    rows = [r['evaluation'] for r in results]
    summary = {k: sum(r[k] for r in rows) for k in ('correct', 'wrong', 'abstained', 'utility')}
    summary.update(attempted=len(results), planned=6, incomplete=sum(not r['completed'] for r in rows),
        not_completed_or_not_started=6-sum(r['completed'] for r in rows),
        credits=sum(r['scientific_status']['spent'] for r in rows),
        api_committed_upper_usd=str(sum((Decimal(r['api_budget']['committed_upper_usd']) for r in results), Decimal(0))),
        api_actual_offline_expenditure_usd=0 if manifest['mode'] == 'dry-run' else None)
    _write(path / 'summary.json', json_text(summary) + '\n')
    lines = ['# Luna/high: frozen follow-up claim audit', '',
             f"Mode: {manifest['mode']}. Six engineered development studies; 32 credits each; no forced acquisitions.", '',
             'Utility = correct - 2 * wrong; abstention = 0. Raw outcomes are retained.', '',
             '| Study | Correct / 6 | Wrong | Abstain | Utility | Credits | Status | Transcript |',
             '|---|---:|---:|---:|---:|---:|---|---|']
    for row in results:
        r = row['evaluation']
        relative = Path(row['path']).relative_to(path).as_posix()
        lines.append(f"| {row['slot']} | {r['correct']} | {r['wrong']} | {r['abstained']} | {r['utility']} | "
                     f"{r['scientific_status']['spent']} | {row['termination_reason']} | [trace]({relative}/transcript.md) |")
    lines += ['', '## Aggregate', '', '```json', json_text(summary), '```', '',
              '## Imported CPU comparisons (same attempted studies)', '',
              '| Method | Correct | Wrong | Abstain | Utility | Mean credits |', '|---|---:|---:|---:|---:|---:|']
    for method in COMPARISONS:
        cpu = [r['fixed_policy'][method] for r in results]
        totals = [sum(r[k] for r in cpu) for k in ('correct', 'wrong', 'abstained', 'utility')]
        mean = sum(r['scientific_status']['spent'] for r in cpu) / max(1, len(cpu))
        lines.append('| ' + method + ' | ' + ' | '.join(map(str, totals)) + f' | {mean:.2f} |')
    lines += ['', 'CPU snapshots are imported unchanged, not rerun. Their paid 9-credit initialization and '
              'restricted two-fit estimator are not imposed on Luna. Pair partners share reports and initial evidence; '
              'these are not six independent randomly sampled systems. One episode per study cannot establish '
              'general superiority or a causal planning advantage. Raw logs retain all available API-visible '
              'material, not hidden internal reasoning. No live retry/resume is implemented by this adapter.', '']
    _write(path / 'report.md', '\n'.join(lines))
    return path / 'report.md'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'dry-run', 'live', 'render', 'render-episode'))
    parser.add_argument('directory', nargs='?')
    args = parser.parse_args()
    if args.command == 'prepare':
        print(prepare())
    elif not args.directory:
        parser.error('directory required')
    elif args.command == 'render':
        print(render_campaign(args.directory))
    elif args.command == 'render-episode':
        print(regenerate(args.directory))
    else:
        print(asyncio.run(run(args.directory, args.command)))


if __name__ == '__main__':
    main()
