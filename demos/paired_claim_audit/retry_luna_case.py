"""One explicitly authorized fresh retry of Luna's incomplete study 4.

Original campaign records remain immutable. This driver does not resume the
old conversation, rerun CPU comparisons, or automatically repeat an attempt.
"""
import argparse
import asyncio
import hashlib
from pathlib import Path

from budgeted_science.agents import target_three_models as models
from budgeted_science.agents import target_three_claims as task
from budgeted_science.agents.records import RunLog, digest, utc_now
from budgeted_science.agents.runner import provenance, run_episode

CASE = '255c174d83fd'
GUARD = task.RUNS / 'target-three-luna-case4-authorized-retry-1.json'


def source():
    slots, payloads, previous, imported = models.import_luna()
    chosen = [i for i, slot in enumerate(slots) if slot['case_id'] == CASE]
    if len(chosen) != 1:
        raise ValueError('expected precisely the original study 4')
    index = chosen[0]
    old = next(r for r in previous if r['case_id'] == CASE)
    if old['termination_reason'] != 'no_submission' or old['evaluation']['completed']:
        raise ValueError('retry requires the preserved incomplete original attempt')
    return slots[index], payloads[index], old, previous, imported


async def run(mode):
    if mode not in ('dry-run', 'live'):
        raise ValueError('explicit offline/live mode required')
    slot, payload, old, previous, imported = source()
    config = task.Config()
    public = type('PublicEpisode', (), {'environment': task.Audit(payload['study'])})()
    assert public.environment.status()['spent'] == 0
    assert digest(task.prompts(config, public)) == slot['prompt_hash']
    assert digest(payload) == slot['payload_hash']
    assert digest(task.tool_definitions()) == imported['tools_hash']
    frozen = {'created': utc_now(), 'mode': mode, 'sample_status': 'explicit fresh retry, not replacement',
              'case_id': CASE, 'source_slot': slot, 'original_attempt': old['path'],
              'original_result_hash': digest(old), 'original_campaign': imported,
              'configuration': config.public(), 'new_api_ceiling_usd': '1.00',
              'old_scientific_credits_are_not_refunded': True,
              'old_conversation_not_replayed': True, 'new_episode_count': 1,
              'no_automatic_retry': True, 'no_cpu_execution': True,
              'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              **provenance(task.ROOT)}
    if mode == 'live':
        task.previous.mark_attempt(GUARD, frozen)
    log = RunLog(task.RUNS, 'target-three-luna-case4-retry-' + mode)
    try:
        log.write_json('manifest.json', frozen)
        log.write_json('payload.json', payload)
        log.write_json('original_results.json', previous)
        log.event('explicit_retry_started', original=old['path'], mode=mode)
        print(str(log.path), flush=True)
        path, reason = await run_episode(task.ROOT, log.path / 'episodes', mode=mode,
                                        config=config, instance=task.Instance(**payload), adapter=task.Adapter)
        result = {**slot, 'path': str(path), 'sample_status': 'explicit retry',
                  **task.read(path / 'evaluation.json')}
        log.write_json('retry_result.json', result)
        # The original primary result set is never overwritten or relabelled.
        sensitivity = [result if r['case_id'] == CASE else r for r in previous]
        log.write_json('retry_inclusive_six_case_view.json', {
            'label': 'five original completed episodes plus one authorized retry; not first-attempt performance',
            'original_first_attempt_completion': '5/6', 'total_live_attempts_including_original': 7,
            'results': sensitivity})
        # Check immutable inputs/old results again after execution.
        _, _, unchanged, _, _ = source()
        assert digest(unchanged) == digest(old)
        assert task.read(path / 'prompts.json') == task.prompts(config, public)
        assert task.read(path / 'private/study.json') == payload['study']
        assert result['fixed_policy'] == payload['comparisons']
        log.event('explicit_retry_finished', termination=reason, path=str(path))
        print(f"Retry: {reason}; correct={result['evaluation']['correct']}, "
              f"wrong={result['evaluation']['wrong']}, abstain={result['evaluation']['abstained']}", flush=True)
    finally:
        log.close()
    return log.path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--dry-run', action='store_true')
    group.add_argument('--live', action='store_true')
    args = parser.parse_args()
    print(asyncio.run(run('live' if args.live else 'dry-run')))


if __name__ == '__main__':
    main()
