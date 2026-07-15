from __future__ import annotations

import argparse
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import analysis_contract  # noqa: E402
import prepare_analysis_context  # noqa: E402
import run_chatgpt_web_assisted  # noqa: E402
import run_gpt_pro_analysis  # noqa: E402


class PromptContractTests(unittest.TestCase):
    def test_gpt_56_sol_pro_defaults(self) -> None:
        parser = run_gpt_pro_analysis.build_parser()
        args = parser.parse_args(["--manifest", "manifest.json"])

        self.assertEqual(args.model, "gpt-5.6-sol")
        self.assertEqual(args.reasoning_mode, "pro")
        self.assertEqual(args.reasoning_effort, "high")
        self.assertEqual(
            run_gpt_pro_analysis.build_reasoning_config(args),
            {"mode": "pro", "effort": "high"},
        )

    def test_pro_rejects_effort_below_medium(self) -> None:
        args = argparse.Namespace(
            reasoning_mode="pro",
            reasoning_effort="low",
            reasoning_context="auto",
        )

        with self.assertRaisesRegex(ValueError, "medium or higher"):
            run_gpt_pro_analysis.build_reasoning_config(args)

    def test_explicit_reasoning_context_is_sent(self) -> None:
        args = argparse.Namespace(
            reasoning_mode="pro",
            reasoning_effort="medium",
            reasoning_context="all_turns",
        )

        self.assertEqual(
            run_gpt_pro_analysis.build_reasoning_config(args),
            {"mode": "pro", "effort": "medium", "context": "all_turns"},
        )

    def test_goal_appears_once_and_prompt_has_no_template_indentation(self) -> None:
        goal = "Review checkout correctness and test gaps"
        instructions = run_gpt_pro_analysis.build_instructions()
        user_prompt = run_gpt_pro_analysis.build_user_prompt(
            goal,
            "direct",
            ["first warning", "second warning"],
            "direct",
            {
                "scope": ["src/checkout"],
                "stats": {"included_file_count": 12, "focused_file_count": 7},
            },
        )
        combined = f"{instructions}\n{user_prompt}"

        self.assertEqual(combined.count(goal), 1)
        self.assertFalse(any(line.startswith("        ") for line in combined.splitlines()))
        self.assertIn("severity, confidence, claim, evidence, impact, recommendation, validation", instructions)

    def test_report_contract_is_compact(self) -> None:
        self.assertEqual(
            analysis_contract.REQUIRED_OUTPUT_SECTIONS,
            [
                "Verdict",
                "Scope and coverage",
                "Prioritized findings",
                "Unknowns and missing context",
                "Recommended actions",
            ],
        )

    def test_chatgpt_handoff_prompt_uses_the_same_compact_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "upload-source.zip"
            prompt_path = root / "chatgpt-prompt.txt"
            request_meta_path = root / "request_meta.json"
            archive.write_bytes(b"zip")
            selection = run_chatgpt_web_assisted.Selection(
                key="full",
                label="full repository archive",
                archive_path=archive,
                generated_archive=False,
                file_count=10,
                estimated_bytes=1000,
                estimated_tokens=250,
                invalid_reasons=[],
            )
            identity = run_chatgpt_web_assisted.HandoffIdentity(
                run_id="run-1",
                goal="Review checkout correctness",
                handoff_dir=root,
                upload_zip_path=archive,
                upload_zip_sha256="abc",
                attachment_path=archive,
                attachment_sha256="abc",
                computer_use_handoff=False,
                accessible_upload_copy_path=None,
                accessible_upload_copy_sha256=None,
                prompt_path=prompt_path,
                request_meta_path=request_meta_path,
            )

            prompt = run_chatgpt_web_assisted.build_prompt(
                {"scope": ["src/checkout"], "mode_recommendation": "direct"},
                "Review checkout correctness",
                selection,
                [],
                [],
                handoff_identity=identity,
            )

            self.assertFalse(any(line.startswith("        ") for line in prompt.splitlines()))
            self.assertEqual(prompt.count("Review checkout correctness"), 1)
            self.assertIn("severity, confidence, claim, evidence, impact, recommendation, validation", prompt)
            self.assertIn("1. Verdict", prompt)
            self.assertNotIn("Do not reveal chain-of-thought", prompt)


class DirectContextTests(unittest.TestCase):
    def test_prepare_run_writes_lossless_full_context_shards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            source = root / "large.py"
            source_text = "value = '" + ("x" * 500_000) + "'\n"
            source.write_text(source_text, encoding="utf-8")
            out_dir = root / ".codex-analysis" / "context"

            argv = [
                "prepare_analysis_context.py",
                "--root",
                str(root),
                "--goal",
                "Review large source handling",
                "--out-dir",
                str(out_dir),
                "--skip-archives",
            ]
            with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
                result = prepare_analysis_context.main()

            self.assertEqual(result, 0)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            shard_paths = [Path(path) for path in manifest["artifacts"]["full_context_shards"]]
            combined = "\n".join(path.read_text(encoding="utf-8") for path in shard_paths)
            record = next(item for item in manifest["files"] if item["path"] == "large.py")

            self.assertIn(source_text, combined)
            self.assertFalse(record["inline_truncated"])

    def test_direct_mode_prefers_lossless_context_shards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_tree = root / "repo_tree.txt"
            selection_report = root / "selection-report.md"
            shard_one = root / "full-context-001.md"
            shard_two = root / "full-context-002.md"
            raw_file = root / "raw.py"
            for path, content in [
                (repo_tree, "raw.py\n"),
                (selection_report, "selection ok\n"),
                (shard_one, "first shard\n"),
                (shard_two, "second shard\n"),
                (raw_file, "print('raw')\n"),
            ]:
                path.write_text(content, encoding="utf-8")

            manifest = {
                "artifacts": {
                    "repo_tree": str(repo_tree),
                    "selection_report": str(selection_report),
                    "full_context_shards": [str(shard_one), str(shard_two)],
                },
                "selections": {"full_files": ["raw.py"]},
            }

            selected = run_gpt_pro_analysis.select_direct_input_files(manifest, root)
            logical_paths = [item["logical_path"] for item in selected]

            self.assertEqual(len(selected), 4)
            self.assertNotIn("raw.py", logical_paths)
            self.assertIn("__analysis_context__/full-context-001.md", logical_paths)
            self.assertIn("__analysis_context__/full-context-002.md", logical_paths)

    def test_direct_mode_fails_instead_of_truncating_required_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = []
            for index in range(3):
                path = root / f"shard-{index}.md"
                path.write_text(f"shard {index}\n", encoding="utf-8")
                paths.append(str(path))

            manifest = {
                "artifacts": {"full_context_shards": paths},
                "selections": {"full_files": ["unused.py"]},
            }

            with self.assertRaisesRegex(ValueError, "more than 2 input files"):
                run_gpt_pro_analysis.select_direct_input_files(manifest, root, max_files=2)

    def test_direct_mode_rejects_shards_from_an_older_lossy_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shard = root / "full-context-001.md"
            shard.write_text("partial old shard\n", encoding="utf-8")
            manifest = {
                "artifacts": {"full_context_shards": [str(shard)]},
                "selections": {"full_files": ["large.py"]},
                "files": [{"path": "large.py", "inline_truncated": True}],
            }

            with self.assertRaisesRegex(ValueError, "shards are lossy"):
                run_gpt_pro_analysis.select_direct_input_files(manifest, root)

    def test_prepared_file_blocks_are_lossless(self) -> None:
        source = "line one\n" + ("x" * 500_000) + "\nline last"
        block = prepare_analysis_context.render_file_block("large.txt", "source", "text", source)

        self.assertIn(source, block)
        self.assertNotIn("TRUNCATED FOR DIRECT MODE", block)


class RuntimeSafetyTests(unittest.TestCase):
    def test_pro_polling_uses_mode_not_model_slug(self) -> None:
        initial = SimpleNamespace(status="in_progress", id="resp_1")
        completed = SimpleNamespace(status="completed", id="resp_1")
        client = SimpleNamespace(responses=SimpleNamespace(retrieve=mock.Mock(return_value=completed)))

        with (
            mock.patch.object(run_gpt_pro_analysis, "monotonic", side_effect=[0, 1]),
            mock.patch.object(run_gpt_pro_analysis, "sleep") as sleep_mock,
        ):
            result = run_gpt_pro_analysis.poll_response(client, initial, 5, "pro")

        self.assertIs(result, completed)
        sleep_mock.assert_called_once_with(60)

    def test_only_completed_nonempty_output_is_success(self) -> None:
        for status in ["failed", "cancelled", "incomplete", None]:
            with self.subTest(status=status):
                output, reason = run_gpt_pro_analysis.completed_output_text(
                    SimpleNamespace(status=status, output_text="partial")
                )
                self.assertIsNone(output)
                self.assertTrue(reason)

        output, reason = run_gpt_pro_analysis.completed_output_text(
            SimpleNamespace(status="completed", output_text="   ")
        )
        self.assertIsNone(output)
        self.assertEqual(reason, "completed_response_missing_output_text")

        output, reason = run_gpt_pro_analysis.completed_output_text(
            SimpleNamespace(status="completed", output_text="report")
        )
        self.assertEqual(output, "report")
        self.assertIsNone(reason)

    def test_vector_store_ingestion_failure_is_not_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.py"
            source.write_text("print('hello')\n", encoding="utf-8")

            sdk_files = SimpleNamespace(create=mock.Mock(return_value=SimpleNamespace(id="file_1")))
            vector_files = SimpleNamespace(
                create=mock.Mock(),
                retrieve=mock.Mock(return_value=SimpleNamespace(status="failed")),
            )
            client = SimpleNamespace(
                files=sdk_files,
                vector_stores=SimpleNamespace(
                    create=mock.Mock(return_value=SimpleNamespace(id="vs_1")),
                    files=vector_files,
                ),
            )

            with self.assertRaisesRegex(RuntimeError, "refusing a partial analysis"):
                run_gpt_pro_analysis.upload_vector_store_files(
                    client,
                    "test-store",
                    root,
                    ["source.py"],
                )


if __name__ == "__main__":
    unittest.main()
