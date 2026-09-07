#!/usr/bin/env python3
"""Build, query, and validate a derived index for goal execution reports."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import posixpath
import re
import sys
import tempfile
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA_VERSION = 1
GENERATOR_VERSION = "1.1.0"
DEFAULT_LIMIT = 15
DEFAULT_MAX_OUTPUT_BYTES = 24_000
MAX_MATCH_REASONS = 8
MAX_SNIPPETS = 3
MAX_SNIPPET_CHARS = 240

REPORT_DIRS = {
    "failed": PurePosixPath("docs/failed-reports"),
    "passed": PurePosixPath("docs/passed-reports"),
}
CATALOG_PATH = PurePosixPath("docs/report-index/catalog.jsonl")

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
FIELD_RE = re.compile(r"^-\s+(?:\*\*)?([^:*]+?)(?:\*\*)?:\s*(.*)$")
TOKEN_RE = re.compile(r"[\w./:@+-]+", re.UNICODE)
MARKDOWN_LINK_RE = re.compile(r"\]\(([^)]+\.md)(?:#[^)]+)?\)")
REPORT_PATH_RE = re.compile(
    r"(?<![\w.-])((?:(?:\.\.?/)+|docs/)?(?:failed-reports|passed-reports)/[^\s)\],;`<>]+\.md)"
)
URI_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")

# Exact compatibility aliases, not semantic translation. Raw text remains authoritative.
LABEL_ALIASES = {
    "상태": "status",
    "기록 시각": "recorded", "기록일시": "recorded", "기록일": "recorded",
    "문제 서명": "problem signature", "목표/문제 서명": "goal/problem signature",
    "목표/체크포인트": "goal/checkpoint", "영향 범위": "affected scope",
    "제외 범위": "excluded scope", "환경/버전": "environment/versions",
    "정확한 식별자": "exact identifiers", "검색어": "search terms",
    "관련 경로": "related paths", "관련 실패 보고서": "related failed reports",
    "관련 성공 보고서": "related passed reports",
    "대체한 보고서": "supersedes", "후속 보고서": "superseded by",
    "예상": "expected", "관측": "observed", "검증": "verification",
    "시도": "attempts", "증거 및 완료 기준": "evidence and completion criteria",
    "자격": "qualification",
}
STATUS_ALIASES = {
    "미해결": "open", "열림": "open", "해결됨": "resolved", "해결": "resolved",
    "차단됨": "blocked", "차단": "blocked", "대체됨": "superseded",
    "활성": "active", "미상": "unknown",
}
KNOWN_STATUSES = {"open", "resolved", "blocked", "superseded", "active", "unknown"}


class ReportIndexError(RuntimeError):
    """Raised for user-facing report-index failures."""


@dataclass(frozen=True)
class ReportDocument:
    kind: str
    source_path: str
    text: str
    source_hash: str


@dataclass(frozen=True)
class ParsedReport:
    title: str
    fields: dict[str, list[str]]
    sections: dict[str, str]


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_label(value: str) -> str:
    value = value.replace("`", "").replace("*", "")
    label = " ".join(value.casefold().split())
    return LABEL_ALIASES.get(label, label)


def normalize_search_text(value: str) -> str:
    return " ".join(value.casefold().split())


def clean_value(value: str) -> str:
    lines = [line.rstrip() for line in value.strip().splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def meaningful(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    normalized = stripped.casefold()
    return normalized not in {"...", "none", "n/a", "null", "[]", "{}"}


def unique_nonempty(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = clean_value(value)
        if not meaningful(cleaned) or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def discover_reports(root: Path) -> list[ReportDocument]:
    documents: list[ReportDocument] = []
    for kind, relative_dir in REPORT_DIRS.items():
        report_dir = root / Path(relative_dir)
        if not report_dir.is_dir():
            continue
        for path in sorted(report_dir.rglob("*.md")):
            if path.name.casefold() == "template.md":
                continue
            try:
                data = path.read_bytes()
                text = data.decode("utf-8")
            except (OSError, UnicodeDecodeError) as error:
                raise ReportIndexError(f"Cannot read UTF-8 report {path}: {error}") from error
            source_path = path.relative_to(root).as_posix()
            documents.append(
                ReportDocument(
                    kind=kind,
                    source_path=source_path,
                    text=text,
                    source_hash=sha256_bytes(data),
                )
            )
    return sorted(documents, key=lambda document: document.source_path)


def parse_report(text: str) -> ParsedReport:
    lines = text.splitlines()
    title = ""
    sections: dict[str, list[str]] = {"header": []}
    current_section = "header"

    for line in lines:
        heading = HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            heading_text = clean_value(heading.group(2))
            if level == 1 and not title:
                title = heading_text
                continue
            if level == 2:
                current_section = normalize_label(heading_text)
                sections.setdefault(current_section, [])
                continue
        sections.setdefault(current_section, []).append(line)

    fields: dict[str, list[str]] = {}
    rendered_sections: dict[str, str] = {}
    for section_name, section_lines in sections.items():
        rendered_sections[section_name] = clean_value("\n".join(section_lines))
        current_key: str | None = None
        current_parts: list[str] = []

        def flush_field() -> None:
            nonlocal current_key, current_parts
            if current_key is None:
                return
            value = clean_value("\n".join(current_parts))
            if meaningful(value):
                fields.setdefault(current_key, []).append(value)
            current_key = None
            current_parts = []

        for line in section_lines:
            field_match = FIELD_RE.match(line)
            if field_match:
                flush_field()
                current_key = normalize_label(field_match.group(1))
                current_parts = [field_match.group(2)]
                continue
            if current_key is not None:
                if not line.strip():
                    current_parts.append("")
                elif line.startswith((" ", "\t")):
                    current_parts.append(line.strip())
                else:
                    flush_field()
        flush_field()

    return ParsedReport(title=title, fields=fields, sections=rendered_sections)


def field_values(parsed: ParsedReport, *aliases: str) -> list[str]:
    values: list[str] = []
    for alias in aliases:
        values.extend(parsed.fields.get(normalize_label(alias), []))
    return unique_nonempty(values)


def first_field(parsed: ParsedReport, *aliases: str) -> str:
    values = field_values(parsed, *aliases)
    return values[0] if values else ""


def combine_fields(parsed: ParsedReport, *aliases: str) -> str:
    return "\n".join(field_values(parsed, *aliases))


def parse_markdown_table(section: str) -> list[dict[str, str]]:
    rows: list[list[str]] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        cells = [cell.strip().replace(r"\|", "|") for cell in re.split(r"(?<!\\)\|", stripped[1:-1])]
        if cells and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
            continue
        rows.append(cells)
    if len(rows) < 2:
        return []
    headers = [normalize_label(cell) or f"column_{index + 1}" for index, cell in enumerate(rows[0])]
    result: list[dict[str, str]] = []
    for cells in rows[1:]:
        record: dict[str, str] = {}
        for index, header in enumerate(headers):
            if index >= len(cells):
                continue
            value = clean_value(cells[index])
            if meaningful(value):
                record[header] = value
        if record:
            result.append(record)
    return result


def compact(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            compacted = compact(item)
            if compacted not in (None, "", [], {}):
                result[key] = compacted
        return result
    if isinstance(value, list):
        result_list: list[Any] = []
        for item in value:
            compacted = compact(item)
            if compacted not in (None, "", [], {}):
                result_list.append(compacted)
        return result_list
    return value


def normalize_report_path(raw_path: str, source_path: str) -> str | None:
    candidate = raw_path.strip().strip("`<>'\"")
    candidate = candidate.split("#", 1)[0]
    if not candidate.casefold().endswith(".md") or candidate.startswith("/") or URI_SCHEME_RE.match(candidate):
        return None
    if candidate.startswith("docs/"):
        normalized = posixpath.normpath(candidate)
    elif candidate.startswith(("failed-reports/", "passed-reports/")):
        normalized = posixpath.normpath(f"docs/{candidate}")
    else:
        parent = PurePosixPath(source_path).parent.as_posix()
        normalized = posixpath.normpath(posixpath.join(parent, candidate))
    if not normalized.startswith(("docs/failed-reports/", "docs/passed-reports/")):
        return None
    return normalized


def extract_report_paths(values: Iterable[str], source_path: str) -> list[str]:
    paths: list[str] = []
    for value in values:
        candidates = MARKDOWN_LINK_RE.findall(value)
        candidates.extend(REPORT_PATH_RE.findall(value))
        if not candidates and value.strip().casefold().endswith(".md"):
            candidates.append(value.strip())
        for candidate in candidates:
            normalized = normalize_report_path(candidate, source_path)
            if normalized and PurePosixPath(normalized).name.casefold() != "template.md":
                paths.append(normalized)
    return unique_nonempty(paths)


def build_entry(document: ReportDocument) -> dict[str, Any]:
    parsed = parse_report(document.text)
    problem_signature = first_field(parsed, "Problem signature", "Goal/problem signature")
    # Do not silently prefer the English field when a localized alias contradicts it.
    extraction_warnings: list[str] = []
    field_conflicts: list[str] = []
    signatures = field_values(parsed, "Problem signature", "Goal/problem signature")
    if len(signatures) > 1:
        problem_signature = ""
        field_conflicts.append("Conflicting problem-signature fields")
    status_values = [value.strip().casefold() for value in field_values(parsed, "Status")]
    statuses = {STATUS_ALIASES.get(value, value) for value in status_values}
    if len(statuses) > 1:
        status = "unknown"
        field_conflicts.append("Conflicting Status fields")
    elif statuses:
        candidate_status = next(iter(statuses))
        status = candidate_status if candidate_status in KNOWN_STATUSES else "unknown"
        if candidate_status not in KNOWN_STATUSES:
            extraction_warnings.append("Unrecognized Status value; inspect the original report")
    else:
        status = "unknown"
        extraction_warnings.append("Missing recognized Status field")
    if not signatures:
        extraction_warnings.append("Missing recognized Problem signature field")
    recorded = first_field(parsed, "Recorded")
    environment = combine_fields(
        parsed,
        "Environment/versions",
        "Runtime and dependency versions",
        "Repository/ref or artifact",
        "Commit",
        "External conditions or assumptions",
    )
    exact_identifiers = combine_fields(parsed, "Exact identifiers")
    related_paths = combine_fields(parsed, "Related paths")
    scope = combine_fields(parsed, "Affected scope")
    excluded_scope = combine_fields(parsed, "Excluded scope")
    search_terms = combine_fields(parsed, "Search terms")

    attempts = parse_markdown_table(parsed.sections.get("attempts", ""))
    evidence_results = parse_markdown_table(parsed.sections.get("evidence and completion criteria", ""))
    approaches = unique_nonempty(
        [
            combine_fields(parsed, "Approaches"),
            combine_fields(parsed, "Avoid", "Prefer"),
            combine_fields(parsed, "Sequence", "Decisive choices", "Avoided approaches and why"),
            *(" | ".join(row.values()) for row in attempts),
        ]
    )

    routing = compact(
        {
            "problem_signature": problem_signature,
            "exact_identifiers": exact_identifiers,
            "related_paths": related_paths,
            "environment_versions": environment,
            "affected_scope": scope,
            "excluded_scope": excluded_scope,
            "search_terms": search_terms,
            "approaches": approaches,
        }
    )

    if document.kind == "failed":
        capsule = compact(
            {
                "goal_checkpoint": first_field(parsed, "Goal/checkpoint"),
                "trigger_conditions": first_field(parsed, "Conditions or trigger"),
                "expected": first_field(parsed, "Expected"),
                "observed": first_field(parsed, "Observed"),
                "impact": first_field(parsed, "Impact on the goal"),
                "evidence": combine_fields(
                    parsed,
                    "Sanitized command, test, log, trace, artifact, or access-controlled reference",
                    "Result",
                ),
                "cause_assessment": first_field(parsed, "Confirmed cause or current hypothesis"),
                "confidence": first_field(parsed, "Confidence"),
                "remaining_unknowns": first_field(parsed, "Remaining unknowns"),
                "failed_attempts": attempts,
                "resolution_workaround": first_field(parsed, "Resolution/workaround"),
                "verification": first_field(parsed, "Verification"),
                "next_safe_step": first_field(parsed, "Next safe step if unresolved"),
                "avoid": first_field(parsed, "Avoid"),
                "prefer": first_field(parsed, "Prefer"),
                "applicable_when": first_field(parsed, "Applicable when"),
                "recheck_when": first_field(parsed, "Re-check when"),
            }
        )
    else:
        capsule = compact(
            {
                "qualification": first_field(parsed, "Qualification"),
                "repository_ref_artifact": first_field(parsed, "Repository/ref or artifact"),
                "commit": first_field(parsed, "Commit"),
                "external_conditions": first_field(parsed, "External conditions or assumptions"),
                "prerequisites": first_field(parsed, "Prerequisites"),
                "sequence": first_field(parsed, "Sequence"),
                "decisive_choices": first_field(parsed, "Decisive choices"),
                "avoided_approaches": first_field(parsed, "Avoided approaches and why"),
                "completion_evidence": evidence_results,
                "prefer": first_field(parsed, "Prefer"),
                "minimum_verification": first_field(parsed, "Minimum verification when reused"),
                "applicable_when": first_field(parsed, "Applicable when"),
                "do_not_apply_when": first_field(parsed, "Do not apply when"),
                "recheck_invalidate_when": first_field(parsed, "Re-check or invalidate when"),
            }
        )

    links = compact(
        {
            "related_failed_reports": extract_report_paths(
                field_values(parsed, "Related failed reports"), document.source_path
            ),
            "related_passed_reports": extract_report_paths(
                field_values(parsed, "Related passed reports"), document.source_path
            ),
            "supersedes": extract_report_paths(field_values(parsed, "Supersedes"), document.source_path),
            "superseded_by": extract_report_paths(field_values(parsed, "Superseded by"), document.source_path),
        }
    )

    return compact(
        {
            "id": f"{document.kind}:{document.source_path}",
            "kind": document.kind,
            "status": status,
            "recorded": recorded,
            "title": parsed.title,
            "source_path": document.source_path,
            "source_hash": document.source_hash,
            "sparse": not bool(problem_signature and status != "unknown"),
            "extraction_warnings": extraction_warnings,
            "field_conflicts": field_conflicts,
            "routing": routing,
            "capsule": capsule,
            "links": links,
        }
    )


def build_entries(documents: Iterable[ReportDocument]) -> list[dict[str, Any]]:
    return [build_entry(document) for document in documents]


def source_set_hash(entries: Iterable[dict[str, Any]]) -> str:
    material = "\n".join(f"{entry['source_path']}:{entry['source_hash']}" for entry in entries)
    return sha256_bytes(material.encode("utf-8"))


def catalog_records(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    meta = {
        "_meta": {
            "schema_version": SCHEMA_VERSION,
            "generator_version": GENERATOR_VERSION,
            "report_count": len(entries),
            "source_set_hash": source_set_hash(entries),
        }
    }
    return [meta, *entries]


def catalog_bytes(entries: list[dict[str, Any]]) -> bytes:
    return ("\n".join(stable_json(record) for record in catalog_records(entries)) + "\n").encode("utf-8")


def write_catalog(root: Path, entries: list[dict[str, Any]]) -> Path:
    catalog_path = root / Path(CATALOG_PATH)
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    data = catalog_bytes(entries)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=catalog_path.parent, prefix=".catalog.", suffix=".tmp", delete=False
        ) as temporary:
            temporary.write(data)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, catalog_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return catalog_path


def read_catalog(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    catalog_path = root / Path(CATALOG_PATH)
    if not catalog_path.is_file():
        raise ReportIndexError(f"Catalog is missing: {CATALOG_PATH}")
    try:
        records = [json.loads(line) for line in catalog_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReportIndexError(f"Cannot parse catalog {CATALOG_PATH}: {error}") from error
    # JSON scalars and arrays are valid JSON, but are not catalog records.
    # Check the container before membership/indexing so query can fall back.
    if not records or not isinstance(records[0], dict) or "_meta" not in records[0]:
        raise ReportIndexError("Catalog must start with an _meta object record")
    meta = records[0]["_meta"]
    if not isinstance(meta, dict):
        raise ReportIndexError("Catalog _meta must be an object")
    entries = records[1:]
    if not all(isinstance(entry, dict) for entry in entries):
        raise ReportIndexError("Every catalog entry must be an object")
    return meta, entries


def validate_catalog(
    root: Path, expected_entries: list[dict[str, Any]]
) -> tuple[str, list[dict[str, Any]], list[str]]:
    try:
        meta, actual_entries = read_catalog(root)
    except ReportIndexError as error:
        status = "missing-fallback" if "missing" in str(error).casefold() else "invalid-fallback"
        return status, expected_entries, [str(error)]

    errors: list[str] = []
    expected_meta = catalog_records(expected_entries)[0]["_meta"]
    if meta != expected_meta:
        errors.append("Catalog metadata does not match current reports or generator schema")

    actual_by_path: dict[str, dict[str, Any]] = {}
    for entry in actual_entries:
        source_path = entry.get("source_path")
        if not isinstance(source_path, str) or not source_path:
            errors.append("Catalog entry has no valid source_path")
            continue
        if source_path in actual_by_path:
            errors.append(f"Duplicate catalog entry: {source_path}")
            continue
        actual_by_path[source_path] = entry

    expected_by_path = {entry["source_path"]: entry for entry in expected_entries}
    for source_path in sorted(set(expected_by_path) - set(actual_by_path)):
        errors.append(f"Missing catalog entry: {source_path}")
    for source_path in sorted(set(actual_by_path) - set(expected_by_path)):
        errors.append(f"Orphan catalog entry: {source_path}")
    for source_path in sorted(set(expected_by_path) & set(actual_by_path)):
        if actual_by_path[source_path] != expected_by_path[source_path]:
            errors.append(f"Derived catalog entry differs from source report: {source_path}")

    if errors:
        return "stale-fallback", expected_entries, errors
    return "current", actual_entries, []


def link_values(entry: dict[str, Any], key: str) -> list[str]:
    value = entry.get("links", {}).get(key, [])
    return value if isinstance(value, list) else []


def validate_lifecycle(entries: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    by_path = {entry["source_path"]: entry for entry in entries}

    def require_reverse(source: str, target: str, reverse_key: str, relation: str) -> None:
        target_entry = by_path.get(target)
        if target_entry is None:
            errors.append(f"Broken {relation} link: {source} -> {target}")
            return
        if source not in link_values(target_entry, reverse_key):
            errors.append(f"Missing reverse {relation} link: {target} -> {source}")

    for entry in entries:
        source = entry["source_path"]
        warnings.extend(f"{message}: {source}" for message in entry.get("extraction_warnings", []))
        errors.extend(f"{message}: {source}" for message in entry.get("field_conflicts", []))
        status = str(entry.get("status", "unknown")).casefold()
        superseded_by = link_values(entry, "superseded_by")
        if status == "superseded" and not superseded_by:
            errors.append(f"Superseded report has no successor: {source}")
        for target in link_values(entry, "supersedes"):
            require_reverse(source, target, "superseded_by", "supersession")
        for target in superseded_by:
            require_reverse(source, target, "supersedes", "supersession")
        for target in link_values(entry, "related_failed_reports"):
            require_reverse(source, target, "related_passed_reports", "failed/passed")
        for target in link_values(entry, "related_passed_reports"):
            require_reverse(source, target, "related_failed_reports", "failed/passed")

        qualification = str(entry.get("capsule", {}).get("qualification", "")).casefold()
        if qualification == "resolved-material-failure":
            related = link_values(entry, "related_failed_reports")
            if not related:
                errors.append(f"Resolved-material-failure success has no related failed report: {source}")
            elif not any(
                target in by_path and str(by_path[target].get("status", "")).casefold() == "resolved"
                for target in related
            ):
                errors.append(f"Resolved-material-failure success has no resolved failed report: {source}")

        if entry.get("sparse"):
            warnings.append(f"Legacy or incomplete routing fields: {source}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(source: str, trail: list[str]) -> None:
        if source in visiting:
            cycle_start = trail.index(source) if source in trail else 0
            errors.append(f"Supersession cycle: {' -> '.join(trail[cycle_start:] + [source])}")
            return
        if source in visited:
            return
        visiting.add(source)
        trail.append(source)
        entry = by_path.get(source)
        if entry is not None:
            for target in link_values(entry, "superseded_by"):
                if target in by_path:
                    visit(target, trail)
        trail.pop()
        visiting.remove(source)
        visited.add(source)

    for source_path in sorted(by_path):
        visit(source_path, [])
    return unique_nonempty(errors), unique_nonempty(warnings)


def flatten_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(flatten_strings(item))
        return result
    if isinstance(value, list):
        result = []
        for item in value:
            result.extend(flatten_strings(item))
        return result
    return []


def query_terms(raw_query: str) -> tuple[str, list[str]]:
    phrase = normalize_search_text(raw_query)
    tokens = unique_nonempty(TOKEN_RE.findall(phrase))
    return phrase, tokens


def score_text(
    label: str,
    value: Any,
    phrase: str,
    tokens: list[str],
    exact_weight: int,
    token_weight: int,
) -> tuple[int, str | None]:
    haystack = normalize_search_text("\n".join(flatten_strings(value)))
    if not haystack:
        return 0, None
    if phrase and phrase in haystack:
        return exact_weight, f"exact {label}"
    matched = [token for token in tokens if token in haystack]
    if not matched:
        return 0, None
    coverage = len(matched) / max(1, len(tokens))
    score = max(1, round(token_weight * coverage))
    return score, f"{label} tokens {len(matched)}/{len(tokens)}"


def recorded_ordinal(value: Any) -> int:
    if not isinstance(value, str):
        return 0
    match = re.search(r"\d{4}-\d{2}-\d{2}", value)
    if not match:
        return 0
    try:
        return date.fromisoformat(match.group(0)).toordinal()
    except ValueError:
        return 0


def lifecycle_rank(status: Any) -> int:
    normalized = str(status).casefold()
    return {
        "active": 4,
        "open": 4,
        "blocked": 3,
        "resolved": 3,
        "unknown": 2,
        "superseded": 0,
    }.get(normalized, 1)


def matched_snippets(text: str, phrase: str, tokens: list[str]) -> list[str]:
    snippets: list[str] = []
    for line in text.splitlines():
        cleaned = " ".join(line.strip().split())
        if not cleaned:
            continue
        normalized = cleaned.casefold()
        if (phrase and phrase in normalized) or any(token in normalized for token in tokens):
            if len(cleaned) > MAX_SNIPPET_CHARS:
                cleaned = f"{cleaned[: MAX_SNIPPET_CHARS - 1]}…"
            if cleaned not in snippets:
                snippets.append(cleaned)
        if len(snippets) >= MAX_SNIPPETS:
            break
    return snippets


def successor_chain(source_path: str, by_path: dict[str, dict[str, Any]]) -> list[str]:
    result: list[str] = []
    seen = {source_path}
    queue = list(link_values(by_path[source_path], "superseded_by")) if source_path in by_path else []
    while queue:
        target = queue.pop(0)
        if target in seen:
            continue
        seen.add(target)
        if target not in by_path:
            continue
        result.append(target)
        queue.extend(link_values(by_path[target], "superseded_by"))
    return result


def rank_entries(
    entries: list[dict[str, Any]], documents: list[ReportDocument], raw_query: str
) -> list[dict[str, Any]]:
    phrase, tokens = query_terms(raw_query)
    if not phrase:
        raise ReportIndexError("Query must not be empty")
    raw_by_path = {document.source_path: document.text for document in documents}
    by_path = {entry["source_path"]: entry for entry in entries}
    ranked: list[dict[str, Any]] = []

    weights = [
        ("problem signature", lambda entry: entry.get("routing", {}).get("problem_signature", ""), 10_000, 1_000),
        ("exact identifier", lambda entry: entry.get("routing", {}).get("exact_identifiers", ""), 9_000, 900),
        ("path/module", lambda entry: entry.get("routing", {}).get("related_paths", ""), 8_000, 800),
        ("environment/version", lambda entry: entry.get("routing", {}).get("environment_versions", ""), 6_000, 600),
        ("search term", lambda entry: entry.get("routing", {}).get("search_terms", ""), 5_000, 500),
        ("approach", lambda entry: entry.get("routing", {}).get("approaches", ""), 4_000, 400),
        ("scope", lambda entry: {
            "affected": entry.get("routing", {}).get("affected_scope", ""),
            "excluded": entry.get("routing", {}).get("excluded_scope", ""),
        }, 3_000, 300),
        ("title", lambda entry: entry.get("title", ""), 2_500, 250),
        ("capsule", lambda entry: entry.get("capsule", {}), 2_000, 200),
    ]

    for entry in entries:
        score = 0
        reasons: list[str] = []
        for label, accessor, exact_weight, token_weight in weights:
            partial, reason = score_text(label, accessor(entry), phrase, tokens, exact_weight, token_weight)
            score += partial
            if reason:
                reasons.append(reason)

        raw_text = raw_by_path.get(entry["source_path"], "")
        raw_score, raw_reason = score_text("raw report", raw_text, phrase, tokens, 7_000, 150)
        score += raw_score
        if raw_reason:
            reasons.append(raw_reason)
        if score <= 0:
            continue
        ranked.append(
            {
                "source_path": entry["source_path"],
                "kind": entry.get("kind", "unknown"),
                "status": entry.get("status", "unknown"),
                "score": score,
                "match_reasons": unique_nonempty(reasons)[:MAX_MATCH_REASONS],
                "matched_snippets": matched_snippets(raw_text, phrase, tokens),
                "current_successors": successor_chain(entry["source_path"], by_path),
                "_recorded_ordinal": recorded_ordinal(entry.get("recorded")),
                "_lifecycle_rank": lifecycle_rank(entry.get("status")),
            }
        )

    ranked.sort(key=lambda item: item["source_path"])
    ranked.sort(key=lambda item: item["_recorded_ordinal"], reverse=True)
    ranked.sort(key=lambda item: item["_lifecycle_rank"], reverse=True)
    ranked.sort(key=lambda item: item["score"], reverse=True)
    for item in ranked:
        item.pop("_recorded_ordinal", None)
        item.pop("_lifecycle_rank", None)
    return ranked


def bounded_query_payload(
    *,
    raw_query: str,
    catalog_status: str,
    warnings: list[str],
    ranked: list[dict[str, Any]],
    limit: int,
    max_output_bytes: int,
    elapsed_ms: float,
) -> bytes:
    safe_query = raw_query if len(raw_query) <= 500 else f"{raw_query[:499]}…"
    selected = ranked[:limit]
    payload: dict[str, Any] = {
        "catalog_status": catalog_status,
        "query": safe_query,
        "total_matches": len(ranked),
        "returned_matches": 0,
        "truncated": len(ranked) > limit,
        "elapsed_ms": round(elapsed_ms, 3),
        "warnings": warnings[:10],
        "results": [],
    }

    def encoded() -> bytes:
        return (stable_json(payload) + "\n").encode("utf-8")

    for result in selected:
        payload["results"].append(result)
        payload["returned_matches"] = len(payload["results"])
        if len(encoded()) > max_output_bytes:
            payload["results"].pop()
            payload["returned_matches"] = len(payload["results"])
            payload["truncated"] = True
            break

    data = encoded()
    if len(data) > max_output_bytes:
        payload["warnings"] = ["Output metadata was reduced to honor max_output_bytes"]
        payload["query"] = safe_query[:100]
        data = encoded()
    if len(data) > max_output_bytes:
        minimal = {
            "catalog_status": catalog_status,
            "total_matches": len(ranked),
            "returned_matches": 0,
            "truncated": True,
            "results": [],
        }
        data = (stable_json(minimal) + "\n").encode("utf-8")
    if len(data) > max_output_bytes:
        raise ReportIndexError("max_output_bytes is too small for the minimal query response")
    return data


def command_sync(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    documents = discover_reports(root)
    entries = build_entries(documents)
    catalog_path = write_catalog(root, entries)
    lifecycle_errors, lifecycle_warnings = validate_lifecycle(entries)
    result = {
        "catalog": catalog_path.relative_to(root).as_posix(),
        "report_count": len(entries),
        "sparse_count": sum(bool(entry.get("sparse")) for entry in entries),
        "source_set_hash": source_set_hash(entries),
        "lifecycle_errors": lifecycle_errors,
        "warnings": lifecycle_warnings,
    }
    print(stable_json(result))
    return 0


def command_query(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    root = Path(args.root).resolve()
    documents = discover_reports(root)
    expected_entries = build_entries(documents)
    catalog_status, entries, catalog_warnings = validate_catalog(root, expected_entries)
    lifecycle_errors, lifecycle_warnings = validate_lifecycle(entries)
    if lifecycle_errors:
        catalog_status = "invalid-lifecycle-fallback"
        entries = expected_entries
    warnings = [*catalog_warnings, *lifecycle_errors, *lifecycle_warnings]
    raw_query = " ".join(args.terms).strip()
    ranked = rank_entries(entries, documents, raw_query)
    elapsed_ms = (time.perf_counter() - started) * 1000
    data = bounded_query_payload(
        raw_query=raw_query,
        catalog_status=catalog_status,
        warnings=warnings,
        ranked=ranked,
        limit=args.limit,
        max_output_bytes=args.max_output_bytes,
        elapsed_ms=elapsed_ms,
    )
    sys.stdout.buffer.write(data)
    return 0


def command_check(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    documents = discover_reports(root)
    expected_entries = build_entries(documents)
    catalog_status, _entries, catalog_errors = validate_catalog(root, expected_entries)
    lifecycle_errors, lifecycle_warnings = validate_lifecycle(expected_entries)
    errors = unique_nonempty([*catalog_errors, *lifecycle_errors])
    result = {
        "ok": not errors and catalog_status == "current",
        "catalog_status": catalog_status,
        "report_count": len(expected_entries),
        "sparse_count": sum(bool(entry.get("sparse")) for entry in expected_entries),
        "errors": errors,
        "warnings": lifecycle_warnings,
    }
    print(stable_json(result))
    return 0 if result["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build, query, and validate a derived search index for goal execution reports."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=".", help="Repository root (default: current directory)")

    sync_parser = subparsers.add_parser("sync", parents=[common], help="Rebuild catalog.jsonl")
    sync_parser.set_defaults(handler=command_sync)

    query_parser = subparsers.add_parser("query", parents=[common], help="Search catalog and raw reports")
    query_parser.add_argument("terms", nargs="+", help="Search terms or phrase")
    query_parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Maximum candidate count")
    query_parser.add_argument(
        "--max-output-bytes",
        type=int,
        default=DEFAULT_MAX_OUTPUT_BYTES,
        help="Hard byte cap for the JSON response",
    )
    query_parser.set_defaults(handler=command_query)

    check_parser = subparsers.add_parser("check", parents=[common], help="Validate catalog and lifecycle links")
    check_parser.set_defaults(handler=command_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "limit", 1) < 1 or getattr(args, "limit", 1) > 100:
        parser.error("--limit must be between 1 and 100")
    if getattr(args, "max_output_bytes", DEFAULT_MAX_OUTPUT_BYTES) < 256:
        parser.error("--max-output-bytes must be at least 256")
    try:
        return int(args.handler(args))
    except ReportIndexError as error:
        print(stable_json({"error": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
