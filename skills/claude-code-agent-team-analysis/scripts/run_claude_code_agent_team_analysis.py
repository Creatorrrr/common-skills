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
from typing import Any, Callable

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
TEAM_SIGNAL_SCHEMA_VERSION = 1
TEAM_PLAN_SCHEMA_VERSION = 1
DEFAULT_REPORT_SECTIONS = [
    "scope and assumptions",
    "short system map",
    "top findings",
    "evidence",
    "confirmed facts vs inference or uncertainty",
    "correctness risks",
    "team evolution",
    "suggested next design steps",
]
ROLE_REPORT_SECTION_MAP = {
    "tests-refactor-reviewer": "test-gap recommendations",
    "performance-reviewer": "performance review",
    "security-reviewer": "security review",
    "api-contract-reviewer": "api contract review",
    "data-model-reviewer": "data model review",
    "infra-release-reviewer": "infra or release review",
    "frontend-workflow-reviewer": "frontend workflow review",
    "dependency-config-reviewer": "dependency or config review",
}
ROLE_PATH_SIGNAL_MAP = {
    "api-contract-reviewer": "api",
    "data-model-reviewer": "data",
    "infra-release-reviewer": "infra",
    "frontend-workflow-reviewer": "frontend",
    "dependency-config-reviewer": "config",
}
REPORT_SECTION_HEADINGS = {
    "scope and assumptions": "Scope and assumptions",
    "short system map": "Short system map",
    "top findings": "Top findings",
    "evidence": "Evidence",
    "confirmed facts vs inference or uncertainty": "Confirmed facts vs inference or uncertainty",
    "correctness risks": "Correctness risks",
    "team evolution": "Team Evolution",
    "test-gap recommendations": "Test-gap recommendations",
    "performance review": "Performance review",
    "security review": "Security review",
    "api contract review": "API contract review",
    "data model review": "Data model review",
    "infra or release review": "Infra or release review",
    "frontend workflow review": "Frontend workflow review",
    "dependency or config review": "Dependency or config review",
    "suggested next design steps": "Suggested next design steps",
}
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
    "correctness risks": [
        "correctness risks",
        "correctness risk",
        "workflow correctness risks",
        "correctness and workflow risks",
    ],
    "team evolution": [
        "team evolution",
        "team changes",
        "runtime team evolution",
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
    "performance review": [
        "performance review",
        "performance risks",
        "performance analysis",
    ],
    "security review": [
        "security review",
        "security risks",
        "security analysis",
    ],
    "api contract review": [
        "api contract review",
        "api contracts review",
        "api boundary review",
    ],
    "data model review": [
        "data model review",
        "schema review",
        "persistence review",
    ],
    "infra or release review": [
        "infra or release review",
        "infra review",
        "release review",
        "infra and release review",
    ],
    "frontend workflow review": [
        "frontend workflow review",
        "frontend review",
        "workflow review",
    ],
    "dependency or config review": [
        "dependency or config review",
        "dependency review",
        "config review",
        "dependency and config review",
    ],
    "suggested next design steps": [
        "suggested next design steps",
        "next design steps",
        "suggested next steps",
    ],
}
MARKDOWN_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
BOLD_HEADING_RE = re.compile(r"^\s*(?:\*\*|__)(.+?)(?:\*\*|__)\s*$")
LEADING_NUMBER_RE = re.compile(r"^\(?\d+\)?[.)]?\s+")

SECURITY_HINT_RE = re.compile(
    r"\b(auth|oauth|token|secret|credential|password|permission|rbac|acl|iam|session|cookie|jwt|"
    r"payment|billing|checkout|admin|csrf|xss|ssrf|webhook|public api|external api|encrypt|decrypt|"
    r"security|login|signup)\b",
    re.IGNORECASE,
)
TEST_HINT_RE = re.compile(r"\b(test|tests|coverage|flaky|refactor|quality|regression)\b", re.IGNORECASE)
PERFORMANCE_HINT_RE = re.compile(
    r"\b(performance|latency|throughput|scale|scaling|hot path|cache|caching|n\+1|memory|async|concurrency)\b",
    re.IGNORECASE,
)
ROLE_HINT_PATTERNS = {
    "api-contract-reviewer": re.compile(
        r"\b(api|contract|contracts|endpoint|endpoints|graphql|rest|request|response|openapi)\b",
        re.IGNORECASE,
    ),
    "data-model-reviewer": re.compile(
        r"\b(data model|schema|schemas|migration|migrations|database|datastore|sql|orm|entity|entities|persistence)\b",
        re.IGNORECASE,
    ),
    "infra-release-reviewer": re.compile(
        r"\b(ci|cd|release|releases|deploy|deployment|pipeline|pipelines|workflow|workflows|buildkite|github actions)\b",
        re.IGNORECASE,
    ),
    "frontend-workflow-reviewer": re.compile(
        r"\b(frontend|ui|ux|checkout|screen|route|component|components|browser|client-side)\b",
        re.IGNORECASE,
    ),
    "dependency-config-reviewer": re.compile(
        r"\b(dependency|dependencies|package|packages|lockfile|lockfiles|config|configuration|toolchain|build config)\b",
        re.IGNORECASE,
    ),
}
TEAM_CONFIG_SCHEMA_VERSION = 1
COMMON_AGENT_TOOLS = ["Read", "Glob", "Grep", "LSP", "Bash"]
ALLOWED_AGENT_TOOLS = set(COMMON_AGENT_TOOLS)
DEFAULT_TEAM_MAX_SIZE = 5
DEFAULT_TEAM_ROLE_ORDER = [
    "architecture-mapper",
    "correctness-gap-reviewer",
    "tests-refactor-reviewer",
    "performance-reviewer",
]
AUTO_REQUIRED_ROLE_ORDER = [
    "architecture-mapper",
    "correctness-gap-reviewer",
]
TEAM_CONFIG_TOP_LEVEL_KEYS = {"schema_version", "strategy", "agents", "lead"}
TEAM_CONFIG_LEAD_KEYS = {"recommended_roles", "extra_instructions"}
AGENT_SPEC_OPTIONAL_KEYS = {"model", "effort"}
AGENT_SPEC_REQUIRED_KEYS = {"description", "tools", "prompt"}
AGENT_SPEC_ALLOWED_KEYS = AGENT_SPEC_REQUIRED_KEYS | AGENT_SPEC_OPTIONAL_KEYS
PLANNER_REQUIRED_KEYS = {
    "selected_roles",
    "ranked_alternates",
    "selection_reasons",
    "signals_used",
    "soft_cap_warning",
    "lead_guidance",
    "report_sections",
}


@dataclass
class SelectedMode:
    requested: str
    effective: str
    packaging_recommendation: str | None


class ClaudeCommandError(RuntimeError):
    pass


class PlannerValidationError(RuntimeError):
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


def build_output_requirements() -> list[str]:
    return [
        "Use concise markdown.",
        "For every important finding, include file paths and line references when available.",
        "Separate confirmed findings from inference and unknowns.",
        "Prioritize actionable engineering conclusions over generic advice.",
    ]


def build_role_catalog(worker_model: str, worker_effort: str) -> dict[str, dict[str, Any]]:
    output_requirements = [
        *build_output_requirements(),
    ]
    return {
        "architecture-mapper": {
            "description": "Maps module boundaries, entrypoints, major workflows, and cross-layer coupling for repository analysis.",
            "tools": list(COMMON_AGENT_TOOLS),
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
            "tools": list(COMMON_AGENT_TOOLS),
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
            "tools": list(COMMON_AGENT_TOOLS),
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
            "tools": list(COMMON_AGENT_TOOLS),
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
        "security-reviewer": {
            "description": "Audits auth, authorization, secrets, input handling, external interfaces, and security-sensitive configuration.",
            "tools": list(COMMON_AGENT_TOOLS),
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
        },
        "api-contract-reviewer": {
            "description": "Reviews API contracts, request and response assumptions, boundary compatibility, and public interface drift.",
            "tools": list(COMMON_AGENT_TOOLS),
            "model": worker_model,
            "effort": worker_effort,
            "prompt": build_worker_prompt(
                "api contract reviewer",
                [
                    "Public or internal API boundaries, request and response contracts, and compatibility assumptions.",
                    "Schema or payload drift between producers and consumers.",
                    "Validation gaps, error-shape inconsistencies, and unclear contract ownership.",
                    "Only make claims grounded in visible code, types, and nearby docs or config.",
                ],
                output_requirements,
            ),
        },
        "data-model-reviewer": {
            "description": "Reviews schema, persistence, migrations, and data ownership or lifecycle risks.",
            "tools": list(COMMON_AGENT_TOOLS),
            "model": worker_model,
            "effort": worker_effort,
            "prompt": build_worker_prompt(
                "data model reviewer",
                [
                    "Schema boundaries, entity ownership, and data-flow assumptions across modules.",
                    "Migration risks, backward compatibility, and persistence-layer coupling.",
                    "Places where naming, typing, or lifecycle rules are ambiguous or drift-prone.",
                    "Focus on visible data-shape risk rather than hypothetical redesigns.",
                ],
                output_requirements,
            ),
        },
        "infra-release-reviewer": {
            "description": "Reviews CI, build, deployment, release, and operational workflow risk.",
            "tools": list(COMMON_AGENT_TOOLS),
            "model": worker_model,
            "effort": worker_effort,
            "prompt": build_worker_prompt(
                "infra and release reviewer",
                [
                    "CI workflow shape, release/build steps, and deployment assumptions visible in config or scripts.",
                    "Gaps between build, test, packaging, and release enforcement.",
                    "Operational drift between documented and configured workflows.",
                    "Only flag release risks supported by repository evidence.",
                ],
                output_requirements,
            ),
        },
        "frontend-workflow-reviewer": {
            "description": "Reviews user-facing workflow composition, route/state transitions, and frontend integration seams.",
            "tools": list(COMMON_AGENT_TOOLS),
            "model": worker_model,
            "effort": worker_effort,
            "prompt": build_worker_prompt(
                "frontend workflow reviewer",
                [
                    "User-visible routes, screens, state transitions, and integration seams.",
                    "Mismatch risks between frontend orchestration and backend or config expectations.",
                    "Places where component ownership or workflow handoff is unclear.",
                    "Ground conclusions in visible routes, components, handlers, and tests.",
                ],
                output_requirements,
            ),
        },
        "dependency-config-reviewer": {
            "description": "Reviews dependency, config, toolchain, and environment drift that can distort workflow reliability.",
            "tools": list(COMMON_AGENT_TOOLS),
            "model": worker_model,
            "effort": worker_effort,
            "prompt": build_worker_prompt(
                "dependency and config reviewer",
                [
                    "Dependency declarations, version drift, lockfile implications, and missing package ownership.",
                    "Configuration mismatches across environments, tools, and workflow entrypoints.",
                    "Toolchain or build config assumptions that can make analysis conclusions misleading.",
                    "Focus on dependency or config evidence with clear engineering impact.",
                ],
                output_requirements,
            ),
        },
    }

def clone_agent_spec(spec: dict[str, Any]) -> dict[str, Any]:
    cloned = dict(spec)
    cloned["tools"] = list(spec.get("tools") or [])
    return cloned


def ordered_agents(role_names: list[str], catalog: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {name: clone_agent_spec(catalog[name]) for name in role_names}


def build_default_agents(worker_model: str, worker_effort: str, include_security: bool) -> dict[str, dict[str, Any]]:
    catalog = build_role_catalog(worker_model, worker_effort)
    role_names = list(DEFAULT_TEAM_ROLE_ORDER)
    if include_security:
        role_names.append("security-reviewer")
    return ordered_agents(role_names, catalog)


def build_report_sections_for_roles(role_names: list[str]) -> list[str]:
    sections = list(DEFAULT_REPORT_SECTIONS)
    for role_name in role_names:
        section = ROLE_REPORT_SECTION_MAP.get(role_name)
        if section and section not in sections:
            sections.append(section)
    return sections


def report_heading_lines(report_sections: list[str]) -> str:
    return "\n".join(f"## {REPORT_SECTION_HEADINGS[section]}" for section in report_sections)


def build_followup_report_prompt(report_sections: list[str]) -> str:
    heading_lines = report_heading_lines(report_sections)
    return textwrap.dedent(
        f"""
        Using the repository evidence already gathered in this resumed session, write the full consolidated report now.
        Do not redo the whole exploration unless absolutely necessary.
        Use these exact markdown H2 headings, verbatim:
        {heading_lines}
        Put the relevant content under each heading.
        Keep it evidence-first and concise but complete. Return markdown only.
        """
    ).strip()


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def parse_team_request_text(goal: str, manifest: dict[str, Any], team_request: str) -> str:
    parts = [goal, team_request]
    parts.extend(str(item) for item in manifest.get("scope") or [])
    parts.extend(str(item) for item in manifest.get("keywords") or [])
    return "\n".join(part for part in parts if part).strip()


def active_selection_key(effective_mode: str) -> str:
    return "focused_selection" if effective_mode == "focused_team" else "full_selection"


def build_runtime_team_signals(goal: str, team_request: str, manifest: dict[str, Any], effective_mode: str) -> dict[str, Any]:
    manifest_signals = manifest.get("team_signals") or {}
    selection = manifest_signals.get(active_selection_key(effective_mode)) or {}
    repo_flags = manifest_signals.get("repo_flags") or {}
    selection_paths = list(selection.get("sample_paths") or [])
    text_parts = [goal, team_request]
    text_parts.extend(str(item) for item in manifest.get("scope") or [])
    text_parts.extend(str(item) for item in manifest.get("keywords") or [])
    text_parts.extend(selection_paths)
    text_haystack = "\n".join(part for part in text_parts if part).strip()

    derived_flags = {
        "security_signal": bool(SECURITY_HINT_RE.search(text_haystack)) or bool(repo_flags.get("has_security_sensitive_paths")),
        "test_signal": bool(TEST_HINT_RE.search(text_haystack)) or bool((selection.get("path_signals") or {}).get("tests")),
        "performance_signal": bool(PERFORMANCE_HINT_RE.search(text_haystack)),
    }
    return {
        "schema_version": TEAM_SIGNAL_SCHEMA_VERSION,
        "goal": goal,
        "team_request": team_request or None,
        "effective_mode": effective_mode,
        "scope": list(manifest.get("scope") or []),
        "keywords": list(manifest.get("keywords") or []),
        "repo_flags": repo_flags,
        "active_selection": selection,
        "full_selection": manifest_signals.get("full_selection") or {},
        "focused_selection": manifest_signals.get("focused_selection") or {},
        "derived_flags": derived_flags,
        "text_signal_haystack": text_haystack,
    }


def should_include_security(runtime_signals: dict[str, Any], force: bool, skip: bool) -> bool:
    if skip:
        return False
    if force:
        return True
    return bool((runtime_signals.get("derived_flags") or {}).get("security_signal"))


def build_default_selection_reasons(include_security: bool) -> dict[str, list[str]]:
    reasons = {
        "architecture-mapper": ["Default team baseline."],
        "correctness-gap-reviewer": ["Default team baseline."],
        "tests-refactor-reviewer": ["Default team baseline."],
        "performance-reviewer": ["Default team baseline."],
    }
    if include_security:
        reasons["security-reviewer"] = ["Included because the unified team signals look security-sensitive."]
    return reasons


def normalize_agent_spec(name: str, raw_spec: dict[str, Any], worker_model: str, worker_effort: str) -> dict[str, Any]:
    if not isinstance(raw_spec, dict):
        raise SystemExit(f"Agent '{name}' must be an object.")
    unknown_keys = sorted(set(raw_spec) - AGENT_SPEC_ALLOWED_KEYS)
    if unknown_keys:
        raise SystemExit(f"Agent '{name}' has unsupported fields: {', '.join(unknown_keys)}")
    missing = sorted(key for key in AGENT_SPEC_REQUIRED_KEYS if key not in raw_spec)
    if missing:
        raise SystemExit(f"Agent '{name}' is missing required fields: {', '.join(missing)}")
    description = raw_spec["description"]
    prompt = raw_spec["prompt"]
    tools = raw_spec["tools"]
    if not isinstance(description, str) or not description.strip():
        raise SystemExit(f"Agent '{name}' requires a non-empty string description.")
    if not isinstance(prompt, str) or not prompt.strip():
        raise SystemExit(f"Agent '{name}' requires a non-empty string prompt.")
    if not isinstance(tools, list) or not tools or any(not isinstance(item, str) or not item.strip() for item in tools):
        raise SystemExit(f"Agent '{name}' requires a non-empty string list for tools.")
    normalized_tools = [item.strip() for item in tools]
    invalid_tools = [tool for tool in normalized_tools if tool not in ALLOWED_AGENT_TOOLS]
    if invalid_tools:
        raise SystemExit(
            f"Agent '{name}' uses unsupported tools: {', '.join(invalid_tools)}. "
            f"Allowed tools: {', '.join(sorted(ALLOWED_AGENT_TOOLS))}"
        )
    model = raw_spec.get("model", worker_model)
    effort = raw_spec.get("effort", worker_effort)
    if not isinstance(model, str) or not model.strip():
        raise SystemExit(f"Agent '{name}' requires a non-empty string model when provided.")
    if effort not in {"low", "medium", "high", "max"}:
        raise SystemExit(f"Agent '{name}' has invalid effort '{effort}'.")
    return {
        "description": description.strip(),
        "tools": normalized_tools,
        "model": model.strip(),
        "effort": effort,
        "prompt": prompt.strip(),
    }


def load_team_config(team_config_path: Path, worker_model: str, worker_effort: str) -> dict[str, Any]:
    if not team_config_path.exists():
        raise SystemExit(f"Team config file does not exist: {team_config_path}")
    raw_text = team_config_path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Team config is not valid JSON: {team_config_path}\n{exc}") from exc
    if not isinstance(data, dict) or not data:
        raise SystemExit(f"Team config must be a non-empty JSON object: {team_config_path}")

    if "agents" in data:
        unknown_top_level = sorted(set(data) - TEAM_CONFIG_TOP_LEVEL_KEYS)
        if unknown_top_level:
            raise SystemExit(f"Team config has unsupported top-level fields: {', '.join(unknown_top_level)}")
        schema_version = data.get("schema_version", TEAM_CONFIG_SCHEMA_VERSION)
        if schema_version != TEAM_CONFIG_SCHEMA_VERSION:
            raise SystemExit(f"Unsupported team config schema_version: {schema_version}")
        strategy = data.get("strategy", "merge")
        if strategy not in {"merge", "replace"}:
            raise SystemExit(f"Unsupported team config strategy: {strategy}")
        agents_data = data.get("agents")
        if not isinstance(agents_data, dict) or not agents_data:
            raise SystemExit("Wrapped team config requires a non-empty 'agents' object.")
        lead = data.get("lead") or {}
        if not isinstance(lead, dict):
            raise SystemExit("Wrapped team config 'lead' must be an object when provided.")
        unknown_lead_keys = sorted(set(lead) - TEAM_CONFIG_LEAD_KEYS)
        if unknown_lead_keys:
            raise SystemExit(f"Wrapped team config lead has unsupported fields: {', '.join(unknown_lead_keys)}")
        recommended_roles = lead.get("recommended_roles") or []
        if not isinstance(recommended_roles, list) or any(not isinstance(item, str) or not item.strip() for item in recommended_roles):
            raise SystemExit("lead.recommended_roles must be a list of non-empty strings.")
        extra_instructions = lead.get("extra_instructions") or []
        if not isinstance(extra_instructions, list) or any(not isinstance(item, str) or not item.strip() for item in extra_instructions):
            raise SystemExit("lead.extra_instructions must be a list of non-empty strings.")
        normalized_agents = {
            name: normalize_agent_spec(name, spec, worker_model, worker_effort)
            for name, spec in agents_data.items()
        }
        return {
            "format": "wrapped",
            "strategy": strategy,
            "agents": normalized_agents,
            "lead": {
                "recommended_roles": [item.strip() for item in recommended_roles],
                "extra_instructions": [item.strip() for item in extra_instructions],
            },
            "raw_text": raw_text,
        }
    ambiguous_keys = TEAM_CONFIG_TOP_LEVEL_KEYS & set(data)
    if ambiguous_keys:
        raise SystemExit(
            "Ambiguous team config shape. Wrapped configs require an 'agents' object; "
            f"bare configs cannot use reserved top-level keys: {', '.join(sorted(ambiguous_keys))}"
        )

    normalized_agents = {
        name: normalize_agent_spec(name, spec, worker_model, worker_effort)
        for name, spec in data.items()
    }
    return {
        "format": "bare",
        "strategy": "replace",
        "agents": normalized_agents,
        "lead": {
            "recommended_roles": [],
            "extra_instructions": [],
        },
        "raw_text": raw_text,
    }


def apply_security_policy(
    agents: dict[str, dict[str, Any]],
    catalog: dict[str, dict[str, Any]],
    include_security: bool,
    force_security_review: bool,
    skip_security_review: bool,
    selection_reasons: dict[str, list[str]],
) -> None:
    if skip_security_review:
        agents.pop("security-reviewer", None)
        selection_reasons.pop("security-reviewer", None)
        return
    if force_security_review and "security-reviewer" not in agents:
        agents["security-reviewer"] = clone_agent_spec(catalog["security-reviewer"])
        selection_reasons["security-reviewer"] = ["Forced by --force-security-review."]
        return
    if include_security and "security-reviewer" not in agents:
        agents["security-reviewer"] = clone_agent_spec(catalog["security-reviewer"])
        selection_reasons["security-reviewer"] = ["Selected because the unified team signals look security-sensitive."]

def build_heuristic_team_plan(
    catalog: dict[str, dict[str, Any]],
    runtime_signals: dict[str, Any],
    team_max_size: int,
) -> dict[str, Any]:
    haystack = runtime_signals.get("text_signal_haystack") or ""
    active_selection = runtime_signals.get("active_selection") or {}
    repo_flags = runtime_signals.get("repo_flags") or {}
    path_signals = active_selection.get("path_signals") or {}
    derived_flags = runtime_signals.get("derived_flags") or {}
    selection_reasons: dict[str, list[str]] = {
        "architecture-mapper": ["Always include the architecture mapper as a core default role."],
        "correctness-gap-reviewer": ["Always include the correctness-gap reviewer as a core default role."],
    }
    scored_candidates: list[tuple[int, int, str, list[str]]] = []

    def add_candidate(name: str, score: int, reasons: list[str], priority: int) -> None:
        if reasons:
            scored_candidates.append((score, priority, name, reasons))

    if derived_flags.get("test_signal"):
        add_candidate(
            "tests-refactor-reviewer",
            80 + int(path_signals.get("tests", 0)),
            ["Matched test/refactor signals in the request or active selection."],
            10,
        )
    if derived_flags.get("performance_signal"):
        add_candidate("performance-reviewer", 70, ["Matched performance or scale signals in the request."], 20)
    if derived_flags.get("security_signal"):
        add_candidate(
            "security-reviewer",
            90 + int(path_signals.get("security_sensitive", 0)),
            ["Matched security-sensitive signals from the request or repository cues."],
            30,
        )
    for priority, role_name in enumerate(
        [
            "api-contract-reviewer",
            "data-model-reviewer",
            "infra-release-reviewer",
            "frontend-workflow-reviewer",
            "dependency-config-reviewer",
        ],
        start=40,
    ):
        pattern = ROLE_HINT_PATTERNS[role_name]
        matches = sorted(set(match.group(0) for match in pattern.finditer(haystack)))
        repo_reason: str | None = None
        if role_name == "data-model-reviewer" and repo_flags.get("has_migration_or_schema_files"):
            repo_reason = "Repository signals show schema or migration files."
        elif role_name == "infra-release-reviewer" and repo_flags.get("has_ci_release_files"):
            repo_reason = "Repository signals show CI or release workflow files."
        elif role_name == "frontend-workflow-reviewer" and repo_flags.get("has_frontend_surface_files"):
            repo_reason = "Repository signals show frontend workflow files."
        elif role_name == "dependency-config-reviewer" and repo_flags.get("has_dependency_or_lockfile_files"):
            repo_reason = "Repository signals show dependency or configuration files."

        score = 60 + len(matches)
        if matches:
            reasons = [f"Matched role-specific hints: {', '.join(matches[:6])}."]
            if repo_reason:
                reasons.append(repo_reason)
            path_signal_name = ROLE_PATH_SIGNAL_MAP.get(role_name, "")
            add_candidate(role_name, score + int(path_signals.get(path_signal_name, 0)), reasons, priority)
        elif repo_reason:
            add_candidate(role_name, score + 3, [repo_reason], priority)

    scored_candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    selected_role_names = list(AUTO_REQUIRED_ROLE_ORDER)
    ranked_alternates: list[dict[str, Any]] = []
    for score, _, role_name, reasons in scored_candidates:
        if role_name in selected_role_names:
            continue
        if len(selected_role_names) < team_max_size:
            selected_role_names.append(role_name)
            selection_reasons[role_name] = reasons
        else:
            ranked_alternates.append({"role": role_name, "score": score, "reason": " ".join(reasons)})

    soft_cap_warning = None
    if ranked_alternates:
        soft_cap_warning = (
            f"Planner soft cap {team_max_size} reached; keeping the highest-priority initial team and listing overflow alternates."
        )
    report_sections = build_report_sections_for_roles(selected_role_names)
    return {
        "schema_version": TEAM_PLAN_SCHEMA_VERSION,
        "selected_roles": selected_role_names,
        "ranked_alternates": ranked_alternates,
        "selection_reasons": selection_reasons,
        "signals_used": [
            "goal",
            "team_request",
            "scope",
            "keywords",
            f"team_signals.{active_selection_key(runtime_signals['effective_mode'])}",
        ],
        "soft_cap_warning": soft_cap_warning,
        "lead_guidance": [
            "Treat the resolved team as the initial hypothesis only and evolve it if evidence demands more coverage.",
        ],
        "report_sections": report_sections,
    }


def normalize_planner_output(
    raw_plan: dict[str, Any],
    catalog: dict[str, dict[str, Any]],
    team_max_size: int,
) -> dict[str, Any]:
    if not isinstance(raw_plan, dict):
        raise PlannerValidationError("Planner output must be a JSON object.")
    missing_keys = sorted(PLANNER_REQUIRED_KEYS - set(raw_plan))
    if missing_keys:
        raise PlannerValidationError("Planner output is missing required keys: " + ", ".join(missing_keys))

    selected_roles = raw_plan.get("selected_roles")
    if not isinstance(selected_roles, list) or any(not isinstance(item, str) or not item.strip() for item in selected_roles):
        raise PlannerValidationError("selected_roles must be a list of non-empty role names.")
    selected_roles = dedupe_preserve_order([item.strip() for item in selected_roles])
    unknown_roles = [role for role in selected_roles if role not in catalog]
    if unknown_roles:
        raise PlannerValidationError("Planner selected unknown roles: " + ", ".join(unknown_roles))
    if not selected_roles:
        raise PlannerValidationError("Planner selected_roles cannot be empty.")
    missing_core_roles = [role for role in AUTO_REQUIRED_ROLE_ORDER if role not in selected_roles]
    if missing_core_roles:
        raise PlannerValidationError("Planner omitted required core roles: " + ", ".join(missing_core_roles))

    ranked_alternates_raw = raw_plan.get("ranked_alternates")
    if not isinstance(ranked_alternates_raw, list):
        raise PlannerValidationError("ranked_alternates must be a list.")
    ranked_alternates: list[dict[str, Any]] = []
    for item in ranked_alternates_raw:
        if isinstance(item, str):
            role = item.strip()
            reason = ""
        elif isinstance(item, dict):
            role = str(item.get("role") or "").strip()
            reason = str(item.get("reason") or "").strip()
        else:
            raise PlannerValidationError("ranked_alternates items must be strings or objects.")
        if not role:
            raise PlannerValidationError("ranked_alternates items require a role.")
        if role not in catalog:
            raise PlannerValidationError(f"Planner alternate references unknown role: {role}")
        ranked_alternates.append({"role": role, "reason": reason})

    selection_reasons_raw = raw_plan.get("selection_reasons")
    if not isinstance(selection_reasons_raw, dict):
        raise PlannerValidationError("selection_reasons must be an object.")
    selection_reasons: dict[str, list[str]] = {}
    for role in selected_roles:
        reasons = selection_reasons_raw.get(role)
        if not isinstance(reasons, list) or any(not isinstance(item, str) or not item.strip() for item in reasons):
            raise PlannerValidationError(f"selection_reasons[{role}] must be a non-empty string list.")
        selection_reasons[role] = [item.strip() for item in reasons]

    signals_used = raw_plan.get("signals_used")
    if not isinstance(signals_used, list) or any(not isinstance(item, str) or not item.strip() for item in signals_used):
        raise PlannerValidationError("signals_used must be a non-empty string list.")

    lead_guidance = raw_plan.get("lead_guidance")
    if not isinstance(lead_guidance, list) or any(not isinstance(item, str) or not item.strip() for item in lead_guidance):
        raise PlannerValidationError("lead_guidance must be a non-empty string list.")

    report_sections = raw_plan.get("report_sections")
    if not isinstance(report_sections, list) or any(not isinstance(item, str) or not item.strip() for item in report_sections):
        raise PlannerValidationError("report_sections must be a non-empty string list.")
    normalized_sections = dedupe_preserve_order([item.strip().lower() for item in report_sections])
    unknown_sections = [section for section in normalized_sections if section not in REPORT_SECTION_HEADINGS]
    if unknown_sections:
        raise PlannerValidationError("Planner emitted unknown report_sections: " + ", ".join(unknown_sections))
    missing_base_sections = [section for section in DEFAULT_REPORT_SECTIONS if section not in normalized_sections]
    if missing_base_sections:
        raise PlannerValidationError("Planner omitted base report_sections: " + ", ".join(missing_base_sections))
    if "team evolution" not in normalized_sections:
        normalized_sections.append("team evolution")

    soft_cap_warning = raw_plan.get("soft_cap_warning")
    if soft_cap_warning is not None and (not isinstance(soft_cap_warning, str) or not soft_cap_warning.strip()):
        raise PlannerValidationError("soft_cap_warning must be null or a non-empty string.")
    if len(selected_roles) > team_max_size and not soft_cap_warning:
        soft_cap_warning = (
            f"Planner returned {len(selected_roles)} initial roles, above the configured soft cap {team_max_size}."
        )

    return {
        "schema_version": TEAM_PLAN_SCHEMA_VERSION,
        "selected_roles": selected_roles,
        "ranked_alternates": ranked_alternates,
        "selection_reasons": selection_reasons,
        "signals_used": [item.strip() for item in signals_used],
        "soft_cap_warning": soft_cap_warning.strip() if isinstance(soft_cap_warning, str) else None,
        "lead_guidance": [item.strip() for item in lead_guidance],
        "report_sections": normalized_sections,
    }


def build_team_planner_prompt(
    goal: str,
    team_request: str,
    runtime_signals: dict[str, Any],
    catalog: dict[str, dict[str, Any]],
    team_max_size: int,
) -> str:
    role_lines = "\n".join(f"- {name}: {spec['description']}" for name, spec in catalog.items())
    return textwrap.dedent(
        f"""
        You are planning an initial Claude Code analysis team for a repository review.
        Return JSON only with these keys:
        selected_roles, ranked_alternates, selection_reasons, signals_used, soft_cap_warning, lead_guidance, report_sections

        Constraints:
        - Use only these catalog roles:
        {role_lines}
        - Prefer an initial team size around {team_max_size}, but the cap is soft.
        - The runtime lead may change the team later, so optimize for the best starting team.
        - Always include architecture-mapper and correctness-gap-reviewer.
        - report_sections must include: scope and assumptions, short system map, top findings, evidence, confirmed facts vs inference or uncertainty, correctness risks, team evolution, suggested next design steps.
        - Add conditional report_sections only when they match the selected roles.
        - selection_reasons must contain at least one concrete reason per selected role.

        Goal:
        {goal or '(none provided)'}

        Team request:
        {team_request or '(none provided)'}

        Runtime team signals:
        {json.dumps(runtime_signals, indent=2, ensure_ascii=False)}
        """
    ).strip()


def run_model_team_planner(
    *,
    planner_input: dict[str, Any],
    catalog: dict[str, dict[str, Any]],
    team_max_size: int,
    planner_context: dict[str, Any],
) -> dict[str, Any]:
    if planner_context.get("dry_run"):
        raise PlannerValidationError("Model planner is skipped during --dry-run.")
    claude_bin = str(planner_context["claude_bin"])
    repo_root = Path(str(planner_context["repo_root"]))
    env = dict(planner_context.get("env") or os.environ.copy())
    prompt = build_team_planner_prompt(
        goal=str(planner_input.get("goal") or ""),
        team_request=str(planner_input.get("team_request") or ""),
        runtime_signals=planner_input,
        catalog=catalog,
        team_max_size=team_max_size,
    )
    command = [
        claude_bin,
        "-p",
        prompt,
        "--model",
        str(planner_context["model"]),
        "--effort",
        str(planner_context["effort"]),
        "--output-format",
        "json",
        "--no-chrome",
        "--max-turns",
        "1",
    ]
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
    if proc.returncode != 0 or not raw_stdout:
        raise PlannerValidationError(
            f"Model planner failed with exit code {proc.returncode}: {stderr_tail or raw_stdout or 'empty output'}"
        )
    try:
        outer = json.loads(raw_stdout)
    except json.JSONDecodeError as exc:
        raise PlannerValidationError(f"Model planner returned invalid outer JSON: {exc}") from exc
    planner_text = maybe_extract_result_text(outer).strip()
    try:
        planner_json = json.loads(planner_text)
    except json.JSONDecodeError as exc:
        raise PlannerValidationError(f"Model planner returned non-JSON content: {planner_text}") from exc
    return planner_json


def plan_auto_team(
    *,
    catalog: dict[str, dict[str, Any]],
    runtime_signals: dict[str, Any],
    team_planner: str,
    team_max_size: int,
    planner_context: dict[str, Any] | None,
    planner_runner: Callable[..., dict[str, Any]] | None,
) -> dict[str, Any]:
    heuristic_plan = build_heuristic_team_plan(catalog, runtime_signals, team_max_size)
    if team_planner == "heuristic":
        return {
            "planner": {
                "source": "heuristic",
                "fallback_used": False,
                "failure_reason": None,
                "ranked_alternates": heuristic_plan["ranked_alternates"],
            },
            "normalized_plan": heuristic_plan,
            "raw_plan": heuristic_plan,
            "warnings": [heuristic_plan["soft_cap_warning"]] if heuristic_plan.get("soft_cap_warning") else [],
        }

    runner = planner_runner or run_model_team_planner
    last_error: str | None = None
    raw_plan: dict[str, Any] | None = None
    for _ in range(2):
        try:
            raw_plan = runner(
                planner_input=runtime_signals,
                catalog=catalog,
                team_max_size=team_max_size,
                planner_context=planner_context or {"dry_run": True},
            )
            normalized_plan = normalize_planner_output(raw_plan, catalog, team_max_size)
            warnings: list[str] = []
            if normalized_plan.get("soft_cap_warning"):
                warnings.append(normalized_plan["soft_cap_warning"])
            return {
                "planner": {
                    "source": "model",
                    "fallback_used": False,
                    "failure_reason": None,
                    "ranked_alternates": normalized_plan["ranked_alternates"],
                },
                "normalized_plan": normalized_plan,
                "raw_plan": raw_plan,
                "warnings": warnings,
            }
        except PlannerValidationError as exc:
            last_error = str(exc)

    warnings = [f"Fell back to heuristic team planner because the model planner failed: {last_error}"]
    if heuristic_plan.get("soft_cap_warning"):
        warnings.append(heuristic_plan["soft_cap_warning"])
    return {
        "planner": {
            "source": "heuristic_fallback",
            "fallback_used": True,
            "failure_reason": last_error,
            "ranked_alternates": heuristic_plan["ranked_alternates"],
        },
        "normalized_plan": heuristic_plan,
        "raw_plan": raw_plan,
        "warnings": warnings,
    }


def validate_lead_configuration(lead: dict[str, Any], agents: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    recommended_roles = dedupe_preserve_order([role for role in lead.get("recommended_roles") or []])
    missing_roles = [role for role in recommended_roles if role not in agents]
    if missing_roles:
        raise SystemExit(
            "lead.recommended_roles references roles that are not present in the final team: "
            + ", ".join(missing_roles)
        )
    return {
        "recommended_roles": recommended_roles,
        "extra_instructions": list(lead.get("extra_instructions") or []),
    }
def resolve_agents(
    *,
    team_mode: str,
    team_request: str,
    team_config_path: Path | None,
    team_strategy: str,
    goal: str,
    manifest: dict[str, Any],
    effective_mode: str,
    worker_model: str,
    worker_effort: str,
    team_planner: str,
    team_max_size: int,
    include_security: bool,
    force_security_review: bool,
    skip_security_review: bool,
    planner_context: dict[str, Any] | None = None,
    planner_runner: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if team_mode not in {"default", "auto", "custom"}:
        raise SystemExit(f"Unsupported team mode: {team_mode}")
    if team_planner not in {"model", "heuristic"}:
        raise SystemExit(f"Unsupported team planner: {team_planner}")
    if team_max_size < 2:
        raise SystemExit("--team-max-size must be at least 2.")
    if force_security_review and skip_security_review:
        raise SystemExit("Use only one of force_security_review or skip_security_review.")
    if team_mode == "default":
        if team_request:
            raise SystemExit("--team-request can only be used with --team-mode auto.")
        if team_config_path is not None:
            raise SystemExit("--team-config can only be used with --team-mode custom.")
        if team_strategy:
            raise SystemExit("--team-strategy can only be used with --team-mode custom.")
    elif team_mode == "auto":
        if team_config_path is not None:
            raise SystemExit("--team-config can only be used with --team-mode custom.")
        if team_strategy:
            raise SystemExit("--team-strategy can only be used with --team-mode custom.")
    else:
        if team_config_path is None:
            raise SystemExit("--team-mode custom requires --team-config.")
        if team_request:
            raise SystemExit("--team-request is not used with --team-mode custom.")

    catalog = build_role_catalog(worker_model, worker_effort)
    runtime_signals = build_runtime_team_signals(goal, team_request, manifest, effective_mode)
    lead = {"recommended_roles": [], "extra_instructions": []}
    selection_reasons: dict[str, list[str]] = {}
    dropped_roles: list[dict[str, Any]] = []
    strategy = None
    config_format = None
    team_source = "built_in_default"
    planner_summary = {
        "source": "not_used",
        "fallback_used": False,
        "failure_reason": None,
        "ranked_alternates": [],
    }
    raw_team_plan: dict[str, Any] | None = None
    report_sections = list(DEFAULT_REPORT_SECTIONS)
    warnings: list[str] = []
    runtime_policy = {
        "initial_team_semantics": "starting_hypothesis",
        "runtime_team_mutation": "lead_may_change_team_with_team_evolution_reporting",
        "team_max_size_soft_cap": team_max_size,
    }

    if team_mode == "default":
        agents = build_default_agents(worker_model, worker_effort, include_security)
        selection_reasons = build_default_selection_reasons(include_security)
        report_sections = build_report_sections_for_roles(list(agents.keys()))
    elif team_mode == "auto":
        planned = plan_auto_team(
            catalog=catalog,
            runtime_signals=runtime_signals,
            team_planner=team_planner,
            team_max_size=team_max_size,
            planner_context=planner_context,
            planner_runner=planner_runner,
        )
        planner_summary = planned["planner"]
        raw_team_plan = planned["raw_plan"]
        normalized_plan = planned["normalized_plan"]
        warnings.extend(planned["warnings"])
        selection_reasons = normalized_plan["selection_reasons"]
        dropped_roles = normalized_plan["ranked_alternates"]
        report_sections = normalized_plan["report_sections"]
        lead = {
            "recommended_roles": list(normalized_plan["selected_roles"]),
            "extra_instructions": list(normalized_plan["lead_guidance"]),
        }
        agents = ordered_agents(list(normalized_plan["selected_roles"]), catalog)
        team_source = f"auto_planner_{planner_summary['source']}"
    else:
        assert team_config_path is not None
        loaded = load_team_config(team_config_path, worker_model, worker_effort)
        strategy = team_strategy or loaded["strategy"]
        config_format = loaded["format"]
        if strategy == "replace" and (force_security_review or skip_security_review):
            raise SystemExit(
                "custom replace is exact; do not combine --team-strategy replace with --force-security-review or --skip-security-review."
            )
        lead = loaded["lead"]
        loaded_agents = {name: clone_agent_spec(spec) for name, spec in loaded["agents"].items()}
        if strategy == "merge":
            agents = build_default_agents(worker_model, worker_effort, include_security=include_security)
            selection_reasons = build_default_selection_reasons(include_security)
            for name, spec in loaded_agents.items():
                agents[name] = spec
                selection_reasons[name] = [f"Overridden or added from custom team config ({config_format})."]
            apply_security_policy(
                agents=agents,
                catalog=catalog,
                include_security=include_security,
                force_security_review=force_security_review,
                skip_security_review=skip_security_review,
                selection_reasons=selection_reasons,
            )
        else:
            agents = loaded_agents
            selection_reasons = {
                name: [f"Selected from custom team config ({config_format})."]
                for name in loaded_agents
            }
        team_source = f"custom_config_{strategy}"
        report_sections = build_report_sections_for_roles(list(agents.keys()))
        if len(agents) > team_max_size:
            warnings.append(
                f"Resolved custom team has {len(agents)} roles, above the planner soft cap {team_max_size}. The team is preserved unchanged."
            )

    if not agents:
        raise SystemExit("Resolved agent team is empty.")
    validated_lead = validate_lead_configuration(lead, agents)
    selected_roles = list(agents.keys())
    if not validated_lead["recommended_roles"]:
        validated_lead["recommended_roles"] = list(selected_roles)
    if "team evolution" not in report_sections:
        report_sections.append("team evolution")
    return {
        "team_mode": team_mode,
        "team_source": team_source,
        "team_request": team_request or None,
        "team_config_path": str(team_config_path) if team_config_path else None,
        "strategy": strategy,
        "config_format": config_format,
        "runtime_signals": runtime_signals,
        "agents": agents,
        "selected_roles": selected_roles,
        "selection_reasons": selection_reasons,
        "dropped_roles": dropped_roles,
        "warnings": warnings,
        "planner": planner_summary,
        "raw_team_plan": raw_team_plan,
        "report_sections": report_sections,
        "runtime_policy": runtime_policy,
        "lead": validated_lead,
    }


def summarize_warnings(warnings: list[str]) -> str:
    if not warnings:
        return "- none"
    return "\n".join(f"- {item}" for item in warnings)


def build_system_prompt(
    manifest_path: Path,
    repo_tree_path: Path | None,
    goal: str,
    effective_mode: str,
    team_resolution: dict[str, Any],
    seed_files: list[str],
) -> str:
    seed_lines = "\n".join(f"- {path}" for path in seed_files[:40]) if seed_files else "- none"
    repo_tree_note = str(repo_tree_path) if repo_tree_path else "(repo tree unavailable)"
    role_lines = "\n".join(
        f"- {name}: {spec['description']}"
        for name, spec in team_resolution["agents"].items()
    )
    alternate_lines = "\n".join(
        f"- {item['role']}: {item.get('reason') or '(no reason provided)'}"
        for item in team_resolution["planner"].get("ranked_alternates") or []
    ) or "- none"
    lead_instructions = "\n".join(
        f"- {instruction}"
        for instruction in team_resolution["lead"].get("extra_instructions") or []
    ) or "- none"
    warning_lines = "\n".join(f"- {warning}" for warning in team_resolution.get("warnings") or []) or "- none"
    required_heading_lines = report_heading_lines(team_resolution["report_sections"])

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
        4. Use the resolved teammate roles below and assign explicit subtasks with success criteria.

        Resolved teammate roles for this run:
        {role_lines}

        Mode guidance:
        {mode_specific}

        Team resolution guidance:
        - Team mode: {team_resolution['team_mode']}
        - Team source: {team_resolution['team_source']}
        - Use the resolved role list as the initial hypothesis team.
        - You may add or remove teammates during execution if the evidence shows a better split, but record every mutation under the final Team Evolution section.
        - Do not silently ignore the resolved team and collapse into a monolithic single-pass review.
        - Keep all resolved teammates read-only.
        - Planner warnings:
        {warning_lines}
        - Ranked alternates suggested by the planner:
        {alternate_lines}

        Lead-specific extra instructions:
        {lead_instructions}

        Seed files from preparation:
        {seed_lines}

        Coordination guidance:
        - Keep the shared task list concise and independent.
        - Ask each teammate to return: findings, evidence, confidence, and open questions.
        - Merge overlapping findings instead of repeating them.
        - Resolve contradictions explicitly.
        - Shut down and clean up the team before finishing if Claude created one.

        Final output requirements:
        Use these exact markdown H2 headings, verbatim:
        {required_heading_lines}

        User goal:
        {goal or '(none provided)'}
        """
    ).strip() + "\n"


def build_user_prompt(
    goal: str,
    manifest: dict[str, Any],
    mode: SelectedMode,
    team_resolution: dict[str, Any],
    seed_files: list[str],
) -> str:
    warnings_block = summarize_warnings(list(manifest.get("warnings") or []))
    scope = ", ".join(manifest.get("scope") or []) or "(none provided)"
    keywords = ", ".join(manifest.get("keywords") or []) or "(none)"
    stats = manifest.get("stats") or {}
    seed_lines = "\n".join(f"- {path}" for path in seed_files[:60]) if seed_files else "- none"
    role_lines = "\n".join(
        f"- {name}: {spec['description']}"
        for name, spec in team_resolution["agents"].items()
    ) or "- none"
    selection_reason_lines = "\n".join(
        f"- {name}: {' '.join(reasons)}"
        for name, reasons in team_resolution["selection_reasons"].items()
    ) or "- none"
    alternate_lines = "\n".join(
        f"- {item['role']}: {item.get('reason') or '(no reason provided)'}"
        for item in team_resolution["planner"].get("ranked_alternates") or []
    ) or "- none"
    extra_instruction_lines = "\n".join(
        f"- {item}" for item in team_resolution["lead"].get("extra_instructions") or []
    ) or "- none"
    team_request_line = team_resolution.get("team_request") or "(none)"
    strategy_line = team_resolution.get("strategy") or "(default)"
    warning_lines = "\n".join(f"- {item}" for item in team_resolution.get("warnings") or []) or "- none"
    report_section_lines = report_heading_lines(team_resolution["report_sections"])

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
        - team mode: {team_resolution['team_mode']}
        - team source: {team_resolution['team_source']}
        - team request: {team_request_line}
        - team strategy: {strategy_line}

        Local warnings:
        {warnings_block}

        Start from these prepared seed files, then expand only when needed:
        {seed_lines}

        Resolved teammate roles for this run:
        {role_lines}

        Why these roles were selected:
        {selection_reason_lines}

        Planner alternates and warnings:
        - planner source: {team_resolution['planner']['source']}
        - fallback used: {team_resolution['planner']['fallback_used']}
        - warnings:
        {warning_lines}
        - ranked alternates:
        {alternate_lines}

        Important instructions:
        - Agent teams are enabled for this session via environment; use the resolved team configuration below.
        - Treat the resolved roles as the initial hypothesis team, not a frozen contract.
        - Runtime team evolution is allowed when it improves coverage, but you must document every added or removed role under the final Team Evolution section.
        - Do not silently replace the resolved team with a monolithic single-pass review.
        - Keep all teammates read-only.
        - If team mode is custom, start from the resolved team exactly as provided by the helper. If you evolve it at runtime, explain why.
        - Recommended lead coordination order: {', '.join(team_resolution['lead']['recommended_roles'])}
        - Lead extra instructions:
        {extra_instruction_lines}
        - Do not use external web research unless I explicitly ask for it later.
        - Finish with one consolidated report that uses these exact markdown H2 headings:
        {report_section_lines}
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


def build_normalized_section_aliases(required_sections: list[str]) -> dict[str, set[str]]:
    return {
        canonical: {normalize_heading_text(alias) for alias in [canonical, *REPORT_SECTION_ALIASES.get(canonical, [])]}
        for canonical in required_sections
    }


def assess_report_completeness(report_text: str, required_sections: list[str]) -> dict[str, Any]:
    headings = extract_report_headings(report_text)
    normalized_aliases = build_normalized_section_aliases(required_sections)
    missing_sections = [
        section
        for section in required_sections
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


def build_followup_command(
    claude_bin: str,
    args: argparse.Namespace,
    session_id: str,
    report_sections: list[str],
) -> list[str]:
    cmd = [
        claude_bin,
        "-p",
        build_followup_report_prompt(report_sections),
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
    report_sections: list[str],
) -> dict[str, Any]:
    command = build_followup_command(claude_bin, args, session_id, report_sections)
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
    quality = assess_report_completeness(report_text, report_sections)
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
    parser.add_argument(
        "--team-mode",
        choices=["default", "auto", "custom"],
        default="default",
        help="How to resolve the Claude worker team. Default keeps the built-in team, auto adapts via local rules, custom uses --team-config.",
    )
    parser.add_argument(
        "--team-request",
        default="",
        help="Optional natural-language hint for auto team composition. Use with --team-mode auto.",
    )
    parser.add_argument(
        "--team-config",
        default="",
        help="Path to a JSON team config. Use with --team-mode custom.",
    )
    parser.add_argument(
        "--team-strategy",
        choices=["merge", "replace"],
        default="",
        help="Optional override for custom team resolution strategy.",
    )
    parser.add_argument(
        "--team-planner",
        choices=["model", "heuristic"],
        default="model",
        help="Planner used for --team-mode auto. Model is the default; heuristic is kept for fallback and debugging.",
    )
    parser.add_argument(
        "--team-max-size",
        type=int,
        default=DEFAULT_TEAM_MAX_SIZE,
        help="Soft cap for the recommended initial team size. Exceeding it records warnings instead of trimming custom teams.",
    )
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
    if args.force_security_review and args.skip_security_review:
        raise SystemExit("Use only one of --force-security-review or --skip-security-review.")

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
    seed_files = choose_seed_files(manifest, selected_mode.effective)
    repo_tree_path = None
    artifacts = manifest.get("artifacts") or {}
    repo_tree_value = artifacts.get("repo_tree")
    if isinstance(repo_tree_value, str) and repo_tree_value.strip():
        repo_tree_path = Path(repo_tree_value).resolve()

    env = os.environ.copy()
    env.setdefault("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS", "1")
    env.setdefault("CLAUDE_CODE_ENABLE_TASKS", "1")
    env.setdefault("CLAUDE_CODE_SUBPROCESS_ENV_SCRUB", "1")

    runtime_signals = build_runtime_team_signals(goal, args.team_request.strip(), manifest, selected_mode.effective)
    include_security = should_include_security(runtime_signals, args.force_security_review, args.skip_security_review)
    planner_context = {
        "dry_run": bool(args.dry_run),
        "claude_bin": claude_bin,
        "repo_root": repo_root,
        "env": env,
        "model": args.model,
        "effort": args.effort,
    }

    team_config_path = Path(args.team_config).resolve() if args.team_config else None
    team_resolution = resolve_agents(
        team_mode=args.team_mode,
        team_request=args.team_request.strip(),
        team_config_path=team_config_path,
        team_strategy=args.team_strategy,
        goal=goal,
        manifest=manifest,
        effective_mode=selected_mode.effective,
        worker_model=args.worker_model,
        worker_effort=args.worker_effort,
        team_planner=args.team_planner,
        team_max_size=args.team_max_size,
        include_security=include_security,
        force_security_review=args.force_security_review,
        skip_security_review=args.skip_security_review,
        planner_context=planner_context,
    )
    agents = team_resolution["agents"]
    system_prompt_text = build_system_prompt(
        manifest_path=manifest_path,
        repo_tree_path=repo_tree_path,
        goal=goal,
        effective_mode=selected_mode.effective,
        team_resolution=team_resolution,
        seed_files=seed_files,
    )
    user_prompt_text = build_user_prompt(
        goal=goal,
        manifest=manifest,
        mode=selected_mode,
        team_resolution=team_resolution,
        seed_files=seed_files,
    )

    agents_path = out_dir / "claude-agents.json"
    system_prompt_path = out_dir / "claude-system-prompt.md"
    user_prompt_path = out_dir / "claude-user-prompt.txt"
    team_signals_path = out_dir / "team-signals.json"
    team_plan_path = out_dir / "team-plan.json"
    team_resolution_path = out_dir / "team-resolution.json"
    copied_team_config_path: Path | None = None
    if team_config_path is not None:
        copied_team_config_path = out_dir / "team-config.input.json"
        shutil.copyfile(team_config_path, copied_team_config_path)
    write_text(agents_path, json.dumps(agents, indent=2, ensure_ascii=False))
    write_text(system_prompt_path, system_prompt_text)
    write_text(user_prompt_path, user_prompt_text)
    save_json(team_signals_path, team_resolution["runtime_signals"])
    save_json(
        team_plan_path,
        {
            "planner": team_resolution["planner"],
            "raw_plan": team_resolution["raw_team_plan"],
            "normalized_plan": {
                "selected_roles": team_resolution["selected_roles"],
                "selection_reasons": team_resolution["selection_reasons"],
                "ranked_alternates": team_resolution["dropped_roles"],
                "report_sections": team_resolution["report_sections"],
            },
        },
    )
    save_json(
        team_resolution_path,
        {
            "team_mode": team_resolution["team_mode"],
            "team_source": team_resolution["team_source"],
            "team_request": team_resolution["team_request"],
            "team_config_path": team_resolution["team_config_path"],
            "strategy": team_resolution["strategy"],
            "config_format": team_resolution["config_format"],
            "selected_roles": team_resolution["selected_roles"],
            "selection_reasons": team_resolution["selection_reasons"],
            "dropped_roles": team_resolution["dropped_roles"],
            "warnings": team_resolution["warnings"],
            "planner": team_resolution["planner"],
            "report_sections": team_resolution["report_sections"],
            "runtime_policy": team_resolution["runtime_policy"],
            "lead": team_resolution["lead"],
            "agents_path": str(agents_path),
            "team_signals_path": str(team_signals_path),
            "team_plan_path": str(team_plan_path),
            "copied_team_config_path": str(copied_team_config_path) if copied_team_config_path else None,
        },
    )

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
        "team_planner": args.team_planner,
        "team_max_size": args.team_max_size,
        "max_turns": args.max_turns,
        "claude_version": claude_version_text,
        "include_security_reviewer": include_security,
        "force_security_review": bool(args.force_security_review),
        "skip_security_review": bool(args.skip_security_review),
        "team_mode": team_resolution["team_mode"],
        "team_source": team_resolution["team_source"],
        "team_request": team_resolution["team_request"],
        "team_config_path": team_resolution["team_config_path"],
        "team_config_input_copy_path": str(copied_team_config_path) if copied_team_config_path else None,
        "team_strategy": team_resolution["strategy"],
        "team_config_format": team_resolution["config_format"],
        "resolved_agent_names": team_resolution["selected_roles"],
        "team_warnings": team_resolution["warnings"],
        "planner_source": team_resolution["planner"]["source"],
        "planner_fallback_used": team_resolution["planner"]["fallback_used"],
        "team_resolution_path": str(team_resolution_path),
        "team_signals_path": str(team_signals_path),
        "team_plan_path": str(team_plan_path),
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
    report_quality = assess_report_completeness(report_text, team_resolution["report_sections"])

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
            followup_result = run_followup_report(
                claude_bin,
                args,
                repo_root,
                env,
                session_id,
                team_resolution["report_sections"],
            )
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
                        "team_mode": team_resolution["team_mode"],
                        "resolved_agent_names": team_resolution["selected_roles"],
                        "team_resolution_path": str(team_resolution_path),
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
                "team_mode": team_resolution["team_mode"],
                "resolved_agent_names": team_resolution["selected_roles"],
                "team_resolution_path": str(team_resolution_path),
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
