"""Static package checks only. These do NOT measure agent behavior."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "references" / "execution-contract.md"


def contract_blocks() -> dict[str, str]:
    """Parse by heading identity, not fragile positional fence ordering."""
    text = CONTRACT.read_text(encoding="utf-8")
    heading_ids = {
        "Core": "CORE_CONTRACT",
        "Program": "PROGRAM_CONTRACT_IF_ENABLED",
        "Experiment": "EXPERIMENT_CONTRACT_IF_NEEDED",
        "Direction": "DIRECTION_CONTRACT_IF_NEEDED",
        "Research": "RESEARCH_CONTRACT_IF_NEEDED",
        "Retrieval": "RETRIEVAL_CONTRACT_IF_NEEDED",
        "Persistence": "PERSISTENCE_CONTRACT_IF_ENABLED",
    }
    found = re.findall(r"^## ([A-Za-z]+)[^\n]*\n+```text\n(.*?)\n```", text, re.MULTILINE | re.DOTALL)
    if len(found) != len(heading_ids) or {name for name, _ in found} != set(heading_ids):
        raise ValueError("Expected seven uniquely named portable contract blocks")
    return {heading_ids[name]: value for name, value in found}


class SkillContractTests(unittest.TestCase):
    def test_frontmatter_identity_and_version(self) -> None:
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        metadata = text.split("---", 2)[1]
        self.assertRegex(metadata, r"(?m)^name: goal-planner$")
        self.assertRegex(metadata, r"(?m)^description: .+")
        self.assertEqual((ROOT / "VERSION").read_text().strip(), "3.0.0")

    def test_markdown_relative_file_links_resolve(self) -> None:
        # Ignore URLs and anchors; links in authored Markdown must reference bundled files.
        for document in ROOT.rglob("*.md"):
            text = document.read_text(encoding="utf-8")
            for target in re.findall(r"\]\(([^)]+)\)", text):
                if re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", target) or target.startswith("#"):
                    continue
                target = target.split("#", 1)[0]
                if not target:
                    continue
                with self.subTest(document=str(document.relative_to(ROOT)), target=target):
                    self.assertTrue((document.parent / target).is_file(), target)

    def test_contract_and_templates_have_matching_insertion_markers(self) -> None:
        blocks = contract_blocks()
        for name in ("references/runtime-prompts.md", "assets/goal-plan-template.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertEqual(set(re.findall(r"\{\{([A-Z_]+)\}\}", text)), set(blocks))

    def test_selected_contracts_render_without_unselected_rules(self) -> None:
        blocks = contract_blocks()
        profiles = {
            "self_contained": {"CORE_CONTRACT"},
            "research_without_repository": {"CORE_CONTRACT", "RESEARCH_CONTRACT_IF_NEEDED"},
            "read_only_improvement": set(blocks) - {"PERSISTENCE_CONTRACT_IF_ENABLED", "PROGRAM_CONTRACT_IF_ENABLED"},
            "finite_persistence": set(blocks) - {"PROGRAM_CONTRACT_IF_ENABLED"},
            "program_read_only": set(blocks) - {"PERSISTENCE_CONTRACT_IF_ENABLED"},
            "program_persistence": set(blocks),
            "finite_experiment": {"CORE_CONTRACT", "EXPERIMENT_CONTRACT_IF_NEEDED"},
        }
        for name in ("assets/goal-plan-template.md", "references/runtime-prompts.md"):
            original = (ROOT / name).read_text(encoding="utf-8")
            for profile, selected in profiles.items():
                with self.subTest(template=name, profile=profile):
                    rendered = original
                    for marker, value in blocks.items():
                        rendered = rendered.replace("{{" + marker + "}}",
                                                    value if marker in selected else "")
                    self.assertNotRegex(rendered, r"\{\{[A-Z_]+\}\}")
                    for marker, value in blocks.items():
                        self.assertEqual(rendered.count(value), 1 if marker in selected else 0)

    def test_persistence_contract_retains_closed_success_qualifications(self) -> None:
        block = contract_blocks()["PERSISTENCE_CONTRACT_IF_ENABLED"]
        for phrase in ("모든 최종 기준", "중요한 실패", "기본/문서화된 접근",
                       "필수 다단계 재현 절차", "최대 1건", "양방향"):
            self.assertIn(phrase, block)
        reference = (ROOT / "references/execution-knowledge.md").read_text(encoding="utf-8")
        for identifier in ("resolved-material-failure", "non-obvious-after-default-failed",
                           "required-reproduction-procedure"):
            self.assertIn(identifier, reference)

    def test_known_conflicting_runtime_phrases_are_not_reintroduced(self) -> None:
        names = ("SKILL.md", "references/runtime-prompts.md", "references/execution-contract.md")
        forbidden = ("검증-only 작업을 두 번 연속 수행하지 않는다",
                     "최종 검증을 한 번 수행한다",
                     "Treat GOAL_PLAN.md as the authoritative",
                     "Keep the complete Claude Code `/goal` condition under 4,000")
        for name in names:
            text = (ROOT / name).read_text(encoding="utf-8")
            for phrase in forbidden:
                with self.subTest(file=name, phrase=phrase):
                    self.assertNotIn(phrase, text)

    def test_behavioral_scenarios_are_explicitly_unexecuted(self) -> None:
        data = json.loads((ROOT / "tests/behavioral-scenarios.json").read_text(encoding="utf-8"))
        self.assertEqual(data["evaluation_status"], "not_run")
        ids = [case["id"] for case in data["cases"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 64)
        for case in data["cases"]:
            for field in ("id", "mode", "setup", "user_prompt", "must", "must_not"):
                self.assertTrue(case[field], (case["id"], field))
            self.assertEqual(case["status"], "not_run")

    def test_no_bytecode_or_macos_artifacts_in_package(self) -> None:
        for path in ROOT.rglob("*"):
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertNotIn(path.name, ("__MACOSX", ".DS_Store", "__pycache__"))
                self.assertFalse(path.name.startswith("._"))
                self.assertNotEqual(path.suffix, ".pyc")


if __name__ == "__main__":
    unittest.main()
