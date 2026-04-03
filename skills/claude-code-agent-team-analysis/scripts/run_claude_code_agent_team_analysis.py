#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from time import monotonic, sleep
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from analysis_run import find_matching_run_meta_path, resolve_tool_output_dir

DEFAULTS = {
    "model": "opus",
    "worker_model": "sonnet",
    "lead_effort": "high",
    "worker_effort": "medium",
    "max_turns": 120,
    "out_dir": ".codex-analysis/claude-code",
    "tools": "Bash,Glob,Grep,LSP,Read,SendMessage,TaskCreate,TaskGet,TaskList,TaskUpdate,TeamCreate,TeamDelete,TodoWrite",
    "allowed_tools": (
        "Glob,Grep,LSP,Read,SendMessage,TaskCreate,TaskGet,TaskList,TaskUpdate,TeamCreate,TeamDelete,TodoWrite,"
        "Bash(git rev-parse *),Bash(git ls-files *),Bash(git status *),Bash(git diff *),Bash(git log *),"
        "Bash(git grep *),Bash(git show *),Bash(pwd),Bash(ls),Bash(ls *),Bash(cat *),Bash(head *),"
        "Bash(tail *),Bash(sed *),Bash(wc *),Bash(stat *),Bash(file *),Bash(tree *),Bash(jq *)"
    ),
    "minimum_agent_team_version": (2, 1, 32),
}
AUTO_PREFLIGHT_TOKEN_THRESHOLD = 180000
REPORT_MIN_CHARS = 1200
REPORT_REQUIRED_SECTIONS = [
    "scope and assumptions",
    "short system map",
    "top findings",
    "evidence",
    "confirmed facts vs inference or uncertainty",
    "test-gap recommendations",
    "refactoring or redesign recommendations",
    "quick wins vs deeper changes",
    "suggested next design steps",
]
REPORT_SECTION_ALIASES = {
    "scope and assumptions": ["scope and assumptions"],
    "short system map": ["short system map", "system map"],
    "top findings": [
        "top findings",
        "top findings prioritized",
        "top findings prioritised",
        "prioritized findings",
        "prioritised findings",
        "key findings",
    ],
    "evidence": [
        "evidence",
        "evidence per finding",
        "evidence for each finding",
    ],
    "confirmed facts vs inference or uncertainty": [
        "confirmed facts vs inference or uncertainty",
        "confirmed facts vs inference and uncertainty",
        "confirmed facts versus inference or uncertainty",
        "confirmed facts versus inference and uncertainty",
        "confirmed facts vs inferences or uncertainty",
    ],
    "test-gap recommendations": [
        "test-gap recommendations",
        "test gap recommendations",
        "test gaps recommendations",
        "test-gap recommendation",
        "test gap recommendation",
        "testing gap recommendations",
        "test coverage gap recommendations",
    ],
    "refactoring or redesign recommendations": [
        "refactoring or redesign recommendations",
        "refactoring and redesign recommendations",
        "refactoring redesign recommendations",
        "refactor or redesign recommendations",
        "refactor and redesign recommendations",
        "refactor redesign recommendations",
    ],
    "quick wins vs deeper changes": [
        "quick wins vs deeper changes",
        "quick wins versus deeper changes",
        "quick wins and deeper changes",
    ],
    "suggested next design steps": [
        "suggested next design steps",
        "next design steps",
        "suggested next steps",
    ],
}
FOLLOWUP_REPORT_PROMPT = textwrap.dedent(
    """
    Using the repository evidence already gathered in this resumed session, write the full consolidated report now.
    Do not redo the whole exploration unless absolutely necessary.
    Use these exact markdown H2 headings, verbatim:
    ## Scope and assumptions
    ## Short system map
    ## Top findings
    ## Evidence
    ## Confirmed facts vs inference or uncertainty
    ## Test-gap recommendations
    ## Refactoring or redesign recommendations
    ## Quick wins vs deeper changes
    ## Suggested next design steps
    Put the relevant content under each heading.
    Keep it evidence-first and concise but complete. Return markdown only.
    """
).strip()
MARKDOWN_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
BOLD_HEADING_RE = re.compile(r"^\s*(?:\*\*|__)(.+?)(?:\*\*|__)\s*$")
LEADING_NUMBER_RE = re.compile(r"^\(?\d+\)?[.)]?\s+")

SECURITY_HINT_RE = re.compile(
    r"\b(auth|oauth|token|secret|credential|password|permission|role|rbac|acl|iam|session|cookie|jwt|"
    r"payment|billing|checkout|admin|csrf|xss|ssrf|webhook|public api|external api|encrypt|decrypt|"
    r"security|login|signup)\b",
    re.IGNORECASE,
)


@dataclass
class SelectedMode:
    requested: str
    effective: str
    packaging_recommendation: str | None


class ClaudeCommandError(RuntimeError):
    pass


def debug(msg: str) -> None:
    print(msg, file=sys.stderr)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def persist_metadata(run_meta_path: Path, run_meta: dict[str, Any], status_path: Path, status: dict[str, Any]) -> None:
    save_json(run_meta_path, run_meta)
    save_json(status_path, status)


def parse_version(text: str) -> tuple[int, int, int] | None:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def version_ok(found: tuple[int, int, int] | None, minimum: tuple[int, int, int]) -> bool:
    if found is None:
        return False
    return found >= minimum


def ensure_not_nested() -> None:
    if os.environ.get("CLAUDECODE") == "1":
        raise SystemExit(
            "Refusing to launch a nested Claude Code session from a Claude-spawned shell. "
            "Run this helper from a normal terminal, CI runner, or another external process."
        )


def ensure_claude_available(minimum_version: tuple[int, int, int]) -> tuple[str, str]:
    claude_path = shutil.which("claude")
    if not claude_path:
        raise SystemExit(
            "The 'claude' CLI was not found on PATH. Install Claude Code first and confirm 'claude --version' works."
        )
    try:
        proc = subprocess.run(
            [claude_path, "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise SystemExit(f"Failed to execute '{claude_path} --version': {exc}") from exc

    version_text = (proc.stdout or proc.stderr or "").strip()
    found = parse_version(version_text)
    if proc.returncode != 0:
        raise SystemExit(
            f"Unable to verify Claude Code version. 'claude --version' exited with {proc.returncode}. Output:\n{version_text}"
        )
    if not version_ok(found, minimum_version):
        minimum_str = ".".join(str(p) for p in minimum_version)
        raise SystemExit(
            f"Claude Code {minimum_str}+ is required for agent teams. Found: {version_text or '(unknown)'}"
        )
    return claude_path, version_text


def normalize_mode(requested: str, manifest: dict[str, Any]) -> SelectedMode:
    packaging_recommendation = manifest.get("packaging_recommendation")
    manifest_rec = manifest.get("mode_recommendation") or packaging_recommendation or ""
    if requested == "full_repo_team":
        return SelectedMode(requested=requested, effective="full_repo_team", packaging_recommendation=packaging_recommendation)
    if requested == "focused_team":
        return SelectedMode(requested=requested, effective="focused_team", packaging_recommendation=packaging_recommendation)
    if manifest_rec in {"focused_team", "focused_file_search"}:
        effective = "focused_team"
    else:
        effective = "full_repo_team"
    return SelectedMode(requested=requested, effective=effective, packaging_recommendation=packaging_recommendation)


def choose_seed_files(manifest: dict[str, Any], effective_mode: str, limit: int = 60) -> list[str]:
    selections = manifest.get("selections", {})
    if effective_mode == "focused_team":
        candidates = list(selections.get("focused_files") or [])
    else:
        candidates = list(selections.get("full_files") or [])
    return candidates[:limit]


def should_include_security(goal: str, manifest: dict[str, Any], force: bool, skip: bool) -> bool:
    if skip:
        return False
    if force:
        return True
    parts: list[str] = [goal]
    parts.extend(str(item) for item in manifest.get("scope") or [])
    parts.extend(str(item) for item in manifest.get("keywords") or [])
    haystack = "\n".join(parts)
    return bool(SECURITY_HINT_RE.search(haystack))


def build_worker_prompt(title: str, checklist: list[str], output_requirements: list[str]) -> str:
    checklist_text = "\n".join(f"- {item}" for item in checklist)
    output_text = "\n".join(f"- {item}" for item in output_requirements)
    return textwrap.dedent(
        f"""
        You are the {title} for a read-only codebase analysis team.

        Mission:
        - Investigate only your assigned lens.
        - Stay evidence-first and avoid broad claims you cannot support from files.
        - You may read files, grep, use LSP, and run read-only shell commands that are already permitted.
        - Never edit, write, delete, commit, or run destructive commands.

        Investigate:
        {checklist_text}

        Response requirements:
        {output_text}
        """
    ).strip()


def build_agents(worker_model: str, worker_effort: str, include_security: bool) -> dict[str, dict[str, Any]]:
    common_tools = ["Read", "Glob", "Grep", "LSP", "Bash"]
    output_requirements = [
        "Use concise markdown.",
        "For every important finding, include file paths and line references when available.",
        "Separate confirmed findings from inference and unknowns.",
        "Prioritize actionable engineering conclusions over generic advice.",
    ]

    agents: dict[str, dict[str, Any]] = {
        "architecture-mapper": {
            "description": "Maps module boundaries, entrypoints, major workflows, and cross-layer coupling for repository analysis.",
            "tools": common_tools,
            "model": worker_model,
            "effort": "high" if worker_effort in {"medium", "high", "max"} else worker_effort,
            "prompt": build_worker_prompt(
                "architecture mapper",
                [
                    "Repository purpose, module responsibilities, and high-level boundaries.",
                    "Main entrypoints, runtime surfaces, integration points, and orchestration flow.",
                    "At least one relevant end-to-end workflow for the user goal.",
                    "Places where ownership or boundaries are unclear or misleading.",
                ],
                output_requirements,
            ),
        },
        "correctness-gap-reviewer": {
            "description": "Checks workflow validity, failure handling, TODO/FIXME markers, missing implementation, and deprecated or dead logic.",
            "tools": common_tools,
            "model": worker_model,
            "effort": "high",
            "prompt": build_worker_prompt(
                "correctness and gap reviewer",
                [
                    "Failure handling, retries, partial states, and invalid state transitions.",
                    "Missing handlers, TODO/FIXME/HACK/WIP markers, stubbed branches, or not-yet-wired features.",
                    "Deprecated, duplicate, legacy, or suspiciously unused logic.",
                    "Workflow mismatches between visible code paths and intended user or system behavior.",
                ],
                output_requirements,
            ),
        },
        "tests-refactor-reviewer": {
            "description": "Evaluates test coverage shape, missing scenarios, duplication, coupling, and refactoring seams.",
            "tools": common_tools,
            "model": worker_model,
            "effort": worker_effort,
            "prompt": build_worker_prompt(
                "tests and refactor reviewer",
                [
                    "What workflows are protected by tests and which are not.",
                    "Missing edge cases, failure-path tests, integration-test gaps, and flakiness risks.",
                    "Refactoring opportunities justified by duplication, mixed responsibility, or poor seams.",
                    "Quick wins versus deeper redesigns that need broader validation.",
                ],
                output_requirements,
            ),
        },
        "performance-reviewer": {
            "description": "Checks hot paths, repeated work, avoidable I/O, scaling risks, async boundaries, and resource usage.",
            "tools": common_tools,
            "model": worker_model,
            "effort": worker_effort,
            "prompt": build_worker_prompt(
                "performance reviewer",
                [
                    "Repeated work, avoidable I/O, and N+1 or quadratic patterns.",
                    "Blocking operations on hot paths, memory growth risks, and expensive serialization.",
                    "Caching, batching, invalidation, and concurrency or async-boundary concerns.",
                    "Only flag risks supported by visible code and nearby configuration.",
                ],
                output_requirements,
            ),
        },
    }

    if include_security:
        agents["security-reviewer"] = {
            "description": "Audits auth, authorization, secrets, input handling, external interfaces, and security-sensitive configuration.",
            "tools": common_tools,
            "model": worker_model,
            "effort": "high",
            "prompt": build_worker_prompt(
                "security reviewer",
                [
                    "Authentication, authorization, permission checks, and trust boundaries.",
                    "Secret handling, token use, credential exposure, and dangerous defaults.",
                    "Input validation, injection risk, unsafe deserialization, SSRF-style fetches, and webhook/public API exposure when visible.",
                    "Security-sensitive configuration or dependency usage that materially affects the requested scope.",
                ],
                output_requirements,
            ),
        }

    return agents


def summarize_warnings(warnings: list[str]) -> str:
    if not warnings:
        return "- none"
    return "\n".join(f"- {item}" for item in warnings)


def build_system_prompt(
    manifest_path: Path,
    repo_tree_path: Path | None,
    goal: str,
    effective_mode: str,
    include_security: bool,
    seed_files: list[str],
) -> str:
    seed_lines = "\n".join(f"- {path}" for path in seed_files[:40]) if seed_files else "- none"
    security_note = (
        "Include the security-reviewer role because the goal or visible scope looks security-sensitive."
        if include_security
        else "Do not spawn a security-reviewer unless you uncover a clearly security-sensitive surface during early mapping."
    )
    repo_tree_note = str(repo_tree_path) if repo_tree_path else "(repo tree unavailable)"

    mode_specific = {
        "full_repo_team": (
            "This run is a broad whole-repository analysis. Start from the repo map, then distribute independent lenses across the team. "
            "Do not try to read the whole repository linearly; use targeted exploration and evidence sampling."
        ),
        "focused_team": (
            "This run is a focused scoped analysis. Start from the focused file set in the manifest, but expand into dependencies, configs, tests, and docs when needed. "
            "Do not make repository-wide claims unless you intentionally broaden the search and have evidence for them."
        ),
    }[effective_mode]

    return textwrap.dedent(
        f"""
        You are the lead analyst for a read-only Claude Code agent team.

        This run is for repository analysis only.

        Hard rules:
        - Never edit, write, delete, rename, stage, commit, or run destructive commands.
        - Use only the provided read/search/team-coordination tools.
        - Treat Bash as read-only reconnaissance only.
        - Use agent teams only when workstreams are independent; do not overspawn teammates.
        - Agent teams are activated through environment and prompting in this helper; do not rely on a dedicated CLI switch.
        - Every important claim must be grounded in concrete files.
        - Separate confirmed findings, plausible inference, and unknowns.
        - If evidence is insufficient, say exactly what is missing.

        First steps:
        1. Read `{manifest_path}`.
        2. Read `{repo_tree_note}` if available.
        3. Decide how to split the work into independent teammate lenses.
        4. Create the team and assign explicit subtasks with success criteria.

        Recommended teammate roles for this skill:
        - architecture-mapper
        - correctness-gap-reviewer
        - tests-refactor-reviewer
        - performance-reviewer
        - security-reviewer (conditional)

        {security_note}

        Mode guidance:
        {mode_specific}

        Seed files from preparation:
        {seed_lines}

        Coordination guidance:
        - Keep the shared task list concise and independent.
        - Ask each teammate to return: findings, evidence, confidence, and open questions.
        - Merge overlapping findings instead of repeating them.
        - Resolve contradictions explicitly.
        - Shut down and clean up the team before finishing if Claude created one.

        Final output requirements:
        1. Scope and assumptions
        2. Short system map
        3. Top findings (prioritized)
        4. Evidence for each finding with file paths and line references when possible
        5. Confirmed facts vs inference or uncertainty
        6. Test-gap recommendations
        7. Refactoring or redesign recommendations
        8. Quick wins vs deeper changes
        9. Suggested next design steps

        User goal:
        {goal or '(none provided)'}
        """
    ).strip() + "\n"


def build_user_prompt(
    goal: str,
    manifest: dict[str, Any],
    mode: SelectedMode,
    include_security: bool,
    seed_files: list[str],
) -> str:
    warnings_block = summarize_warnings(list(manifest.get("warnings") or []))
    scope = ", ".join(manifest.get("scope") or []) or "(none provided)"
    keywords = ", ".join(manifest.get("keywords") or []) or "(none)"
    stats = manifest.get("stats") or {}
    seed_lines = "\n".join(f"- {path}" for path in seed_files[:60]) if seed_files else "- none"
    security_line = "yes" if include_security else "no"

    return textwrap.dedent(
        f"""
        Analyze this local repository with a read-only Claude Code agent team.

        Goal:
        {goal or manifest.get('goal') or '(none provided)'}

        Preparation summary:
        - repo root: {manifest.get('repo_root')}
        - requested mode: {mode.requested}
        - effective mode: {mode.effective}
        - preparation recommendation: {manifest.get('mode_recommendation')}
        - legacy packaging recommendation: {mode.packaging_recommendation or '(none)'}
        - explicit scope hints: {scope}
        - extracted keywords: {keywords}
        - included file count: {stats.get('included_file_count', '(unknown)')}
        - focused file count: {stats.get('focused_file_count', '(unknown)')}
        - estimated included tokens: {stats.get('included_estimated_tokens', '(unknown)')}
        - estimated focused tokens: {stats.get('focused_estimated_tokens', '(unknown)')}
        - conditional security reviewer: {security_line}

        Local warnings:
        {warnings_block}

        Start from these prepared seed files, then expand only when needed:
        {seed_lines}

        Important instructions:
        - Agent teams are enabled for this session via environment; create and coordinate the team from the prompt itself.
        - Create the agent team now rather than doing a single monolithic pass.
        - Keep all teammates read-only.
        - Use architecture, correctness/gaps, tests/refactor, and performance as the default independent lenses.
        - Add the security lens only when relevant.
        - Do not use external web research unless I explicitly ask for it later.
        - Finish with one consolidated report that follows the required section structure.
        """
    ).strip() + "\n"


def compute_poll_interval_seconds(elapsed_seconds: int) -> int:
    if elapsed_seconds < 1800:
        return 300
    if elapsed_seconds < 2400:
        return 150
    if elapsed_seconds < 3000:
        return 90
    return 30


def tail_text(path: Path, max_chars: int = 4000) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def maybe_extract_session_id(data: dict[str, Any]) -> str | None:
    for key in ("session_id", "sessionId"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    session = data.get("session")
    if isinstance(session, dict):
        for key in ("id", "session_id"):
            value = session.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def maybe_extract_result_text(data: dict[str, Any]) -> str:
    for key in ("result", "text"):
        value = data.get(key)
        if isinstance(value, str):
            return value
    structured = data.get("structured_output")
    if isinstance(structured, dict):
        return json.dumps(structured, indent=2, ensure_ascii=False)
    return json.dumps(data, indent=2, ensure_ascii=False)


def result_is_error(data: dict[str, Any]) -> bool:
    return bool(data.get("is_error"))


def extract_reported_reset_time(text: str) -> str | None:
    match = re.search(r"resets?\s+([^\n]+)", text, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip().rstrip(".")


def classify_failure_kind(
    return_code: int,
    stderr_tail: str,
    result_data: dict[str, Any] | None = None,
    raw_stdout: str = "",
    default_kind: str | None = None,
) -> dict[str, Any]:
    result_text = maybe_extract_result_text(result_data) if result_data else ""
    combined = "\n".join(part for part in [stderr_tail, result_text, raw_stdout] if part).strip()
    normalized = combined.lower()
    reported_reset_time = extract_reported_reset_time(combined)

    if "hit your limit" in normalized:
        failure_kind = "quota_exceeded"
    elif "may not exist or you may not have access" in normalized or "do not have access" in normalized:
        failure_kind = "model_access_denied"
    elif "unknown option" in normalized or "unknown argument" in normalized or "unexpected argument" in normalized:
        failure_kind = "invalid_option"
    elif default_kind:
        failure_kind = default_kind
    elif return_code != 0:
        failure_kind = "subprocess_exit_nonzero"
    else:
        failure_kind = "unknown_runtime_error"

    failure_message = result_text or stderr_tail or raw_stdout or failure_kind
    return {
        "failure_kind": failure_kind,
        "failure_message": failure_message,
        "reported_reset_time": reported_reset_time,
    }


def normalize_heading_text(text: str) -> str:
    normalized = text.strip().lower()
    normalized = re.sub(r"`", "", normalized)
    normalized = re.sub(r"[*_]+", "", normalized)
    normalized = LEADING_NUMBER_RE.sub("", normalized)
    normalized = normalized.replace("&", " and ")
    normalized = normalized.replace("vs.", "vs")
    normalized = re.sub(r"[/:-]+", " ", normalized)
    normalized = re.sub(r"[()]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def extract_report_headings(report_text: str) -> list[str]:
    headings: list[str] = []
    for raw_line in report_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = MARKDOWN_HEADING_RE.match(line)
        if match:
            headings.append(normalize_heading_text(match.group(1)))
            continue
        match = BOLD_HEADING_RE.match(line)
        if match:
            headings.append(normalize_heading_text(match.group(1)))
    return headings


def build_normalized_section_aliases() -> dict[str, set[str]]:
    return {
        canonical: {normalize_heading_text(alias) for alias in [canonical, *REPORT_SECTION_ALIASES.get(canonical, [])]}
        for canonical in REPORT_REQUIRED_SECTIONS
    }


def assess_report_completeness(report_text: str) -> dict[str, Any]:
    headings = extract_report_headings(report_text)
    normalized_aliases = build_normalized_section_aliases()
    missing_sections = [
        section
        for section in REPORT_REQUIRED_SECTIONS
        if not any(heading in normalized_aliases[section] for heading in headings)
    ]
    char_count = len(report_text.strip())
    is_complete = char_count >= REPORT_MIN_CHARS and not missing_sections
    if is_complete:
        return {
            "is_complete": True,
            "failure_kind": None,
            "failure_message": None,
            "missing_sections": [],
            "char_count": char_count,
            "headings": headings,
        }

    reasons: list[str] = []
    if char_count < REPORT_MIN_CHARS:
        reasons.append(f"report too short ({char_count} chars; expected at least {REPORT_MIN_CHARS})")
    if missing_sections:
        reasons.append("missing required sections: " + ", ".join(missing_sections))
    return {
        "is_complete": False,
        "failure_kind": "report_incomplete",
        "failure_message": "; ".join(reasons) or "report incomplete",
        "missing_sections": missing_sections,
        "char_count": char_count,
        "headings": headings,
    }


def estimate_tokens_for_mode(manifest: dict[str, Any], effective_mode: str) -> int:
    stats = manifest.get("stats") or {}
    if effective_mode == "focused_team":
        value = stats.get("focused_estimated_tokens")
    else:
        value = stats.get("included_estimated_tokens")
    if isinstance(value, int):
        return value
    return 0


def should_run_preflight_probe(args: argparse.Namespace, manifest: dict[str, Any], effective_mode: str) -> bool:
    policy = args.preflight_probe
    if policy == "on":
        return True
    if policy == "off":
        return False
    if "opus" in args.model.lower():
        return True
    return estimate_tokens_for_mode(manifest, effective_mode) >= AUTO_PREFLIGHT_TOKEN_THRESHOLD


def run_capability_probe(claude_bin: str, args: argparse.Namespace) -> dict[str, Any]:
    proc = subprocess.run(
        [claude_bin, "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    help_text = "\n".join(part for part in [proc.stdout, proc.stderr] if part)
    checks = [
        {"name": "agents", "supported": "--agents" in help_text, "evidence": "--agents"},
        {"name": "output_format", "supported": "--output-format" in help_text, "evidence": "--output-format"},
        {"name": "model", "supported": "--model" in help_text, "evidence": "--model"},
        {"name": "effort", "supported": "--effort" in help_text, "evidence": "--effort"},
        {"name": "no_chrome", "supported": "--no-chrome" in help_text, "evidence": "--no-chrome"},
        {"name": "resume", "supported": "--resume" in help_text, "evidence": "--resume"},
        {"name": "fork_session", "supported": "--fork-session" in help_text, "evidence": "--fork-session"},
        {"name": "name", "supported": "--name" in help_text, "evidence": "--name"},
        {
            "name": "append_system_prompt_file",
            "supported": "append-system-prompt[-file]" in help_text or "--append-system-prompt-file" in help_text,
            "evidence": "--append-system-prompt-file",
        },
        {
            "name": "append_system_prompt",
            "supported": "append-system-prompt[-file]" in help_text or "--append-system-prompt" in help_text,
            "evidence": "--append-system-prompt",
        },
    ]
    if args.teammate_mode:
        checks.append(
            {
                "name": "teammate_mode",
                "supported": "--teammate-mode" in help_text,
                "evidence": "--teammate-mode",
                "validation": "runtime_or_preflight",
            }
        )

    support_map = {check["name"]: bool(check.get("supported")) for check in checks}
    missing = [
        check["name"]
        for check in checks
        if check["name"] not in {"teammate_mode", "append_system_prompt", "append_system_prompt_file"}
        and check.get("supported") is False
    ]
    system_prompt_mode: str | None
    if support_map.get("append_system_prompt_file"):
        system_prompt_mode = "file"
    elif support_map.get("append_system_prompt"):
        system_prompt_mode = "inline"
    else:
        system_prompt_mode = None
        missing.append("append_system_prompt")
    if proc.returncode != 0 or missing:
        details = classify_failure_kind(proc.returncode, help_text, default_kind="invocation_contract_failed")
        if missing:
            details["failure_message"] = "missing required CLI capabilities: " + ", ".join(missing)
        return {
            "status": "failed",
            "checks": checks,
            "system_prompt_mode": system_prompt_mode,
            **details,
        }

    return {
        "status": "ok",
        "checks": checks,
        "system_prompt_mode": system_prompt_mode,
    }


def build_preflight_command(claude_bin: str, args: argparse.Namespace) -> list[str]:
    cmd = [
        claude_bin,
        "-p",
        "Reply with OK only.",
        "--model",
        args.model,
        "--output-format",
        "json",
        "--no-chrome",
        "--max-turns",
        "1",
    ]
    if args.teammate_mode:
        cmd.extend(["--teammate-mode", args.teammate_mode])
    return cmd


def run_preflight_probe(
    claude_bin: str,
    args: argparse.Namespace,
    repo_root: Path,
    env: dict[str, str],
) -> dict[str, Any]:
    command = build_preflight_command(claude_bin, args)
    proc = subprocess.run(
        command,
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    raw_stdout = (proc.stdout or "").strip()
    stderr_tail = (proc.stderr or "").strip()
    if not raw_stdout:
        details = classify_failure_kind(
            proc.returncode,
            stderr_tail,
            raw_stdout=raw_stdout,
            default_kind="empty_stdout" if proc.returncode == 0 else None,
        )
        return {
            "status": "failed",
            "command": command,
            **details,
        }

    try:
        result_data = json.loads(raw_stdout)
    except json.JSONDecodeError:
        return {
            "status": "failed",
            "command": command,
            **classify_failure_kind(
                proc.returncode,
                stderr_tail,
                raw_stdout=raw_stdout,
                default_kind="invalid_json_output",
            ),
        }

    if proc.returncode != 0 or result_is_error(result_data):
        return {
            "status": "failed",
            "command": command,
            "result": result_data,
            **classify_failure_kind(proc.returncode, stderr_tail, result_data=result_data, raw_stdout=raw_stdout),
        }

    return {
        "status": "ok",
        "command": command,
        "result": result_data,
        "response_text": maybe_extract_result_text(result_data),
    }


def build_followup_command(claude_bin: str, args: argparse.Namespace, session_id: str) -> list[str]:
    cmd = [
        claude_bin,
        "-p",
        FOLLOWUP_REPORT_PROMPT,
        "--resume",
        session_id,
        "--model",
        args.model,
        "--effort",
        args.effort,
        "--output-format",
        "json",
        "--no-chrome",
        "--max-turns",
        str(min(args.max_turns, 30)),
    ]
    if args.teammate_mode:
        cmd.extend(["--teammate-mode", args.teammate_mode])
    return cmd


def run_followup_report(
    claude_bin: str,
    args: argparse.Namespace,
    repo_root: Path,
    env: dict[str, str],
    session_id: str,
) -> dict[str, Any]:
    command = build_followup_command(claude_bin, args, session_id)
    proc = subprocess.run(
        command,
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    raw_stdout = (proc.stdout or "").strip()
    stderr_tail = (proc.stderr or "").strip()
    if not raw_stdout:
        return {
            "status": "failed",
            "command": command,
            **classify_failure_kind(
                proc.returncode,
                stderr_tail,
                raw_stdout=raw_stdout,
                default_kind="empty_stdout" if proc.returncode == 0 else None,
            ),
        }

    try:
        result_data = json.loads(raw_stdout)
    except json.JSONDecodeError:
        return {
            "status": "failed",
            "command": command,
            **classify_failure_kind(
                proc.returncode,
                stderr_tail,
                raw_stdout=raw_stdout,
                default_kind="invalid_json_output",
            ),
        }

    if proc.returncode != 0 or result_is_error(result_data):
        return {
            "status": "failed",
            "command": command,
            "result": result_data,
            **classify_failure_kind(proc.returncode, stderr_tail, result_data=result_data, raw_stdout=raw_stdout),
        }

    report_text = maybe_extract_result_text(result_data)
    quality = assess_report_completeness(report_text)
    if not quality["is_complete"]:
        return {
            "status": "failed",
            "command": command,
            "result": result_data,
            **quality,
        }

    return {
        "status": "ok",
        "command": command,
        "result": result_data,
        "report_text": report_text,
        "report_quality": quality,
    }


def load_last_session_id(manifest_path: Path, manifest: dict[str, Any], out_dir: Path) -> str:
    run_meta_path = find_matching_run_meta_path(
        manifest_path=manifest_path,
        manifest=manifest,
        active_out_dir=out_dir,
        tool_name="claude-code",
    )
    if run_meta_path is None:
        raise SystemExit(
            "No prior Claude Code run metadata matched the manifest run_id. "
            f"Checked active out-dir {out_dir / 'run_meta.json'}"
            " and the matching archived run, if any. Cannot use --resume-last."
        )
    meta = load_json(run_meta_path)
    session_id = meta.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        raise SystemExit(f"run_meta.json does not contain a usable session_id: {run_meta_path}")
    return session_id.strip()


def poll_process(proc: subprocess.Popen[Any], stderr_path: Path) -> int:
    started = monotonic()
    while True:
        code = proc.poll()
        if code is not None:
            return code
        elapsed = int(max(0, monotonic() - started))
        wait_seconds = compute_poll_interval_seconds(elapsed)
        debug(
            f"[info] Claude Code analysis still running after {elapsed // 60}m {elapsed % 60}s. "
            f"Next status check in {wait_seconds}s."
        )
        if stderr_path.exists() and stderr_path.stat().st_size > 0:
            err_tail = tail_text(stderr_path, max_chars=800)
            if err_tail.strip():
                debug("[info] Latest stderr tail:\n" + err_tail)
        sleep(wait_seconds)


def build_command(
    claude_bin: str,
    prompt_text: str,
    system_prompt_path: Path,
    system_prompt_text: str,
    agents_path: Path,
    session_name: str,
    args: argparse.Namespace,
    system_prompt_mode: str = "file",
) -> list[str]:
    agents_json = agents_path.read_text(encoding="utf-8")
    cmd = [
        claude_bin,
        "-p",
        prompt_text,
        "--output-format",
        "json",
        "--model",
        args.model,
        "--effort",
        args.effort,
        "--tools",
        DEFAULTS["tools"],
        "--allowedTools",
        DEFAULTS["allowed_tools"],
        "--agents",
        agents_json,
        "--max-turns",
        str(args.max_turns),
        "--no-chrome",
    ]
    if system_prompt_mode == "inline":
        cmd.extend(["--append-system-prompt", system_prompt_text])
    else:
        cmd.extend(["--append-system-prompt-file", str(system_prompt_path)])
    if args.teammate_mode:
        cmd.extend(["--teammate-mode", args.teammate_mode])
    if args.resume:
        cmd.extend(["--resume", args.resume])
    elif args.continue_latest:
        cmd.append("--continue")
    else:
        cmd.extend(["--name", session_name])
    if args.fork_session:
        cmd.append("--fork-session")
    return cmd


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a read-only local repository analysis using Claude Code CLI agent teams."
    )
    parser.add_argument("--manifest", required=True, help="Path to manifest.json produced by prepare_analysis_context.py")
    parser.add_argument("--goal", default="", help="Analysis goal. Falls back to the manifest goal when omitted.")
    parser.add_argument(
        "--mode",
        choices=["auto", "full_repo_team", "focused_team"],
        default="auto",
        help="Whether to run a broad whole-repo team pass or a focused scoped team pass.",
    )
    parser.add_argument("--model", default=DEFAULTS["model"], help="Lead session model alias or full model name. Default: opus")
    parser.add_argument("--worker-model", default=DEFAULTS["worker_model"], help="Worker teammate model alias or full model name. Default: sonnet")
    parser.add_argument("--effort", default=DEFAULTS["lead_effort"], choices=["low", "medium", "high", "max"], help="Lead effort level.")
    parser.add_argument("--worker-effort", default=DEFAULTS["worker_effort"], choices=["low", "medium", "high", "max"], help="Worker effort level encoded into generated subagents.")
    parser.add_argument("--max-turns", type=int, default=DEFAULTS["max_turns"], help="Maximum agentic turns for the lead session.")
    parser.add_argument("--out-dir", default=DEFAULTS["out_dir"], help="Directory for generated prompts, metadata, and results.")
    parser.add_argument("--resume", default="", help="Resume a specific Claude Code session ID or name.")
    parser.add_argument("--resume-last", action="store_true", help="Resume the session_id saved in the previous run_meta.json in out-dir.")
    parser.add_argument("--continue-latest", action="store_true", help="Use Claude Code's latest session in the current directory.")
    parser.add_argument("--fork-session", action="store_true", help="Fork the resumed/continued session into a new session ID.")
    parser.add_argument(
        "--teammate-mode",
        choices=["auto", "in-process", "tmux"],
        default="",
        help="Optional Claude teammate display mode when agent teams are active.",
    )
    parser.add_argument(
        "--preflight-probe",
        choices=["auto", "on", "off"],
        default="auto",
        help="Whether to run a short Claude preflight probe before the full analysis run.",
    )
    parser.add_argument("--force-security-review", action="store_true", help="Always include the security reviewer role.")
    parser.add_argument("--skip-security-review", action="store_true", help="Never include the security reviewer role.")
    parser.add_argument("--dry-run", action="store_true", help="Generate prompts and metadata but do not launch Claude Code.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.resume_last and args.resume:
        raise SystemExit("Use only one of --resume or --resume-last.")
    if args.resume_last and args.continue_latest:
        raise SystemExit("Use only one of --resume-last or --continue-latest.")
    if args.resume and args.continue_latest:
        raise SystemExit("Use only one of --resume or --continue-latest.")

    manifest_path = Path(args.manifest).resolve()
    manifest = load_json(manifest_path)
    goal = args.goal.strip() or str(manifest.get("goal") or "").strip()
    repo_root = Path(str(manifest.get("repo_root") or ".")).resolve()
    requested_out_dir = Path(args.out_dir).resolve()
    out_dir = resolve_tool_output_dir(
        manifest_path=manifest_path,
        manifest=manifest,
        tool_name="claude-code",
        requested_out_dir=requested_out_dir,
        default_out_dir=Path(DEFAULTS["out_dir"]),
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.resume_last:
        args.resume = load_last_session_id(manifest_path, manifest, out_dir)

    if args.dry_run:
        claude_bin = shutil.which("claude") or "claude"
        claude_version_text = "(not checked: dry-run)"
    else:
        ensure_not_nested()
        claude_bin, claude_version_text = ensure_claude_available(DEFAULTS["minimum_agent_team_version"])

    selected_mode = normalize_mode(args.mode, manifest)
    include_security = should_include_security(goal, manifest, args.force_security_review, args.skip_security_review)
    seed_files = choose_seed_files(manifest, selected_mode.effective)
    repo_tree_path = None
    artifacts = manifest.get("artifacts") or {}
    repo_tree_value = artifacts.get("repo_tree")
    if isinstance(repo_tree_value, str) and repo_tree_value.strip():
        repo_tree_path = Path(repo_tree_value).resolve()

    agents = build_agents(args.worker_model, args.worker_effort, include_security)
    system_prompt_text = build_system_prompt(
        manifest_path=manifest_path,
        repo_tree_path=repo_tree_path,
        goal=goal,
        effective_mode=selected_mode.effective,
        include_security=include_security,
        seed_files=seed_files,
    )
    user_prompt_text = build_user_prompt(
        goal=goal,
        manifest=manifest,
        mode=selected_mode,
        include_security=include_security,
        seed_files=seed_files,
    )

    agents_path = out_dir / "claude-agents.json"
    system_prompt_path = out_dir / "claude-system-prompt.md"
    user_prompt_path = out_dir / "claude-user-prompt.txt"
    write_text(agents_path, json.dumps(agents, indent=2, ensure_ascii=False))
    write_text(system_prompt_path, system_prompt_text)
    write_text(user_prompt_path, user_prompt_text)

    session_name = f"codebase-analysis-{repo_root.name}"
    if goal:
        compact_goal = re.sub(r"[^\w-]+", "-", goal, flags=re.UNICODE).strip("-")
        if compact_goal:
            session_name += "-" + compact_goal[:40]

    capability_probe: dict[str, Any] | None = None
    system_prompt_mode = "file"
    if not args.dry_run:
        capability_probe = run_capability_probe(claude_bin, args)
        system_prompt_mode = capability_probe.get("system_prompt_mode") or "file"

    command = build_command(
        claude_bin=claude_bin,
        prompt_text=user_prompt_text,
        system_prompt_path=system_prompt_path,
        system_prompt_text=system_prompt_text,
        agents_path=agents_path,
        session_name=session_name,
        args=args,
        system_prompt_mode=system_prompt_mode,
    )

    request_meta = {
        "transport": "claude_code_cli_local",
        "manifest": str(manifest_path),
        "run_id": manifest.get("run_id"),
        "repo_root": str(repo_root),
        "goal": goal,
        "requested_mode": selected_mode.requested,
        "effective_mode": selected_mode.effective,
        "preparation_recommendation": manifest.get("mode_recommendation"),
        "legacy_packaging_recommendation": selected_mode.packaging_recommendation,
        "model": args.model,
        "worker_model": args.worker_model,
        "lead_effort": args.effort,
        "worker_effort": args.worker_effort,
        "max_turns": args.max_turns,
        "claude_version": claude_version_text,
        "include_security_reviewer": include_security,
        "seed_files": seed_files,
        "repo_tree_path": str(repo_tree_path) if repo_tree_path else None,
        "system_prompt_path": str(system_prompt_path),
        "system_prompt_mode": system_prompt_mode,
        "user_prompt_path": str(user_prompt_path),
        "agents_path": str(agents_path),
        "command": command,
        "adaptive_poll_schedule_seconds": {
            "under_30m": 300,
            "30_to_under_40m": 150,
            "40_to_under_50m": 90,
            "50m_plus": 30,
        },
        "resumed_session": bool(args.resume),
        "resume_value": args.resume or None,
        "continue_latest": bool(args.continue_latest),
        "fork_session": bool(args.fork_session),
        "teammate_mode": args.teammate_mode or None,
        "preflight_probe_policy": args.preflight_probe,
        "agent_team_activation": "env_and_prompt",
        "read_only_analysis": True,
        "dry_run": bool(args.dry_run),
    }
    request_meta_path = out_dir / "request_meta.json"
    run_meta_path = out_dir / "run_meta.json"
    status_path = out_dir / "analysis-status.json"
    save_json(request_meta_path, request_meta)

    run_meta = dict(request_meta)
    analysis_status = {
        "status": "preparing",
        "failure_kind": None,
        "failure_message": None,
        "run_id": manifest.get("run_id"),
        "session_id": None,
        "reported_reset_time": None,
        "stdout_path": None,
        "stderr_path": None,
        "analysis_result_path": None,
        "analysis_report_path": None,
        "analysis_report_partial_path": None,
        "auto_followup_used": False,
    }
    persist_metadata(run_meta_path, run_meta, status_path, analysis_status)

    if args.dry_run:
        run_meta.update({"status": "dry_run"})
        analysis_status.update({"status": "dry_run"})
        persist_metadata(run_meta_path, run_meta, status_path, analysis_status)
        print(json.dumps(request_meta, indent=2, ensure_ascii=False))
        return 0

    stdout_path = out_dir / "claude-stdout.json"
    stderr_path = out_dir / "claude-stderr.log"
    for path in (stdout_path, stderr_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.setdefault("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS", "1")
    env.setdefault("CLAUDE_CODE_ENABLE_TASKS", "1")
    env.setdefault("CLAUDE_CODE_SUBPROCESS_ENV_SCRUB", "1")

    if capability_probe is None:
        capability_probe = {"status": "not_run"}
    request_meta["capability_probe"] = capability_probe
    run_meta["capability_probe"] = capability_probe
    analysis_status["capability_probe"] = capability_probe
    save_json(request_meta_path, request_meta)
    persist_metadata(run_meta_path, run_meta, status_path, analysis_status)
    if capability_probe["status"] != "ok":
        analysis_status.update(
            {
                "status": "failed",
                "failure_kind": capability_probe["failure_kind"],
                "failure_message": capability_probe["failure_message"],
            }
        )
        run_meta.update(
            {
                "status": "failed",
                "failure_kind": capability_probe["failure_kind"],
                "failure_message": capability_probe["failure_message"],
            }
        )
        persist_metadata(run_meta_path, run_meta, status_path, analysis_status)
        raise SystemExit(capability_probe["failure_message"])

    preflight_probe: dict[str, Any] | None = None
    if should_run_preflight_probe(args, manifest, selected_mode.effective):
        preflight_probe = run_preflight_probe(claude_bin, args, repo_root, env)
        request_meta["preflight_probe"] = preflight_probe
        run_meta["preflight_probe"] = preflight_probe
        analysis_status["preflight_probe"] = preflight_probe
        save_json(request_meta_path, request_meta)
        persist_metadata(run_meta_path, run_meta, status_path, analysis_status)
        if preflight_probe["status"] != "ok":
            analysis_status.update(
                {
                    "status": "failed",
                    "failure_kind": preflight_probe["failure_kind"],
                    "failure_message": preflight_probe["failure_message"],
                    "reported_reset_time": preflight_probe.get("reported_reset_time"),
                }
            )
            run_meta.update(
                {
                    "status": "failed",
                    "failure_kind": preflight_probe["failure_kind"],
                    "failure_message": preflight_probe["failure_message"],
                    "reported_reset_time": preflight_probe.get("reported_reset_time"),
                }
            )
            persist_metadata(run_meta_path, run_meta, status_path, analysis_status)
            raise SystemExit(preflight_probe["failure_message"])
    else:
        preflight_probe = {"status": "skipped", "policy": args.preflight_probe}
        request_meta["preflight_probe"] = preflight_probe
        run_meta["preflight_probe"] = preflight_probe
        analysis_status["preflight_probe"] = preflight_probe
        save_json(request_meta_path, request_meta)
        persist_metadata(run_meta_path, run_meta, status_path, analysis_status)

    debug(f"[info] Launching Claude Code in {repo_root}")
    debug("[info] Local agent-team analysis is running in read-only mode.")
    analysis_status["status"] = "running"
    persist_metadata(run_meta_path, run_meta, status_path, analysis_status)

    with stdout_path.open("w", encoding="utf-8") as stdout_fh, stderr_path.open("w", encoding="utf-8") as stderr_fh:
        proc = subprocess.Popen(
            command,
            cwd=str(repo_root),
            stdout=stdout_fh,
            stderr=stderr_fh,
            text=True,
            env=env,
        )
        return_code = poll_process(proc, stderr_path)

    raw_stdout = stdout_path.read_text(encoding="utf-8", errors="replace").strip()
    stderr_tail = tail_text(stderr_path)
    run_meta.update(
        {
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
        }
    )
    analysis_status.update(
        {
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
        }
    )
    if return_code != 0:
        details = classify_failure_kind(return_code, stderr_tail, raw_stdout=raw_stdout)
        run_meta.update({"status": "failed", **details})
        analysis_status.update({"status": "failed", **details})
        persist_metadata(run_meta_path, run_meta, status_path, analysis_status)
        raise SystemExit(
            "Claude Code analysis failed with exit code "
            f"{return_code}.\nStderr tail:\n{stderr_tail or '(none)'}\n"
            f"Raw stdout saved at: {stdout_path}"
        )
    if not raw_stdout:
        details = classify_failure_kind(return_code, stderr_tail, raw_stdout=raw_stdout, default_kind="empty_stdout")
        run_meta.update({"status": "failed", **details})
        analysis_status.update({"status": "failed", **details})
        persist_metadata(run_meta_path, run_meta, status_path, analysis_status)
        raise SystemExit(
            f"Claude Code analysis finished with no stdout output. Check {stderr_path} for details."
        )

    try:
        result_data = json.loads(raw_stdout)
    except json.JSONDecodeError as exc:
        details = classify_failure_kind(return_code, stderr_tail, raw_stdout=raw_stdout, default_kind="invalid_json_output")
        run_meta.update({"status": "failed", **details})
        analysis_status.update({"status": "failed", **details})
        persist_metadata(run_meta_path, run_meta, status_path, analysis_status)
        raise SystemExit(
            f"Claude Code stdout was not valid JSON: {exc}\nRaw output saved at: {stdout_path}\n"
            f"Stderr tail:\n{stderr_tail or '(none)'}"
        ) from exc

    session_id = maybe_extract_session_id(result_data)
    result_path = out_dir / "analysis-result.json"
    report_path = out_dir / "analysis-report.md"
    save_json(result_path, result_data)
    report_text = maybe_extract_result_text(result_data)
    report_quality = assess_report_completeness(report_text)

    run_meta.update(
        {
            "session_id": session_id,
            "analysis_result_path": str(result_path),
            "analysis_report_path": str(report_path) if report_quality["is_complete"] else None,
            "analysis_error": result_is_error(result_data),
            "report_quality": report_quality,
        }
    )
    analysis_status.update(
        {
            "session_id": session_id,
            "analysis_result_path": str(result_path),
            "analysis_report_path": str(report_path) if report_quality["is_complete"] else None,
        }
    )

    if result_is_error(result_data):
        details = classify_failure_kind(return_code, stderr_tail, result_data=result_data, raw_stdout=raw_stdout)
        run_meta.update({"status": "failed", **details})
        analysis_status.update({"status": "failed", **details})
        persist_metadata(run_meta_path, run_meta, status_path, analysis_status)
        raise SystemExit(
            "Claude Code returned an error result.\n"
            f"Reported result: {details['failure_message']}\n"
            f"Saved JSON: {result_path}\n"
            f"Stderr tail:\n{stderr_tail or '(none)'}"
        )

    auto_followup_used = False
    if not report_quality["is_complete"]:
        followup_result: dict[str, Any] | None = None
        if session_id:
            auto_followup_used = True
            followup_result = run_followup_report(claude_bin, args, repo_root, env, session_id)
            run_meta["auto_followup_used"] = True
            analysis_status["auto_followup_used"] = True
        if followup_result and followup_result["status"] == "ok":
            final_result = followup_result["result"]
            final_report_text = followup_result["report_text"]
            final_report_quality = followup_result["report_quality"]
            final_session_id = maybe_extract_session_id(final_result) or session_id
            save_json(result_path, final_result)
            write_text(report_path, final_report_text)
            run_meta.update(
                {
                    "status": "succeeded",
                    "session_id": final_session_id,
                    "analysis_result_path": str(result_path),
                    "analysis_report_path": str(report_path),
                    "analysis_report_partial_path": None,
                    "analysis_error": False,
                    "report_quality": final_report_quality,
                }
            )
            analysis_status.update(
                {
                    "status": "succeeded",
                    "session_id": final_session_id,
                    "analysis_result_path": str(result_path),
                    "analysis_report_path": str(report_path),
                    "analysis_report_partial_path": None,
                    "failure_kind": None,
                    "failure_message": None,
                }
            )
            persist_metadata(run_meta_path, run_meta, status_path, analysis_status)
            print(
                json.dumps(
                    {
                        "transport": "claude_code_cli_local",
                        "manifest": str(manifest_path),
                        "repo_root": str(repo_root),
                        "effective_mode": selected_mode.effective,
                        "model": args.model,
                        "worker_model": args.worker_model,
                        "session_id": final_session_id,
                        "analysis_result_path": str(result_path),
                        "analysis_report_path": str(report_path),
                        "stdout_path": str(stdout_path),
                        "stderr_path": str(stderr_path),
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 0

        partial_report_path = out_dir / "analysis-report.partial.md"
        write_text(partial_report_path, report_text)
        failure_message = report_quality["failure_message"]
        if followup_result and followup_result["status"] != "ok":
            failure_message = f"{failure_message}; follow-up failed: {followup_result['failure_message']}"
        run_meta.update(
            {
                "status": "failed",
                "failure_kind": "report_incomplete",
                "failure_message": failure_message,
                "analysis_report_partial_path": str(partial_report_path),
                "analysis_report_path": None,
                "report_quality": report_quality,
            }
        )
        analysis_status.update(
            {
                "status": "failed",
                "failure_kind": "report_incomplete",
                "failure_message": failure_message,
                "analysis_report_path": None,
                "analysis_report_partial_path": str(partial_report_path),
            }
        )
        persist_metadata(run_meta_path, run_meta, status_path, analysis_status)
        raise SystemExit(failure_message)

    write_text(report_path, report_text)
    run_meta.update(
        {
            "status": "succeeded",
            "analysis_report_path": str(report_path),
            "auto_followup_used": auto_followup_used,
        }
    )
    analysis_status.update(
        {
            "status": "succeeded",
            "analysis_report_path": str(report_path),
            "auto_followup_used": auto_followup_used,
        }
    )
    persist_metadata(run_meta_path, run_meta, status_path, analysis_status)

    print(
        json.dumps(
            {
                "transport": "claude_code_cli_local",
                "manifest": str(manifest_path),
                "repo_root": str(repo_root),
                "effective_mode": selected_mode.effective,
                "model": args.model,
                "worker_model": args.worker_model,
                "session_id": session_id,
                "analysis_result_path": str(result_path),
                "analysis_report_path": str(report_path),
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
