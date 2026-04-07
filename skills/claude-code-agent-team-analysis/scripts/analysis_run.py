from __future__ import annotations

import json
import secrets
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ACTIVE_DIR_NAMES = ("context", "claude-code")
DEFAULT_ANALYSIS_ROOT_NAME = ".codex-analysis"
LAYOUT_VERSION = 1
TEXT_REWRITE_SUFFIXES = {".json", ".log", ".md", ".txt"}


@dataclass(frozen=True)
class PrepareRunLayout:
    run_id: str
    analysis_root: Path
    history_root: Path
    layout_version: int
    archived_previous_run_id: str | None
    managed: bool


@dataclass(frozen=True)
class ManifestLayout:
    run_id: str | None
    analysis_root: Path | None
    history_root: Path | None
    run_root: Path | None
    is_archived: bool
    managed: bool


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def generate_run_id(prefix: str | None = None) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = secrets.token_hex(3)
    if prefix:
        return f"{prefix}-{stamp}-{suffix}"
    return f"{stamp}-{suffix}"


def path_is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
        return True
    except ValueError:
        return False


def find_analysis_root(path: Path) -> Path | None:
    resolved = path.resolve()
    for candidate in (resolved, *resolved.parents):
        if candidate.name == DEFAULT_ANALYSIS_ROOT_NAME:
            return candidate
    return None


def infer_analysis_root_for_manifest(out_dir: Path) -> Path:
    managed_root = find_analysis_root(out_dir)
    if managed_root is not None:
        return managed_root
    return out_dir.parent.resolve()


def _read_run_id_from_manifest(manifest_path: Path) -> str | None:
    if not manifest_path.exists():
        return None
    try:
        manifest = load_json(manifest_path)
    except (json.JSONDecodeError, OSError):
        return None
    run_id = manifest.get("run_id")
    if isinstance(run_id, str) and run_id.strip():
        return run_id.strip()
    return None


def _allocate_archive_run_id(history_root: Path, run_id: str) -> str:
    candidate = run_id
    attempt = 2
    while (history_root / candidate).exists():
        candidate = f"{run_id}-{attempt}"
        attempt += 1
    return candidate


def _rewrite_archived_paths(archive_root: Path, replacements: dict[str, str]) -> None:
    ordered_pairs = sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True)
    for path in archive_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_REWRITE_SUFFIXES:
            continue
        try:
            original = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rewritten = original
        for old, new in ordered_pairs:
            rewritten = rewritten.replace(old, new)
        if rewritten != original:
            path.write_text(rewritten, encoding="utf-8")


def archive_active_run(analysis_root: Path) -> str | None:
    active_dirs = {
        name: (analysis_root / name)
        for name in ACTIVE_DIR_NAMES
        if (analysis_root / name).exists()
    }
    if not active_dirs:
        return None

    history_root = analysis_root / "history"
    history_root.mkdir(parents=True, exist_ok=True)
    manifest_path = analysis_root / "context" / "manifest.json"
    run_id = _read_run_id_from_manifest(manifest_path) or generate_run_id(prefix="legacy")
    archive_run_id = _allocate_archive_run_id(history_root, run_id)
    archive_root = history_root / archive_run_id

    replacements: dict[str, str] = {}
    for name, source in active_dirs.items():
        target = archive_root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        replacements[str(source.resolve())] = str(target.resolve())

    _rewrite_archived_paths(archive_root, replacements)
    return archive_run_id


def prepare_run_layout(out_dir: Path) -> PrepareRunLayout:
    resolved_out_dir = out_dir.resolve()
    analysis_root = infer_analysis_root_for_manifest(resolved_out_dir)
    managed = analysis_root.name == DEFAULT_ANALYSIS_ROOT_NAME
    archived_previous_run_id = archive_active_run(analysis_root) if managed else None
    return PrepareRunLayout(
        run_id=generate_run_id(),
        analysis_root=analysis_root,
        history_root=analysis_root / "history",
        layout_version=LAYOUT_VERSION,
        archived_previous_run_id=archived_previous_run_id,
        managed=managed,
    )


def resolve_manifest_layout(manifest_path: Path, manifest: dict[str, Any]) -> ManifestLayout:
    resolved_manifest_path = manifest_path.resolve()
    analysis_root_value = manifest.get("analysis_root")
    analysis_root = Path(analysis_root_value).resolve() if isinstance(analysis_root_value, str) and analysis_root_value else find_analysis_root(resolved_manifest_path)
    if analysis_root is None:
        history_root = None
        managed = False
    else:
        history_root_value = manifest.get("history_root")
        history_root = (
            Path(history_root_value).resolve()
            if isinstance(history_root_value, str) and history_root_value
            else analysis_root / "history"
        )
        managed = analysis_root.name == DEFAULT_ANALYSIS_ROOT_NAME

    run_id = manifest.get("run_id")
    normalized_run_id = run_id.strip() if isinstance(run_id, str) and run_id.strip() else None
    run_root = None
    is_archived = False

    if managed and analysis_root is not None and history_root is not None:
        if path_is_relative_to(resolved_manifest_path, history_root):
            relative = resolved_manifest_path.relative_to(history_root)
            if relative.parts:
                archived_run_id = relative.parts[0]
                normalized_run_id = normalized_run_id or archived_run_id
                run_root = history_root / archived_run_id
                is_archived = True
        elif path_is_relative_to(resolved_manifest_path, analysis_root):
            run_root = analysis_root

    return ManifestLayout(
        run_id=normalized_run_id,
        analysis_root=analysis_root,
        history_root=history_root,
        run_root=run_root,
        is_archived=is_archived,
        managed=managed,
    )


def resolve_tool_output_dir(
    *,
    manifest_path: Path,
    manifest: dict[str, Any],
    tool_name: str,
    requested_out_dir: Path,
    default_out_dir: Path,
) -> Path:
    resolved_requested_out_dir = requested_out_dir.resolve()
    resolved_default_out_dir = default_out_dir.resolve()
    if resolved_requested_out_dir != resolved_default_out_dir:
        return resolved_requested_out_dir

    layout = resolve_manifest_layout(manifest_path, manifest)
    if not layout.managed or layout.run_root is None:
        return resolved_requested_out_dir
    return layout.run_root / tool_name


def _run_meta_matches(path: Path, run_id: str) -> bool:
    if not path.exists():
        return False
    try:
        data = load_json(path)
    except (json.JSONDecodeError, OSError):
        return False
    value = data.get("run_id")
    return isinstance(value, str) and value.strip() == run_id


def find_matching_run_meta_path(
    *,
    manifest_path: Path,
    manifest: dict[str, Any],
    active_out_dir: Path,
    tool_name: str,
) -> Path | None:
    candidate = active_out_dir / "run_meta.json"
    layout = resolve_manifest_layout(manifest_path, manifest)
    if not layout.run_id:
        return candidate if candidate.exists() else None

    if _run_meta_matches(candidate, layout.run_id):
        return candidate

    if not layout.managed or layout.history_root is None:
        return None

    archived_candidate = layout.history_root / layout.run_id / tool_name / "run_meta.json"
    if archived_candidate == candidate:
        return candidate if candidate.exists() else None
    if _run_meta_matches(archived_candidate, layout.run_id):
        return archived_candidate
    return None
