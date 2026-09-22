"""Static handoff/fixture regressions; no model calls and no behavior pass claim."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from test_skill_contracts import contract_blocks

ROOT = Path(__file__).resolve().parents[1]


class VerificationContractTests(unittest.TestCase):
    def test_new_behavior_fixture_definitions_are_complete_and_unexecuted(self):
        data = json.loads((ROOT / "tests/behavioral-verification.json").read_text())
        self.assertEqual(data["evaluation_status"], "not_run")
        self.assertEqual(len(data["cases"]), 16)
        self.assertEqual(len({c["id"] for c in data["cases"]}), 16)
        for case in data["cases"]:
            with self.subTest(id=case["id"]):
                for key in ("mode", "fixture_files", "user_prompt", "must", "must_not"):
                    self.assertTrue(case[key])
                self.assertEqual(case["status"], "not_run")
                for filename in case["fixture_files"]:
                    self.assertFalse(Path(filename).is_absolute())
                    self.assertNotIn("..", Path(filename).parts)

    def test_comparison_semantics_are_in_portable_contract_not_only_reference(self):
        block = contract_blocks()["EXPERIMENT_CONTRACT_IF_NEEDED"]
        for phrase in ("실제 생성된 구성", "후보와 비교군의 실제 차이", "초기 조건", "단일 요인의 효과", "결론 범위 축소"):
            self.assertIn(phrase, block)

    def test_failed_gate_diagnosis_is_not_promotion_or_new_authority(self):
        block = contract_blocks()["EXPERIMENT_CONTRACT_IF_NEEDED"]
        for phrase in ("어떤 결과가 어떤 다음 결정을", "진단 결과로 승격하지", "위임된 범위 안의 진단", "원래 실패를 유지"):
            self.assertIn(phrase, block)

    def test_verifier_and_metric_limits_are_in_portable_handoff(self):
        block = contract_blocks()["EXPERIMENT_CONTRACT_IF_NEEDED"]
        for phrase in ("원시 증거를 먼저", "순차 자기검토", "미수행", "확률 보정만으로", "의미적 정확성의 증명이 아니다"):
            self.assertIn(phrase, block)

    def test_program_carries_unresolved_claims_and_separate_cost_units(self):
        block = contract_blocks()["PROGRAM_CONTRACT_IF_ENABLED"]
        for phrase in ("미해결 핵심 주장", "상속된", "신규 실험 수", "공통 코드를 계속 복제"):
            self.assertIn(phrase, block)

    def test_light_core_does_not_require_empirical_infrastructure(self):
        block = contract_blocks()["CORE_CONTRACT"]
        for word in ("experiment_preflight.py", "schema_version", "독립 검증자 의무", "캐시 비교"):
            self.assertNotIn(word, block)

    def test_review_template_keeps_assessment_before_reconciliation(self):
        content = (ROOT / "assets/verification-template.md").read_text()
        self.assertLess(content.index("Evidence-first assessment"), content.index("Reconciliation"))
        self.assertIn("read-only by default", content)
        self.assertIn("sequential-self-review", content)
        self.assertIn("unresolved disagreements", content)

    def test_existing_templates_capture_new_fields_without_mandatory_new_database(self):
        experiment = (ROOT / "assets/experiment-template.md").read_text()
        state = (ROOT / "assets/research-state-template.md").read_text()
        for phrase in ("Decision fork", "Candidate-minus-comparator", "Changed mechanism", "New work versus inherited"):
            self.assertIn(phrase, experiment)
        for phrase in ("Unresolved mission claims", "Failed gate", "inherited"):
            self.assertIn(phrase, state)


if __name__ == "__main__":
    unittest.main()
