"""Packaging/forwarding regressions only; these are not LLM behavior tests."""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("astra_handoff_builder", ROOT / "scripts/build_handoff.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

class AstraHandoffTests(unittest.TestCase):
    def setUp(self):
        self.blocks = builder.parse_blocks((ROOT / "references/execution-contract.md").read_text())

    def test_small_handoff_forwards_revision_without_loading_api_or_history(self):
        text, stats = builder.compile_handoff("깨진 계획 링크만 수정. 기존 경로와 승인 한도를 유지.", self.blocks, ["Core"])
        self.assertEqual(text.count(self.blocks["Core"]), 1)
        self.assertIn("도중에 요구가 바뀌면", text)
        self.assertIn("가역적 저영향 수정", text)
        for absent in ("configuration_update", "GPT-5.6", "gpt-6-astra", "temperature", "지속 연구 프로그램:"):
            self.assertNotIn(absent, text)
        self.assertFalse(stats["execution_authorized"])
        self.assertEqual(stats["token_count"], "not_measured")

    def test_research_handoff_retains_scope_and_depth_controls(self):
        text, stats = builder.compile_handoff("지정 자료의 두 독립 문제를 검토. 외부 쓰기 금지.", self.blocks, ["Core", "Research"])
        self.assertEqual(stats["selected_blocks"], ["Core", "Research"])
        self.assertEqual(text.count(self.blocks["Research"]), 1)
        self.assertIn("하위 위임 금지", text)
        self.assertIn("공유 예산", text)
        self.assertIn("실패를 성공으로", text)
        self.assertNotIn(self.blocks["Persistence"], text)

    def test_new_core_is_not_silently_truncated_under_prior_cap(self):
        goal = "현재 한정 목표의 기준과 작업 상태를 보존한다."
        text, stats = builder.compile_handoff(goal, self.blocks, ["Core"])
        exact = len(text.encode("utf-8"))
        self.assertEqual(builder.compile_handoff(goal, self.blocks, ["Core"], exact)[0], text)
        with self.assertRaises(builder.HandoffError):
            builder.compile_handoff(goal, self.blocks, ["Core"], exact - 1)
        self.assertEqual(stats["utf8_bytes"], exact)

    def test_prior_source_is_archived_and_current_target_is_explicit(self):
        current = (ROOT / "MODEL_GUIDE_REVIEW.md").read_text()
        old = (ROOT / "MODEL_GUIDE_REVIEW_V3_2.md").read_text()
        metadata = json.loads((ROOT / "tests/evidence/v3.2.1/source-verification.json").read_text())
        self.assertIn("Using GPT-5.6", old)
        self.assertIn("Using GPT-6 Astra", current)
        self.assertEqual(metadata["target_model"], "gpt-6-astra")
        self.assertFalse(metadata["canonical_direct_open"]["used_as_astra_guidance"])
        self.assertFalse(metadata["full_http_snapshot_captured"])
        self.assertIn("model=gpt-6-astra", metadata["requested_url"])

    def test_scenario_definitions_do_not_claim_model_execution(self):
        data = json.loads((ROOT / "tests/behavioral-astra.json").read_text())
        self.assertEqual(data["evaluation_status"], "not_run")
        self.assertEqual(len(data["cases"]), 12)
        self.assertEqual(len({x["id"] for x in data["cases"]}), 12)
        for case in data["cases"]:
            self.assertEqual(case["status"], "not_run")
            for field in ("setup", "user_prompt", "must", "must_not"):
                self.assertTrue(case[field])

if __name__ == "__main__":
    unittest.main()
