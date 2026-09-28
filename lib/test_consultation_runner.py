"""State and caller-boundary regression tests for consultation_runner."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
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

# npm installs start through `#!/usr/bin/env node`; this stand-in tells the launcher
# which install's Node ran it, as the real launcher only finds its own platform binary.
FAKE_NODE = """#!/bin/bash
script="$1"
shift
FAKE_NODE_HOME="$(cd "$(dirname "$0")" && pwd -P)" exec /bin/bash "$script" "$@"
"""

# Mirrors Codex CLI 0.142.4, which predates the root --approve-for-me option.
OLD_CODEX = """#!/usr/bin/env node
case " $* " in
  *" --approve-for-me "*) echo "error: unexpected argument '--approve-for-me' found" >&2; exit 2 ;;
  *" --version "*) echo "codex-cli 0.142.4"; exit 0 ;;
esac
exit 0
"""

# Mirrors Codex CLI 0.156.0 installed under another Node.
NEW_CODEX = """#!/usr/bin/env node
here="$(cd "$(dirname "$0")" && pwd -P)"
if [ "${FAKE_NODE_HOME:-}" != "$here" ]; then
  echo "Error: Missing optional dependency @openai/codex-darwin-x64." >&2
  exit 1
fi
case " $* " in
  *" --version "*) echo "codex-cli 0.156.0"; exit 0 ;;
  *" --help "*) echo "Usage: codex exec resume [OPTIONS]"; exit 0 ;;
esac
output=""
previous=""
for argument in "$@"; do
  if [ "$previous" = "-o" ]; then output="$argument"; fi
  previous="$argument"
done
[ -n "$output" ] || exit 64
printf 'answer from %s\\n' "$here" >"$output"
printf '{"type":"thread.started","thread_id":"11111111-2222-3333-4444-555555555555"}\\n'
printf '{"type":"turn.completed"}\\n'
"""


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

    def install_cli(self, name: str, launcher: str) -> Path:
        """Lay out an npm global install: bin/node beside a bin/codex symlink into lib/node_modules."""
        prefix = self.workdir / name
        script = prefix / "lib/node_modules/@openai/codex/bin/codex.js"
        script.parent.mkdir(parents=True)
        (prefix / "bin").mkdir()
        for path, text in ((script, launcher), (prefix / "bin/node", FAKE_NODE)):
            path.write_text(text)
            path.chmod(0o755)
        (prefix / "bin/codex").symlink_to("../lib/node_modules/@openai/codex/bin/codex.js")
        return prefix / "bin/codex"

    def use_codex_installs(self) -> tuple[Path, Path]:
        """Order PATH like the desktop fallback: the old install and its Node come first."""
        old = self.install_cli("v14", OLD_CODEX)
        new = self.install_cli("v22", NEW_CODEX)
        environment = patch.dict(os.environ, {
            "PATH": os.pathsep.join((str(old.parent), str(new.parent), "/usr/bin", "/bin")),
        })
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop("CONSULT_CODEX_BIN", None)
        return old, new

    def test_codex_resolution_skips_cli_without_wrapper_options(self) -> None:
        _old, new = self.use_codex_installs()
        with redirect_stderr(io.StringIO()):
            self.assertEqual(runner.resolve_binary("codex"), str(new))

    def test_codex_resolution_reports_skipped_cli(self) -> None:
        old, _new = self.use_codex_installs()
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            runner.resolve_binary("codex")
        self.assertIn(str(old), stderr.getvalue())
        self.assertIn("0.142.4", stderr.getvalue())

    def test_codex_launch_runs_under_the_cli_install_node(self) -> None:
        _old, new = self.use_codex_installs()
        args = runner.parse_args("codex", ["question"])
        try:
            with redirect_stderr(io.StringIO()):
                identifier, answer, _ = runner.run_provider(
                    "codex", args, str(new), self.workdir, "prompt", None)
        except runner.ConsultationError as exc:
            self.fail(f"codex launch failed: {exc}")
        self.assertEqual(identifier, TARGET_ID)
        self.assertEqual(answer, f"answer from {new.parent}\n")

    def test_incompatible_codex_keeps_active_mapping(self) -> None:
        _old, new = self.use_codex_installs()
        new.unlink()
        self.save_active()
        with redirect_stderr(io.StringIO()), self.assertRaises(runner.ConsultationError) as caught:
            self.call_codex("question")
        self.assertEqual(caught.exception.code, 127)
        self.assertIn("0.142.4", str(caught.exception))
        self.assertEqual(self.saved_state()["status"], "ACTIVE")
        self.assertEqual(self.saved_state()["target_id"], TARGET_ID)

    def test_codex_override_is_checked_without_path_fallback(self) -> None:
        old, _new = self.use_codex_installs()
        with patch.dict(os.environ, {"CONSULT_CODEX_BIN": str(old)}), redirect_stderr(io.StringIO()):
            with self.assertRaises(runner.ConsultationError) as caught:
                runner.resolve_binary("codex")
        self.assertIn("CONSULT_CODEX_BIN", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
