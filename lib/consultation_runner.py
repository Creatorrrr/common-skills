#!/usr/bin/env python3
"""Session-safe non-interactive consultations for the three CLI skills."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid


SCHEMA = 2
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$")
CALLER_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{8,256}$")
ARTIFACT_RE = re.compile(
    r"(wrote|written|created|saved).*(plan|report|markdown|file)"
    r"|계획.*파일|파일.*작성|작성.*파일|saved at|written to",
    re.IGNORECASE,
)


class ConsultationError(Exception):
    def __init__(self, message: str, code: int = 70):
        super().__init__(message)
        self.code = code


class BeforeLaunchError(ConsultationError):
    """The target CLI definitely did not start, so prior state remains valid."""


def warn(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def is_uuid(value: object) -> bool:
    return isinstance(value, str) and UUID_RE.fullmatch(value) is not None


def parse_args(provider: str, argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog={"claude": "consult_claude_code.sh",
              "antigravity": "consult_antigravity_cli.sh",
              "codex": "consult_codex_cli.sh"}[provider],
        description="Consult another local agent; continue only within a verified caller session.",
        allow_abbrev=False,
    )
    parser.add_argument("-C", "--cd", "--workdir", dest="workdir")
    parser.add_argument("-m", "--model")
    parser.add_argument("--caller-kind", choices=("codex", "claude", "antigravity", "other"))
    parser.add_argument("--caller-session-id")
    parser.add_argument("--chain", metavar="NAME")
    parser.add_argument("--shared-chain", metavar="NAME")
    parser.add_argument("--reset-chain", metavar="NAME")
    parser.add_argument("--reset-shared-chain", metavar="NAME")
    parser.add_argument("--reset-session", action="store_true")
    parser.add_argument("--new-session", action="store_true")
    parser.add_argument("--one-shot", action="store_true")
    parser.add_argument("--status", action="store_true")
    if provider in ("claude", "antigravity"):
        parser.add_argument("--auth-smoke", "--auth-check", action="store_true")
        parser.add_argument("-o", "--output-format", choices=("text", "json", "stream-json"))
        parser.add_argument("--permission-mode")
    if provider == "claude":
        parser.add_argument("--effort", choices=("low", "medium", "high", "xhigh", "max"))
        parser.add_argument("--add-dir", action="append", default=[])
    elif provider == "antigravity":
        parser.add_argument("--approval-mode")
        parser.add_argument("--sandbox", "-s", action="store_true")
        parser.add_argument("--dangerously-skip-permissions", "--yolo", action="store_true")
        parser.add_argument("--no-dangerously-skip-permissions", "--request-review", "--ask", action="store_true")
        parser.add_argument("--print-timeout")
    else:
        parser.add_argument("--effort", "--reasoning-effort")
        speed = parser.add_mutually_exclusive_group()
        speed.add_argument("--fast", action="store_true")
        speed.add_argument("--standard", action="store_true")
    parser.add_argument("request", nargs="*")
    return parser.parse_args(argv)


def nearest_agent() -> tuple[str | None, int | None]:
    """Use process ancestry to reject inherited markers from an outer agent."""
    try:
        result = subprocess.run(
            ["ps", "-axo", "pid=,ppid=,comm="],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None, None
    parents: dict[int, tuple[int, str]] = {}
    for line in result.stdout.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) != 3:
            continue
        try:
            parents[int(parts[0])] = (int(parts[1]), Path(parts[2]).name.lower())
        except ValueError:
            continue
    pid = os.getppid()
    seen: set[int] = set()
    while pid > 1 and pid not in seen and pid in parents:
        seen.add(pid)
        ppid, name = parents[pid]
        if name in ("claude", "codex", "agy", "antigravity", "antigravity-cli"):
            return {"agy": "antigravity", "antigravity-cli": "antigravity"}.get(name, name), pid
        pid = ppid
    return None, None


def caller_identity(args: argparse.Namespace, nearest: tuple[str | None, int | None]) -> tuple[str, str] | None:
    kind, pid = nearest
    explicit_kind = args.caller_kind
    explicit_id = args.caller_session_id
    if bool(explicit_kind) != bool(explicit_id):
        raise ConsultationError("--caller-kind and --caller-session-id must be provided together.", 64)
    if explicit_kind:
        if not CALLER_ID_RE.fullmatch(explicit_id):
            raise ConsultationError("--caller-session-id has an invalid format.", 64)
        if kind and kind != explicit_kind:
            warn(f"Explicit caller {explicit_kind} differs from nearest detected process {kind}; "
                 "the invoking host is responsible for supplying its current conversation ID.")
        return explicit_kind, explicit_id
    if kind == "codex":
        candidate = os.environ.get("CODEX_THREAD_ID", "")
        if is_uuid(candidate):
            return "codex", candidate.lower()
    if kind == "claude":
        candidate = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
        claude_pid = os.environ.get("CLAUDE_PID", "")
        if is_uuid(candidate) and (not claude_pid or claude_pid == str(pid)):
            return "claude", candidate.lower()
    return None


def state_root(provider: str) -> Path:
    override = {
        "claude": "CONSULT_CLAUDE_CHAIN_STATE_DIR",
        "antigravity": "CONSULT_ANTIGRAVITY_CHAIN_STATE_DIR",
        "codex": "CONSULT_CODEX_STATE_DIR",
    }[provider]
    if os.environ.get(override):
        return Path(os.environ[override]).expanduser() / "v2"
    base = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))
    return base / "common-skills" / "consultations" / provider / "v2"


class StateStore:
    def __init__(self, provider: str, scope: dict[str, object]):
        self.scope = scope
        self.root = state_root(provider)
        digest = hashlib.sha256(
            json.dumps(scope, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self.path = self.root / f"{digest}.json"
        self.lock_path = self.root / f"{digest}.lock"
        self.fd: int | None = None

    def ensure_root(self) -> None:
        if self.root.is_symlink():
            raise ConsultationError(f"Consultation state directory is a symlink: {self.root}", 73)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.root.is_symlink() or not self.root.is_dir():
            raise ConsultationError(f"Invalid consultation state directory: {self.root}", 73)
        self.root.chmod(0o700)

    def __enter__(self) -> "StateStore":
        self.ensure_root()
        flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        self.fd = os.open(self.lock_path, flags, 0o600)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            os.close(self.fd)
            self.fd = None
            raise ConsultationError(
                "A consultation for this caller scope is already running; use --one-shot for an independent call.",
                75,
            ) from exc
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)

    def read(self) -> dict[str, object] | None:
        if not self.path.exists() and not self.path.is_symlink():
            return None
        if self.path.is_symlink():
            raise ConsultationError("Consultation state file is a symlink.", 65)
        try:
            data = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise ConsultationError(f"Cannot read consultation state: {exc}", 65) from exc
        if not isinstance(data, dict) or data.get("schema") != SCHEMA or data.get("scope") != self.scope:
            raise ConsultationError("Consultation state scope or schema does not match.", 65)
        target_id = data.get("target_id")
        if target_id is not None and not is_uuid(target_id):
            raise ConsultationError("Stored target conversation ID is invalid.", 65)
        if data.get("status") not in ("ACTIVE", "IN_FLIGHT", "BLOCKED"):
            raise ConsultationError("Stored consultation status is invalid.", 65)
        if data["status"] == "ACTIVE" and not is_uuid(target_id):
            raise ConsultationError("Active consultation has no valid target ID.", 65)
        return data

    def write(self, data: dict[str, object]) -> None:
        fd, temp_name = tempfile.mkstemp(prefix=".state-", dir=self.root)
        try:
            with os.fdopen(fd, "w") as handle:
                os.fchmod(handle.fileno(), 0o600)
                json.dump(data, handle, ensure_ascii=False, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def delete(self) -> None:
        self.path.unlink(missing_ok=True)


def make_state(scope: dict[str, object], status: str, target_id: str | None = None,
               retired_id: str | None = None, reason: str | None = None) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "scope": scope,
        "status": status,
        "target_id": target_id,
        "retired_target_id": retired_id,
        "reason": reason,
        "updated_at": int(time.time()),
    }


def resolve_binary(provider: str) -> str:
    candidates = {
        "claude": ("CONSULT_CLAUDE_BIN", "claude"),
        "antigravity": ("CONSULT_ANTIGRAVITY_BIN", "agy"),
        "codex": ("CONSULT_CODEX_BIN", "codex"),
    }
    variable, name = candidates[provider]
    override = os.environ.get(variable)
    if provider == "antigravity":
        override = override or os.environ.get("CONSULT_AGY_BIN")
    if override:
        path = Path(override).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
        raise ConsultationError(f"{variable} is not an executable file: {override}", 127)
    found = shutil.which(name)
    if found:
        return found
    if provider in ("claude", "antigravity"):
        shell = os.environ.get("SHELL", "")
        if shell and os.path.isfile(shell):
            result = subprocess.run([shell, "-lc", f"command -v {name}"], capture_output=True, text=True)
            found = result.stdout.strip().splitlines()
            if result.returncode == 0 and found and os.path.isfile(found[-1]) and os.access(found[-1], os.X_OK):
                return found[-1]
    raise ConsultationError(f"{name} CLI is not on PATH.", 127)


def build_prompt(provider: str, argument: str, stdin: str, auth_smoke: bool) -> str:
    if auth_smoke:
        return f"Reply exactly with: {provider}-auth-ok"
    if provider == "claude":
        prefix = """You are being consulted from another local AI coding agent through non-interactive Claude Code.

Return the complete answer directly in stdout.
Do not create, write, or update files as the answer artifact for this consultation.
Do not respond only by saying that you wrote a plan, report, markdown file, or other artifact.
If a plan, report, diff, checklist, or markdown document would be useful, include its full contents in this stdout response instead.
If the user explicitly asks you to edit files, follow that request only within the named scope and still print the complete result summary to stdout. Do not write a plan or report file as a substitute for the response.

Preserve the user's request, constraints, paths, language, and requested output shape."""
    else:
        name = "Codex CLI" if provider == "codex" else "Antigravity CLI"
        thinking = "reasoning-token" if provider == "codex" else "thinking"
        prefix = f"""You are {name} being consulted by another local AI coding agent as an independent engineering reviewer.

Take the time needed for a careful answer. There is no requested token, {thinking}, output, or budget cap for this consultation; prioritize correctness and concrete evidence over brevity.

Return a concise but complete response that the calling agent can compare against its own reasoning. Call out uncertainties, cite local file paths when relevant, and state when you are making an inference."""
    if argument:
        prefix += f"\n\nRequest from command arguments:\n{argument}"
    if stdin:
        prefix += f"\n\nRequest from stdin:\n{stdin}"
    return prefix


def artifact_notice(value: str) -> bool:
    return len(value.splitlines()) <= 8 and len(value.split()) <= 140 and ARTIFACT_RE.search(value) is not None


def parse_envelope(provider: str, raw: str, stream: bool) -> tuple[str, str, dict[str, object]]:
    try:
        if stream:
            events = [json.loads(line) for line in raw.splitlines() if line.strip()]
            if not all(isinstance(event, dict) for event in events):
                raise ValueError("stream event is not an object")
            if provider == "claude":
                matches = [event for event in events if event.get("type") == "result"]
                envelope = matches[-1] if matches else None
            else:
                matches = [event.get("result") for event in events if event.get("event") == "result"]
                envelope = matches[-1] if matches else None
        else:
            envelope = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise ConsultationError(f"{provider} did not return valid structured output: {exc}", 75) from exc
    if not isinstance(envelope, dict):
        raise ConsultationError(f"{provider} did not return a result envelope.", 75)
    identifier = envelope.get("session_id") if provider == "claude" else envelope.get("conversation_id")
    if not is_uuid(identifier):
        raise ConsultationError(f"{provider} returned no valid conversation ID.", 75)
    if provider == "claude":
        if envelope.get("is_error"):
            raise ConsultationError(f"Claude reported an error: {envelope.get('result', '')}", 75)
        answer = envelope.get("result")
    else:
        if envelope.get("status") != "SUCCESS":
            raise ConsultationError(f"Antigravity status: {envelope.get('status')}; {envelope.get('error', '')}", 75)
        answer = envelope.get("response")
    if not isinstance(answer, str) or not answer.strip():
        raise ConsultationError(f"{provider} returned no complete console answer.", 75)
    return identifier.lower(), answer, envelope


def child_environment(provider: str) -> dict[str, str]:
    environment = os.environ.copy()
    # The target must not inherit the outer agent's identity as its own.
    stale_markers = (
        "CLAUDECODE", "CLAUDE_CODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_PID",
        "ANTIGRAVITY_CLI", "ANTIGRAVITY_CLI_SESSION_ID", "AGY_CLI",
        "AGY_SESSION_ID", "AGY_BROWSER_WS_URL", "ANTIGRAVITY_INTERNAL_ORIGINATOR_OVERRIDE",
        "CODEX_SHELL", "CODEX_THREAD_ID", "CODEX_SESSION_ID",
        "CODEX_INTERNAL_ORIGINATOR_OVERRIDE",
    )
    for key in stale_markers:
        environment.pop(key, None)
    return environment


def run_command(command: list[str], cwd: Path, output_path: Path, provider: str) -> str:
    try:
        with output_path.open("wb") as output:
            result = subprocess.run(command, cwd=cwd, stdin=subprocess.DEVNULL, stdout=output,
                                    stderr=subprocess.PIPE, env=child_environment(provider))
    except OSError as exc:
        raise BeforeLaunchError(f"Could not start {provider} CLI: {exc}", 71) from exc
    stderr = result.stderr.decode("utf-8", errors="replace")
    if stderr:
        print(stderr, end="" if stderr.endswith("\n") else "\n", file=sys.stderr, flush=True)
    if result.returncode != 0:
        raise ConsultationError(
            f"Target CLI exited with status {result.returncode}; the consultation state is blocked.",
            result.returncode if 1 <= result.returncode <= 125 else 75,
        )
    if provider == "antigravity" and re.search(
        r"print[- ]?timeout|print mode.*timed out|warning:.*(?:timeout|timed out)",
        stderr, re.IGNORECASE
    ):
        raise ConsultationError("Antigravity ended at its print timeout; its partial answer was withheld.", 124)
    return output_path.read_text(errors="replace")


def resolved_output_format(provider: str, args: argparse.Namespace) -> str:
    output_format = getattr(args, "output_format", None)
    if not output_format and provider == "claude":
        output_format = os.environ.get("CONSULT_CLAUDE_OUTPUT_FORMAT")
    output_format = output_format or "text"
    if output_format not in ("text", "json", "stream-json"):
        raise ConsultationError(f"Unsupported output format: {output_format}", 64)
    return output_format


def antigravity_permission(args: argparse.Namespace) -> str:
    permission = (args.permission_mode or args.approval_mode
                  or os.environ.get("CONSULT_ANTIGRAVITY_PERMISSION_MODE")
                  or "dangerously-skip-permissions")
    if args.dangerously_skip_permissions:
        permission = "dangerously-skip-permissions"
    if args.no_dangerously_skip_permissions:
        permission = "request-review"
    if args.sandbox:
        permission = "sandbox"
    if permission in ("always-proceed", "yolo", "dangerous", "skip-permissions", "skip"):
        permission = "dangerously-skip-permissions"
    elif permission in ("ask", "default", "strict", "plan", "auto_edit", "manual", "request_review"):
        permission = "request-review"
    elif permission in ("proceed-in-sandbox", "proceed_in_sandbox"):
        permission = "sandbox"
    if permission not in ("dangerously-skip-permissions", "request-review", "sandbox"):
        raise ConsultationError(f"Unsupported Antigravity permission mode: {permission}", 64)
    return permission


def run_provider(provider: str, args: argparse.Namespace, binary: str, cwd: Path,
                 prompt: str, expected_id: str | None) -> tuple[str, str, str]:
    output_format = resolved_output_format(provider, args)
    stream = output_format == "stream-json"
    try:
        temporary_directory = tempfile.TemporaryDirectory(prefix="consultation-")
    except OSError as exc:
        raise BeforeLaunchError(f"Could not prepare {provider} CLI output: {exc}", 71) from exc
    with temporary_directory as temporary:
        temporary_path = Path(temporary)
        output_path = temporary_path / "stdout"
        if provider == "claude":
            model = args.model or os.environ.get("CONSULT_CLAUDE_MODEL") or os.environ.get("CLAUDE_MODEL") or "opus"
            effort = args.effort or os.environ.get("CONSULT_CLAUDE_EFFORT") or "max"
            permission = args.permission_mode or os.environ.get("CONSULT_CLAUDE_PERMISSION_MODE") or "auto"
            if permission == "plan":
                warn("Claude plan permission mode is not used for consultations; using auto.")
                permission = "auto"
            warn(f"  model: {model}; effort: {effort}; permission: {permission}; output: {output_format}")
            command = [binary, "-p", prompt, "--model", model, "--effort", effort,
                       "--permission-mode", permission, "--output-format", "stream-json" if stream else "json"]
            if stream:
                command.append("--verbose")
            for extra in args.add_dir:
                command.extend(("--add-dir", extra))
            if expected_id:
                command.extend(("--resume", expected_id))
            else:
                command.extend(("--session-id", str(uuid.uuid4())))
            raw = run_command(command, cwd, output_path, provider)
            identifier, answer, _ = parse_envelope(provider, raw, stream)
            if expected_id and identifier != expected_id:
                raise ConsultationError(
                    f"Claude resumed {identifier} instead of requested {expected_id}.", 75
                )
            if artifact_notice(answer) and not args.auth_smoke:
                warn("Claude returned only an artifact notice; asking the same session for the full answer.")
                retry = "The previous response only referred to a file artifact. Print the complete answer directly now, without creating a file."
                retry_command = [binary, "-p", retry, "--model", model, "--effort", effort,
                                 "--permission-mode", permission, "--output-format", "stream-json" if stream else "json"]
                if stream:
                    retry_command.append("--verbose")
                for extra in args.add_dir:
                    retry_command.extend(("--add-dir", extra))
                retry_command.extend(("--resume", identifier))
                raw = run_command(retry_command, cwd, output_path, provider)
                retry_id, answer, _ = parse_envelope(provider, raw, stream)
                if retry_id != identifier or artifact_notice(answer):
                    raise ConsultationError("Claude artifact retry did not return a complete answer in the same session.", 75)
            rendered = raw if output_format != "text" else answer
            return identifier, answer, rendered
        if provider == "antigravity":
            model = args.model or os.environ.get("CONSULT_ANTIGRAVITY_MODEL") or os.environ.get("AGY_MODEL") or ""
            permission = antigravity_permission(args)
            timeout = args.print_timeout or os.environ.get("CONSULT_ANTIGRAVITY_PRINT_TIMEOUT") or "24h"
            warn(f"  model: {model or 'CLI default'}; permission: {permission}; "
                 f"output: {output_format}; print timeout: {timeout}")
            command = [binary, "-p", prompt, "--output-format", "stream-json" if stream else "json",
                       "--print-timeout", timeout]
            if model and model not in ("default", "cli-default"):
                command.extend(("--model", model))
            if permission == "sandbox":
                command.append("--sandbox")
            elif permission == "dangerously-skip-permissions":
                command.append("--dangerously-skip-permissions")
            if expected_id:
                command.extend(("--conversation", expected_id))
            raw = run_command(command, cwd, output_path, provider)
            identifier, answer, _ = parse_envelope(provider, raw, stream)
            if expected_id and identifier != expected_id:
                raise ConsultationError(
                    f"Antigravity created {identifier} instead of resuming {expected_id}; its answer was withheld.", 75
                )
            rendered = raw if output_format != "text" else answer
            return identifier, answer, rendered
        model = args.model or os.environ.get("CODEX_MODEL") or "gpt-6-sol"
        effort = args.effort or os.environ.get("CODEX_REASONING_EFFORT") or "max"
        tier = "fast" if args.fast else "default"
        warn(f"  model: {model}; effort: {effort}; service tier: {tier}; "
             "approval: on-request; sandbox: workspace-write")
        final_path = temporary_path / "final-answer"
        command = [binary, "-C", str(cwd), "--approve-for-me", "exec"]
        if expected_id:
            command.append("resume")
        command.extend(("--json", "-m", model, "-c", f'model_reasoning_effort="{effort}"',
                        "-c", f'service_tier="{tier}"', "-c", 'approval_policy="on-request"',
                        "--skip-git-repo-check", "-o", str(final_path)))
        if expected_id:
            command.append(expected_id)
        command.append("-")
        try:
            with output_path.open("wb") as output:
                result = subprocess.run(command, cwd=cwd, input=prompt.encode(), stdout=output,
                                        stderr=subprocess.PIPE, env=child_environment(provider))
        except OSError as exc:
            raise BeforeLaunchError(f"Could not start Codex CLI: {exc}", 71) from exc
        stderr = result.stderr.decode("utf-8", errors="replace")
        if stderr:
            print(stderr, end="" if stderr.endswith("\n") else "\n", file=sys.stderr, flush=True)
        if result.returncode != 0:
            raise ConsultationError(f"Codex exited with status {result.returncode}; the consultation state is blocked.",
                                    result.returncode if 1 <= result.returncode <= 125 else 75)
        identifiers: list[str] = []
        completed = False
        for line in output_path.read_text(errors="replace").splitlines():
            try:
                event = json.loads(line)
            except ValueError as exc:
                raise ConsultationError(f"Codex emitted invalid JSONL: {exc}", 75) from exc
            if not isinstance(event, dict):
                raise ConsultationError("Codex emitted a non-object JSONL event.", 75)
            if event.get("type") == "thread.started":
                identifiers.append(event.get("thread_id", ""))
            elif event.get("type") == "turn.completed":
                completed = True
            elif event.get("type") in ("turn.failed", "error"):
                raise ConsultationError(f"Codex reported {event.get('type')}: {event}", 75)
        if len(identifiers) != 1 or not is_uuid(identifiers[0]) or not completed:
            raise ConsultationError("Codex did not confirm one thread ID and a completed turn.", 75)
        identifier = identifiers[0].lower()
        if expected_id and identifier != expected_id:
            raise ConsultationError(f"Codex returned thread {identifier} instead of {expected_id}.", 75)
        if not final_path.exists():
            raise ConsultationError("Codex did not write its final answer.", 75)
        answer = final_path.read_text(errors="replace")
        if not answer.strip():
            raise ConsultationError("Codex returned an empty final answer.", 75)
        return identifier, answer, answer


def scope_for(provider: str, cwd: Path, caller: tuple[str, str] | None,
              chain: str, shared: bool) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "provider": provider,
        "workdir": str(cwd),
        "caller_kind": None if shared else caller[0] if caller else None,
        "caller_id": None if shared else caller[1] if caller else None,
        "chain": chain,
        "shared": shared,
    }


def main(provider: str, argv: list[str]) -> int:
    os.umask(0o077)
    args = parse_args(provider, argv)
    if provider in ("claude", "antigravity"):
        legacy_name = "CONSULT_CLAUDE_CHAIN_KEY" if provider == "claude" else "CONSULT_ANTIGRAVITY_CHAIN_KEY"
        if os.environ.get(legacy_name):
            warn(f"Ignoring inherited {legacy_name}; pass --chain explicitly within the current caller session.")
    reset_kind = bool(args.reset_chain) + bool(args.reset_shared_chain) + bool(args.reset_session)
    if reset_kind > 1 or (args.chain and args.shared_chain):
        raise ConsultationError("Conflicting chain or reset options.", 64)
    if args.one_shot and (args.new_session or args.chain or args.shared_chain or reset_kind):
        raise ConsultationError("--one-shot cannot be combined with state-changing options.", 64)
    if args.new_session and reset_kind:
        raise ConsultationError("--new-session cannot be combined with reset options.", 64)
    if args.status and (args.one_shot or args.new_session or reset_kind):
        raise ConsultationError("--status cannot be combined with execution or reset options.", 64)
    if reset_kind and (args.chain or args.shared_chain):
        raise ConsultationError("Use one chain selector or reset selector at a time.", 64)
    auth_smoke = getattr(args, "auth_smoke", False)
    if auth_smoke and (args.chain or args.shared_chain or args.new_session or reset_kind or args.status):
        raise ConsultationError("--auth-smoke cannot be combined with session state options.", 64)
    raw_workdir = args.workdir or {
        "claude": os.environ.get("CONSULT_CLAUDE_WORKDIR"),
        "antigravity": os.environ.get("CONSULT_ANTIGRAVITY_WORKDIR"),
        "codex": os.environ.get("CODEX_WORKDIR"),
    }[provider] or os.getcwd()
    if auth_smoke:
        raw_workdir = os.environ.get(
            "CONSULT_CLAUDE_AUTH_WORKDIR" if provider == "claude" else "CONSULT_ANTIGRAVITY_AUTH_WORKDIR",
            "/private/tmp" if Path("/private/tmp").is_dir() else "/tmp",
        )
    cwd = Path(raw_workdir).expanduser().resolve()
    if not cwd.is_dir():
        raise ConsultationError(f"Working directory does not exist: {cwd}", 66)
    nearest = nearest_agent()
    if (provider == "antigravity"
            and nearest[0] in (None, "antigravity")
            and os.environ.get("CONSULT_ANTIGRAVITY_CLI_FROM_ANTIGRAVITY") == "1"):
        raise ConsultationError("Antigravity cannot recursively consult itself.", 69)
    if nearest[0] == provider:
        raise ConsultationError(f"{provider} cannot recursively consult itself.", 69)
    if nearest[0] is None:
        self_markers = {
            "claude": ("CLAUDECODE", "CLAUDE_CODE"),
            "codex": ("CODEX_SHELL", "CODEX_THREAD_ID"),
            "antigravity": ("ANTIGRAVITY_CLI", "AGY_CLI", "AGY_SESSION_ID"),
        }
        antigravity_originator = (
            provider == "antigravity"
            and re.search(r"\bAntigravity\b",
                          os.environ.get("ANTIGRAVITY_INTERNAL_ORIGINATOR_OVERRIDE", ""), re.IGNORECASE)
        )
        if any(os.environ.get(marker) for marker in self_markers[provider]) or antigravity_originator:
            raise ConsultationError(
                f"Cannot rule out recursive {provider} invocation because caller process is unknown.", 69
            )
    caller = caller_identity(args, nearest)
    if caller and caller[0] == provider:
        raise ConsultationError(f"{provider} cannot recursively consult itself.", 69)
    shared = bool(args.shared_chain or args.reset_shared_chain)
    chain = args.chain or args.shared_chain or args.reset_chain or args.reset_shared_chain or "default"
    if not chain.strip() or len(chain) > 128:
        raise ConsultationError("Chain name must be 1 to 128 non-whitespace characters.", 64)
    if (args.chain or args.reset_chain or args.new_session or args.reset_session or args.status) and not (caller or shared):
        raise ConsultationError("A current caller session ID is required for this option; use --caller-kind and --caller-session-id.", 64)
    independent = args.one_shot or auth_smoke or (caller is None and not shared)
    if independent and not args.one_shot and not auth_smoke:
        warn("Current caller session could not be verified; running an independent one-shot consultation without reading saved state.")
    scope = scope_for(provider, cwd, caller, chain, shared)
    if args.status:
        store = StateStore(provider, scope)
        store.ensure_root()
        print(json.dumps(store.read(), ensure_ascii=False, sort_keys=True))
        return 0
    if reset_kind:
        with StateStore(provider, scope) as store:
            store.delete()
            print("Consultation mapping removed; the target CLI conversation still exists.")
        return 0
    argument = " ".join(args.request)
    stdin = "" if argument or sys.stdin.isatty() else sys.stdin.read()
    if auth_smoke and (argument or stdin):
        raise ConsultationError("--auth-smoke cannot be combined with a prompt.", 64)
    if not auth_smoke and not (argument or stdin):
        raise ConsultationError("No consultation prompt received from arguments or stdin.", 64)
    prompt = build_prompt(provider, argument, stdin, auth_smoke)
    resolved_output_format(provider, args)
    if provider == "antigravity":
        antigravity_permission(args)
    if independent:
        binary = resolve_binary(provider)
        warn(f"Starting {provider} consultation: one-shot; workdir={cwd}")
        _, answer, rendered = run_provider(provider, args, binary, cwd, prompt, None)
        if auth_smoke and answer.strip() != f"{provider}-auth-ok":
            raise ConsultationError(f"{provider} auth smoke returned an unexpected answer.", 65)
        print(rendered, end="" if rendered.endswith("\n") else "\n")
        return 0
    with StateStore(provider, scope) as store:
        old = store.read()
        if old and old["status"] != "ACTIVE" and not args.new_session:
            raise ConsultationError(
                f"Consultation state is {old['status']} ({old.get('reason') or 'prior call incomplete'}); "
                "use --new-session or --reset-session explicitly.", 75
            )
        previous_id = old.get("target_id") if old else None
        expected_id = None if args.new_session else previous_id
        if expected_id and not is_uuid(expected_id):
            raise ConsultationError("Stored target conversation ID is invalid.", 65)
        binary = resolve_binary(provider)
        inflight = make_state(scope, "IN_FLIGHT", expected_id,
                              previous_id if args.new_session else old.get("retired_target_id") if old else None)
        store.write(inflight)
        try:
            action = "resume" if expected_id else "new"
            warn(f"Starting {provider} consultation: {action}; caller={scope['caller_kind'] or 'shared'}; workdir={cwd}")
            identifier, _answer, rendered = run_provider(provider, args, binary, cwd, prompt, expected_id)
            store.write(make_state(scope, "ACTIVE", identifier, inflight.get("retired_target_id")))
        except BeforeLaunchError:
            if old:
                store.write(old)
            else:
                store.delete()
            raise
        except Exception as exc:
            reason = f"error-code-{exc.code}" if isinstance(exc, ConsultationError) else type(exc).__name__
            store.write(make_state(scope, "BLOCKED", expected_id,
                                   inflight.get("retired_target_id"), reason))
            raise
        print(rendered, end="" if rendered.endswith("\n") else "\n")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("claude", "antigravity", "codex"):
        warn("Runner requires a target provider: claude, antigravity, or codex.")
        sys.exit(64)
    try:
        sys.exit(main(sys.argv[1], sys.argv[2:]))
    except ConsultationError as exc:
        warn(f"Consultation error: {exc}")
        sys.exit(exc.code)
    except (OSError, ValueError) as exc:
        warn(f"Consultation error: {exc}")
        sys.exit(70)
