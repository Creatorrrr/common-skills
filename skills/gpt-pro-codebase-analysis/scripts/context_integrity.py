"""Snapshot verification, exact selection, and machine-checkable approval binding.
Hashes detect corruption/drift, not a malicious local user who can rewrite the manifest.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any
from analysis_contract import canonical_hash, contract_for

SCHEMA_VERSION = 2
NORMALIZATION_VERSION = "utf8-numbered-v1"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_relative(value: str) -> str:
    p = PurePosixPath(value)
    if not value or p.is_absolute() or ".." in p.parts or "\\" in value or ":" in value or value != p.as_posix():
        raise ValueError(f"Unsafe/noncanonical relative path: {value!r}")
    if any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise ValueError(f"Unsupported control/non-Unicode path: {value!r}")
    return value


def checked_file(root: Path, relative: str) -> Path:
    relative = safe_relative(relative)
    root = root.resolve()
    current = root
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Symlink is not an immutable input: {relative!r}")
    if not current.is_file() or not current.resolve().is_relative_to(root):
        raise ValueError(f"Required snapshot file is missing or unsafe: {relative!r}")
    return current


def hydrate_manifest(manifest: dict[str, Any], manifest_path: Path) -> dict[str, Any]:
    """Rebase artifact pointers after archiving without rewriting any snapshot bytes."""
    result = copy.deepcopy(manifest)
    context_root = manifest_path.resolve().parent
    old_root = Path(result.get("context_root") or context_root)
    for key, value in result.get("artifacts", {}).items():
        def rebase(item: str) -> str:
            p = Path(item)
            if p.is_absolute():
                try:
                    rel = p.relative_to(old_root).as_posix()
                except ValueError as exc:
                    raise ValueError(f"Artifact outside prepared context: {key}") from exc
            else:
                rel = p.as_posix()
            return str(context_root / safe_relative(rel))
        if isinstance(value, str):
            result["artifacts"][key] = rebase(value)
        elif isinstance(value, list):
            result["artifacts"][key] = [rebase(x) for x in value]
    result["context_root"] = str(context_root)
    result["_manifest_path"] = str(manifest_path.resolve())
    return result


def snapshot_identity(records: list[dict[str, Any]]) -> str:
    return canonical_hash(sorted(
        [{"path": x["path"], "sha256": x["sha256"], "size": x["size"]}
         for x in records if x["status"] == "included"], key=lambda x: x["path"]))


def resolve_selection(manifest: dict[str, Any], requested: str = "auto") -> str:
    aliases = {"direct": "full", "direct_warn": "full", "file_search_full": "full", "focused_file_search": "focused"}
    prepared = manifest.get("preparation_mode", "auto")
    if requested == "auto":
        key = prepared if prepared in {"full", "focused"} else aliases.get(manifest.get("mode_recommendation"), "full")
    else:
        key = aliases.get(requested, requested)
    if key not in {"full", "focused"}:
        raise ValueError(f"Unknown selection: {requested}")
    if prepared in {"full", "focused"} and key != prepared:
        raise ValueError(f"Prepared {prepared} selection cannot silently change to {key}; reprepare with the authorized scope.")
    return key


def selected_paths(manifest: dict[str, Any], key: str) -> list[str]:
    paths = list(manifest.get("selections", {}).get(f"{key}_files", []))
    if not paths or len(paths) != len(set(paths)):
        raise ValueError("Selection is empty or contains duplicate paths.")
    for p in paths:
        safe_relative(p)
    return paths


def verify_manifest(manifest: dict[str, Any]) -> dict[str, bytes]:
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("A v2 snapshot manifest is required. Re-run prepare_analysis_context.py; legacy manifests are not trusted for upload.")
    if manifest.get("blocking_issues"):
        raise ValueError("Preparation has blocking issues: " + "; ".join(manifest["blocking_issues"]))
    root = Path(manifest["context_root"])
    records = manifest["files"]
    included = [r for r in records if r["status"] == "included"]
    paths = [r["path"] for r in included]
    if len(set(paths)) != len(paths) or set(paths) != set(selected_paths(manifest, "full")):
        raise ValueError("Full selection does not exactly match included snapshot records.")
    if not set(selected_paths(manifest, "focused")).issubset(paths):
        raise ValueError("Focused selection contains unrecorded files.")
    if snapshot_identity(records) != manifest.get("snapshot_id"):
        raise ValueError("Snapshot identity does not match its records.")
    data: dict[str, bytes] = {}
    for rec in included:
        p = checked_file(root, rec["snapshot_path"])
        raw = p.read_bytes()
        if len(raw) != rec["size"] or sha256_bytes(raw) != rec["sha256"]:
            raise ValueError(f"Snapshot content hash mismatch: {rec['path']}")
        data[rec["path"]] = raw
    digests = manifest.get("artifact_digests", {})
    referenced: list[str] = []
    for value in manifest.get("artifacts", {}).values():
        values = value if isinstance(value, list) else [value] if isinstance(value, str) else []
        for item in values:
            p = Path(item)
            rel = p.relative_to(root).as_posix()
            if rel not in digests:
                raise ValueError(f"Artifact has no recorded digest: {rel}")
            referenced.append(rel)
    for rel, digest in digests.items():
        if sha256_bytes(checked_file(root, rel).read_bytes()) != digest:
            raise ValueError(f"Prepared artifact hash mismatch: {rel}")
    if not referenced:
        raise ValueError("No verified context artifacts exist.")
    return data


def read_manifest(path: Path) -> dict[str, Any]:
    return hydrate_manifest(json.loads(path.read_text(encoding="utf-8")), path)


def selection_hash(manifest: dict[str, Any], key: str) -> str:
    return canonical_hash({"snapshot_id": manifest["snapshot_id"], "paths": sorted(selected_paths(manifest, key))})


def binding(manifest: dict[str, Any], key: str) -> dict[str, Any]:
    return {"run_id": manifest["run_id"], "snapshot_id": manifest["snapshot_id"], "selection": key,
            "selection_hash": selection_hash(manifest, key),
            "contract_hash": canonical_hash(contract_for(manifest)),
            "exclusions_hash": canonical_hash([{"path": r["path"], "reasons": r["reasons"]}
                                                 for r in manifest["files"] if r["status"] != "included"])}


def validate_approval(approval: dict[str, Any], manifest: dict[str, Any], key: str,
                      transport: str, options: dict[str, Any]) -> None:
    if approval.get("schema_version") != 1 or approval.get("approved") is not True:
        raise ValueError("Explicit external-transmission approval is required.")
    if approval.get("transport") != transport:
        raise ValueError("Approval is for a different transport; no automatic fallback.")
    if approval.get("binding") != binding(manifest, key):
        raise ValueError("Approval does not match this snapshot, scope, exclusions, or request contract.")
    if approval.get("execution_options") != options:
        raise ValueError("Execution/model/retention settings differ from the recorded approval.")
    if approval.get("selection_reviewed") is not True:
        raise ValueError("Selection and exclusions must be reviewed before external transmission.")


def execution_options(args: Any) -> dict[str, Any]:
    return {"mode": args.resolved_mode, "model": args.model, "reasoning": args.resolved_reasoning,
            "verbosity": args.verbosity, "background": args.background, "store": args.store,
            "resource_retention": args.resource_retention, "expires_days": args.expires_days,
            "max_output_tokens": args.max_output_tokens, "max_tool_calls": args.max_tool_calls,
            "file_search_max_num_results": args.file_search_max_num_results,
            "previous_response_id": args.previous_response_id or None,
            "vector_store_id": args.vector_store_id or None}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=True, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)
