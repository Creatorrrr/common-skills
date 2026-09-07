"""Contract coverage and handoff consistency, NOT autonomous research evaluation."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from test_skill_contracts import contract_blocks

ROOT = Path(__file__).resolve().parents[1]


class ResearchContractTests(unittest.TestCase):
    def test_exact_named_blocks_have_no_duplicate_fences(self):
        blocks = contract_blocks()
        self.assertEqual(len(blocks), 7)
        self.assertTrue(all(block.strip() for block in blocks.values()))

    def test_core_scopes_succession_exception(self):
        core = contract_blocks()['CORE_CONTRACT']
        self.assertIn('finite-goal', core)
        self.assertIn('research-program', core)
        self.assertIn('위임된 범위 밖의 새로운 결과', core)
        self.assertIn('실패를 성공으로', core)

    def test_program_preserves_budget_and_current_state(self):
        program = contract_blocks()['PROGRAM_CONTRACT_IF_ENABLED']
        for phrase in ('다음 이정표', '진행 중 예약', '예산을 초기화하지', '재개 시 실제 파일',
                       '가장 좋은 검증된 산출물', '중단 요청 후 새 연구', 'completed'):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, program)

    def test_experiment_judgments_and_feasibility_exception_are_embedded(self):
        block = contract_blocks()['EXPERIMENT_CONTRACT_IF_NEEDED']
        for phrase in ('valid/invalid/pending', 'supported/refuted/inconclusive/not_tested',
                       'adopt/reject/defer/not_applicable', 'pending/pass/fail/blocked/not_run',
                       '자원 한도 내 실행 가능성', '그 한정된 가능성을 반증', '같은 버전으로 재비교'):
            self.assertIn(phrase, block)

    def test_no_numeric_budget_is_invented_as_prerequisite(self):
        program = contract_blocks()['PROGRAM_CONTRACT_IF_ENABLED']
        self.assertIn('수치가 없으면', program)
        self.assertIn('이미 허용된 가역적 작업은 진행', program)
        self.assertIn('미확인 비용을 0이나 무제한으로', program)

    def test_delegation_constraints_and_successor_transfer(self):
        block = contract_blocks()['RESEARCH_CONTRACT_IF_NEEDED']
        self.assertIn('하위 위임 금지', block)
        self.assertIn('후속 이정표에도 필요한 작업', block)
        self.assertIn('예산을 새로 부여하지', block)

    def test_success_is_scoped_to_milestone_not_program(self):
        block = contract_blocks()['PERSISTENCE_CONTRACT_IF_ENABLED']
        self.assertIn('판정 대상 이정표의 모든 최종 기준', block)
        self.assertIn('프로그램이 계속 중이어도', block)
        self.assertIn('성공 보고서와 별도인 실험 기록', block)

    def test_templates_capture_pre_and_post_run_fields(self):
        text = (ROOT/'assets/experiment-template.md').read_text()
        self.assertLess(text.index('Before execution'), text.index('After execution'))
        for key in ('Experiment ID', 'Hypothesis ID', 'Predictions', 'Validity', 'Hypothesis verdict',
                    'Adoption', 'Milestone outcome', 'Amendments'):
            self.assertIn(key, text)

    def test_resume_template_distinguishes_accounting_and_ownership(self):
        text = (ROOT/'assets/research-state-template.md').read_text()
        for key in ('Actual used', 'In-flight reserved', 'Remaining/unknown', 'Task ID / owner',
                    'Best verified artifact', 'Evaluation exposure', 'Already completed work not to repeat'):
            self.assertIn(key, text)

    def test_research_and_experiment_records_stay_outside_report_catalog(self):
        text = (ROOT/'scripts/report_index.py').read_text()
        self.assertNotIn('"research": PurePosixPath', text)
        ref = (ROOT/'references/experiment-protocol.md').read_text()
        self.assertIn('outside the execution-report catalog', ref)

    def test_new_behavior_definitions_are_not_reported_as_executions(self):
        data = json.loads((ROOT/'tests/behavioral-scenarios.json').read_text())
        new = [case for case in data['cases'] if int(case['id'][1:]) >= 45]
        self.assertEqual(len(new), 20)
        self.assertTrue(all(case['status']=='not_run' for case in new))

    def test_no_unconditional_successor_stop_in_active_references(self):
        # Regression for specific formerly-unconditional clauses; not a general semantic proof.
        for name in ('references/execution-contract.md','references/execution-knowledge.md',
                     'assets/research-readme.md'):
            text = (ROOT/name).read_text()
            self.assertNotIn('완료 뒤 새 목표를 자동 생성하는 권한은 부여하지 않는다.', text)
            self.assertNotIn('Do not start or reopen a goal automatically from a research suggestion.', text)

if __name__ == '__main__':
    unittest.main()
