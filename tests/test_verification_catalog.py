"""No-API tests of the catalog wrapper and aggregate accounting."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from budgeted_science.agents.records import digest
from budgeted_science.agents.verification_catalog import read_catalog, render, run_catalog, summarize
from budgeted_science.agents.verification_fake import VerificationGateway
from test_claim_verification import examples


class CatalogTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_independent_slots_offline_and_regeneration(self):
        studies = [deepcopy(s) for s in examples()[:2]]
        with tempfile.TemporaryDirectory() as folder:
            with patch('budgeted_science.agents.verification_catalog.read_catalog', return_value=(studies, 'fixture')), patch('budgeted_science.agents.runner.load_api_key', side_effect=AssertionError('credentials read')):
                path = await run_catalog('fixture', folder, mode='dry-run')
            result = render(path)
            self.assertEqual(result['overall']['attempts'], 2)
            self.assertEqual(result['overall']['audit_credits'], 10)
            self.assertEqual(result['overall']['baseline_correct'], 2)
            self.assertEqual(len(list((path/'slots').glob('*.json'))), 2)
            self.assertEqual(len(list(Path(folder).glob('*-dry-run-*/evaluation.json'))), 2)
            before = (path/'report.md').read_bytes()
            with patch('budgeted_science.agents.runner.run_episode', side_effect=AssertionError('replay')):
                self.assertEqual(render(path), result)
            self.assertEqual(before, (path/'report.md').read_bytes())

    async def test_uncertain_attempt_kept_without_retry(self):
        studies = [deepcopy(s) for s in examples()[:2]]
        with tempfile.TemporaryDirectory() as folder:
            with patch('budgeted_science.agents.verification_catalog.read_catalog', return_value=(studies,'fixture')):
                path = await run_catalog('fixture', folder, mode='dry-run',
                    gateway_factory=lambda i: VerificationGateway(fail_turn=1) if i==0 else VerificationGateway())
            result = render(path)['overall']
            self.assertEqual(result['attempts'], 2)
            self.assertEqual(result['incomplete'], 1)
            self.assertGreater(float(result['uncertain_reserved_usd']), 0)
            self.assertEqual(len(list(Path(folder).glob('*-dry-run-*/evaluation.json'))), 2)

    def test_aggregate_abstention_and_incomplete_are_not_correct(self):
        base = dict(claim_valid=True, correct=False, false_accept=False, false_reject=False,
                    covered=False, abstained=False, incomplete=False, spent=0, elapsed_seconds=1,
                    input_tokens=10, output_tokens=2, reasoning_tokens=1, api_upper_usd='0.1',
                    api_lower_usd='0.05', uncertain_reserved_usd='0', baseline_correct=True)
        rows = [{**base, 'correct':True, 'covered':True, 'spent':5},
                {**base, 'abstained':True}, {**base, 'incomplete':True, 'claim_valid':False}]
        result = summarize(rows)
        self.assertEqual((result['attempts'],result['correct'],result['abstained'],result['incomplete']), (3,1,1,1))
        self.assertEqual(result['api_committed_upper_usd'], '0.3')
        self.assertEqual((result['valid_claims'],result['invalid_claims']), (2,1))

    def test_rejects_non_30_catalog_and_live_fake_override(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            (p/'private').mkdir()
            catalog={'complete':True,'studies':[examples()[0]]}
            (p/'private/catalog.json').write_text(json.dumps(catalog))
            (p/'catalog_integrity.json').write_text(json.dumps({'catalog_digest':digest(catalog)}))
            with self.assertRaises(ValueError):
                read_catalog(p)
            with self.assertRaises(ValueError):
                self._asyncioRunner.run(run_catalog(p,p,mode='live',gateway_factory=lambda i: VerificationGateway()))


if __name__ == '__main__':
    unittest.main()
