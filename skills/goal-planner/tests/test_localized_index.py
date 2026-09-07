"""Actual parser/CLI regressions; these are not tests of model behavior."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/report_index.py'
SPEC = importlib.util.spec_from_file_location('localized_report_index', SCRIPT)
assert SPEC is not None and SPEC.loader is not None
index = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = index
SPEC.loader.exec_module(index)


def entry(text: str, kind: str = 'failed', name: str = 'case.md') -> dict:
    path = f'docs/{kind}-reports/{name}'
    return index.build_entry(index.ReportDocument(kind, path, text, index.sha256_bytes(text.encode())))


class LocalizedIndexTests(unittest.TestCase):
    def test_canonical_keys_with_korean_values(self):
        value = entry('# 결과\n- Status: open\n- Problem signature: 공간 추정\n- Related paths: src/추정.py\n')
        self.assertEqual(value['status'], 'open')
        self.assertEqual(value['routing']['problem_signature'], '공간 추정')
        self.assertFalse(value['sparse'])

    def test_korean_routing_labels(self):
        value = entry('# 결과\n- 상태: 미해결\n- 문제 서명: 위치 추정\n- 기록 시각: 2026-09-07 19:00 KST\n- 환경/버전: Python 3\n- 관련 경로: src/model.py\n')
        self.assertEqual(value['status'], 'open')
        self.assertEqual(value['recorded'], '2026-09-07 19:00 KST')
        self.assertEqual(value['routing']['environment_versions'], 'Python 3')
        self.assertEqual(value['routing']['related_paths'], 'src/model.py')
        self.assertFalse(value['sparse'])

    def test_bold_and_casefold_labels(self):
        value = entry('# 결과\n- **상태**: 해결됨\n- **Problem Signature**: X\n')
        self.assertEqual(value['status'], 'resolved')
        self.assertEqual(value['routing']['problem_signature'], 'X')

    def test_localized_status_values(self):
        for given, expected in index.STATUS_ALIASES.items():
            with self.subTest(status=given):
                self.assertEqual(entry(f'# X\n- Status: {given}\n- Problem signature: X\n')['status'], expected)

    def test_equivalent_duplicate_statuses_are_not_conflicts(self):
        value = entry('# X\n- Status: OPEN\n- 상태: 미해결\n- Problem signature: X\n- 문제 서명: X\n')
        self.assertEqual(value['status'], 'open')
        self.assertNotIn('field_conflicts', value)

    def test_conflicting_status_aliases_are_errors(self):
        value = entry('# X\n- Status: active\n- 상태: 해결됨\n- Problem signature: X\n')
        self.assertEqual(value['status'], 'unknown')
        errors, _ = index.validate_lifecycle([value])
        self.assertTrue(any('Conflicting Status' in e for e in errors))

    def test_conflicting_signature_aliases_are_not_arbitrarily_selected(self):
        value = entry('# X\n- Status: open\n- Problem signature: A\n- 문제 서명: B\n')
        self.assertTrue(value['sparse'])
        self.assertNotIn('problem_signature', value.get('routing', {}))
        self.assertTrue(index.validate_lifecycle([value])[0])

    def test_unknown_labels_remain_sparse_with_warnings(self):
        value = entry('# X\n- état: open\n- identifiant du problème: XYZ\n')
        self.assertTrue(value['sparse'])
        self.assertEqual(value['status'], 'unknown')
        _, warnings = index.validate_lifecycle([value])
        self.assertTrue(any('Missing recognized Status' in w for w in warnings))
        self.assertTrue(any('Problem signature' in w for w in warnings))

    def test_unknown_status_does_not_become_active(self):
        value = entry('# X\n- Status: confirmed scientific truth\n- Problem signature: X\n')
        self.assertEqual(value['status'], 'unknown')
        self.assertTrue(value['sparse'])
        self.assertIn('Unrecognized Status', value['extraction_warnings'][0])

    def test_localized_lifecycle_links_are_validated(self):
        old = entry('# old\n- 상태: 대체됨\n- 문제 서명: X\n- 후속 보고서: new.md\n', name='old.md')
        new = entry('# new\n- 상태: 미해결\n- 문제 서명: X\n- 대체한 보고서: old.md\n', name='new.md')
        self.assertEqual(old['links']['superseded_by'], ['docs/failed-reports/new.md'])
        self.assertEqual(index.validate_lifecycle([old, new])[0], [])

    def test_localized_tables_and_observations(self):
        value = entry('# X\n- Status: open\n- Problem signature: X\n\n## 실패\n- 예상: A\n- 관측: B\n\n## 시도\n| Attempt | Result |\n|---|---|\n| v1 | failed |\n')
        self.assertEqual(value['capsule']['expected'], 'A')
        self.assertEqual(value['capsule']['observed'], 'B')
        self.assertEqual(value['capsule']['failed_attempts'][0]['attempt'], 'v1')

    def test_cli_roundtrip_and_read_only_query(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / 'docs/failed-reports/case.md'
            report.parent.mkdir(parents=True)
            report.write_text('# 한글\n- 상태: 미해결\n- 문제 서명: 한국어-SENTINEL\n', encoding='utf-8')
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
            def cli(command, *args):
                return subprocess.run([sys.executable, '-B', str(SCRIPT), command, '--root', directory, *args], capture_output=True, check=False, timeout=30, env=env)
            self.assertEqual(cli('sync').returncode, 0)
            self.assertEqual(cli('check').returncode, 0)
            before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            result = cli('query', '한국어-SENTINEL')
            self.assertEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertEqual(payload['catalog_status'], 'current')
            self.assertEqual(payload['results'][0]['status'], 'open')
            self.assertEqual(before, {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_cli_conflicting_fields_fail_check_but_preserve_search(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / 'docs/failed-reports/case.md'
            report.parent.mkdir(parents=True)
            report.write_text('# X\n- Status: open\n- 상태: 해결됨\n- Problem signature: CONFLICT\n', encoding='utf-8')
            def cli(command, *args):
                return subprocess.run([sys.executable, '-B', str(SCRIPT), command, '--root', directory, *args], capture_output=True, check=False, timeout=30, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
            self.assertEqual(cli('sync').returncode, 0)
            checked = cli('check')
            self.assertEqual(checked.returncode, 1)
            self.assertFalse(json.loads(checked.stdout)['ok'])
            queried = json.loads(cli('query', 'CONFLICT').stdout)
            self.assertEqual(queried['catalog_status'], 'invalid-lifecycle-fallback')
            self.assertEqual(queried['results'][0]['status'], 'unknown')

if __name__ == '__main__':
    unittest.main()
