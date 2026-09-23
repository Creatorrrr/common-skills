"""State and caller-boundary regression tests for consultation_runner."""

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lib import consultation_runner as runner


CALLER_ID = "caller-session-0001"
TARGET_ID = "11111111-2222-3333-4444-555555555555"


class ConsultationRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="consult-runner-test-")
        self.addCleanup(temporary.cleanup)
        self.workdir = Path(temporary.name).resolve()
        environment = patch.dict(os.environ, {
            "CONSULT_CODEX_STATE_DIR": str(self.workdir / "state"),
        })
        environment.start()
        self.addCleanup(environment.stop)

    def scope(self) -> dict[str, object]:
        return runner.scope_for("codex", self.workdir, ("claude", CALLER_ID), "default", False)

    def saved_state(self) -> dict[str, object] | None:
        with runner.StateStore("codex", self.scope()) as store:
            return store.read()

    def save_active(self) -> None:
        with runner.StateStore("codex", self.scope()) as store:
            store.write(runner.make_state(self.scope(), "ACTIVE", TARGET_ID))

    def call_codex(self, *options: str) -> int:
        args = ["-C", str(self.workdir), "--caller-kind", "claude",
                "--caller-session-id", CALLER_ID, *options]
        with patch.object(runner, "nearest_agent", return_value=("claude", 123)), \
             patch("sys.stdin", io.StringIO("")), redirect_stdout(io.StringIO()):
            return runner.main("codex", args)

    def test_missing_binary_keeps_active_mapping(self) -> None:
        self.save_active()
        with patch.object(runner, "resolve_binary",
                          side_effect=runner.ConsultationError("missing", 127)):
            with self.assertRaises(runner.ConsultationError) as caught:
                self.call_codex("question")
        self.assertEqual(caught.exception.code, 127)
        self.assertEqual(self.saved_state()["status"], "ACTIVE")
        self.assertEqual(self.saved_state()["target_id"], TARGET_ID)

    def test_failed_spawn_keeps_active_mapping_even_for_new_session(self) -> None:
        self.save_active()
        with patch.object(runner, "resolve_binary", return_value="/nonexistent/codex"):
            with self.assertRaises(runner.BeforeLaunchError):
                self.call_codex("--new-session", "question")
        self.assertEqual(self.saved_state()["status"], "ACTIVE")
        self.assertEqual(self.saved_state()["target_id"], TARGET_ID)

    def test_uncertain_failure_blocks_until_explicit_new_session(self) -> None:
        self.save_active()
        with patch.object(runner, "resolve_binary", return_value="/mock/codex"), \
             patch.object(runner, "run_provider",
                          side_effect=runner.ConsultationError("target failed", 75)):
            with self.assertRaises(runner.ConsultationError):
                self.call_codex("question")
        self.assertEqual(self.saved_state()["status"], "BLOCKED")
        self.assertEqual(self.saved_state()["target_id"], TARGET_ID)
        with self.assertRaisesRegex(runner.ConsultationError, "state is BLOCKED"):
            self.call_codex("another question")
        new_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        with patch.object(runner, "resolve_binary", return_value="/mock/codex"), \
             patch.object(runner, "run_provider", return_value=(new_id, "ok", "ok")):
            self.assertEqual(self.call_codex("--new-session", "new question"), 0)
        self.assertEqual(self.saved_state()["status"], "ACTIVE")
        self.assertEqual(self.saved_state()["target_id"], new_id)
        self.assertEqual(self.saved_state()["retired_target_id"], TARGET_ID)

    def test_status_reads_inflight_state_while_writer_holds_lock(self) -> None:
        scope = self.scope()
        with runner.StateStore("codex", scope) as store:
            store.write(runner.make_state(scope, "IN_FLIGHT", TARGET_ID))
            output = io.StringIO()
            args = ["-C", str(self.workdir), "--caller-kind", "claude",
                    "--caller-session-id", CALLER_ID, "--status"]
            with patch.object(runner, "nearest_agent", return_value=("claude", 123)), \
                 redirect_stdout(output):
                self.assertEqual(runner.main("codex", args), 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "IN_FLIGHT")

    def test_argument_prompt_never_reads_open_stdin(self) -> None:
        class OpenPipe:
            def isatty(self) -> bool:
                return False

            def read(self) -> str:
                raise AssertionError("argument prompt must not read stdin")

        with patch.object(runner, "nearest_agent", return_value=("claude", 123)), \
             patch.object(runner, "resolve_binary", return_value="/mock/codex"), \
             patch.object(runner, "run_provider", return_value=(TARGET_ID, "ok", "ok")), \
             patch("sys.stdin", OpenPipe()), redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main("codex", ["--one-shot", "question"]), 0)

    def test_antigravity_originator_blocks_when_ancestry_is_unknown(self) -> None:
        with patch.dict(os.environ, {"ANTIGRAVITY_INTERNAL_ORIGINATOR_OVERRIDE": "Antigravity CLI"}), \
             patch.object(runner, "nearest_agent", return_value=(None, None)):
            with self.assertRaises(runner.ConsultationError) as caught:
                runner.main("antigravity", ["--one-shot", "question"])
        self.assertEqual(caught.exception.code, 69)

    def test_child_does_not_inherit_outer_agent_ids(self) -> None:
        markers = {
            "CODEX_THREAD_ID": TARGET_ID,
            "CLAUDE_CODE_SESSION_ID": TARGET_ID,
            "AGY_SESSION_ID": TARGET_ID,
            "ANTIGRAVITY_INTERNAL_ORIGINATOR_OVERRIDE": "Antigravity CLI",
        }
        with patch.dict(os.environ, markers):
            child = runner.child_environment("claude")
        for marker in markers:
            self.assertNotIn(marker, child)


if __name__ == "__main__":
    unittest.main()
