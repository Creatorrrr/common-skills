#!/usr/bin/env python3
"""One approved Responses API analysis, with immutable inputs and explicit lifecycle.
No automatic transport/model fallback, no SDK retries, no repository code execution.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
from time import monotonic, sleep
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from analysis_contract import audit_instructions, contract_for, render_request_contract, canonical_hash  # noqa: E402
from analysis_run import resolve_tool_output_dir  # noqa: E402
from context_integrity import (read_manifest, verify_manifest, resolve_selection, selected_paths,  # noqa: E402
    selection_hash, execution_options, validate_approval, write_json, checked_file, NORMALIZATION_VERSION)
from model_profiles import reasoning_config, enforce_token_budget  # noqa: E402
from api_resources import normalized_documents, OwnedResources, upload_documents, verify_reused_store  # noqa: E402
from run_attempt import Attempt  # noqa: E402

DEFAULTS = {
    "model": "gpt-6-astra", "reasoning_mode": "auto", "reasoning_effort": "max",
    "reasoning_context": "auto", "verbosity": "medium", "background": False, "store": False,
    "direct_input_max_bytes": 45_000_000, "direct_input_max_files": 200,
    "file_search_max_num_results": 24, "poll_interval_seconds": 5, "env_file": "",
}


def require_openai() -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Install the official OpenAI Python SDK in your environment: python -m pip install -U openai") from exc
    return OpenAI


def load_env_file(path: Path) -> None:
    # Only an explicitly selected trusted env file is read. Never execute shell syntax.
    if not path.is_file() or path.is_symlink():
        raise ValueError("Explicit env file is missing or is a symlink.")
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("export "):
            line = line[7:].strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() != "OPENAI_API_KEY":
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault("OPENAI_API_KEY", value)


def ensure_openai_api_key(env_file: Path | None = None) -> None:
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise ValueError("OPENAI_API_KEY is not configured. Set it securely outside the repository; never paste it into a prompt.")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


save_json = write_json


def serialize_sdk_object(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: serialize_sdk_object(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [serialize_sdk_object(v) for v in obj]
    if hasattr(obj, "__dict__"):
        return serialize_sdk_object(vars(obj))
    return obj


def build_instructions() -> str:
    return audit_instructions()


def build_user_prompt(goal: str, recommendation: str, warnings: list[str], mode: str,
                      manifest: dict[str, Any] | None = None) -> str:
    manifest = manifest or {}
    return "\n".join([
        render_request_contract(manifest, goal),
        "Prepared context:",
        f"- snapshot_id: {manifest.get('snapshot_id', 'not supplied')}",
        f"- execution mode: {mode}; preparation recommendation: {recommendation}",
        "- direct mode provides the complete selected normalized source as text.",
        "- retrieval mode provides every selected source as UTF-8 text fragments; use file_search to inspect concrete evidence.",
        "- selected/available is not equivalent to inspected/verified.",
        "- cite original_path and original line numbers from fragment headers, not the generated .txt filename.",
        "Local warnings:", *["- " + x for x in warnings],
        "Start with the verdict unless the user's requested format says otherwise.",
    ])


def build_reasoning_config(args: argparse.Namespace) -> dict[str, str]:
    return reasoning_config(getattr(args, "model", DEFAULTS["model"]), args.reasoning_mode,
                            args.reasoning_effort, args.reasoning_context)


def compute_pro_poll_interval_seconds(elapsed_seconds: int) -> int:
    if elapsed_seconds < 1800:
        return 60
    if elapsed_seconds < 2400:
        return 45
    if elapsed_seconds < 3000:
        return 30
    return 15


def poll_response(client: Any, response: Any, interval_seconds: int, reasoning_mode: str,
                  timeout_seconds: float = 7200) -> Any:
    started = monotonic()
    while getattr(response, "status", None) in {"queued", "in_progress"}:
        elapsed = max(0, monotonic() - started)
        if elapsed >= timeout_seconds:
            raise TimeoutError("Response polling timed out. The owned response will be cancelled where possible; no retry.")
        interval = compute_pro_poll_interval_seconds(int(elapsed)) if reasoning_mode == "pro" else interval_seconds
        sleep(min(interval, timeout_seconds - elapsed))
        response = client.responses.retrieve(response.id)
    return response


def completed_output_text(response: Any) -> tuple[str | None, str | None]:
    status = getattr(response, "status", None)
    if status != "completed":
        return None, f"response_status={status or 'unknown'}"
    text = getattr(response, "output_text", None)
    if not isinstance(text, str) or not text.strip():
        return None, "completed_response_missing_output_text"
    return text, None


def select_direct_input_files(
    manifest: dict,
    repo_root: Path,
    preferred_key: str = "full",
    max_total_bytes: int = DEFAULTS["direct_input_max_bytes"],
    max_files: int = DEFAULTS["direct_input_max_files"],
) -> list[dict[str, Any]]:
    selections = manifest.get("selections", {})
    artifacts = manifest.get("artifacts", {})
    selected: list[dict[str, Any]] = []
    selected_paths: set[Path] = set()
    total_bytes = 0

    def add_required(path: Path, logical_path: str) -> None:
        nonlocal total_bytes
        if len(selected) >= max_files:
            raise ValueError(
                f"Direct context requires more than {max_files} input files. "
                "Choose file_search_full or prepare fewer lossless context shards."
            )
        if path in selected_paths:
            return
        if not path.exists() or not path.is_file():
            raise ValueError(f"Required direct input file is missing: {logical_path}")
        size = path.stat().st_size
        if size <= 0:
            raise ValueError(f"Required direct input file is empty: {logical_path}")
        if size > max_total_bytes:
            raise ValueError(
                f"Required direct input file exceeds the {max_total_bytes:,}-byte request budget: "
                f"{logical_path} ({size:,} bytes)."
            )
        if total_bytes + size > max_total_bytes:
            raise ValueError(
                f"Complete direct context exceeds the {max_total_bytes:,}-byte request budget. "
                "Choose file_search_full instead of sending a partial direct request."
            )
        selected.append({
            "logical_path": logical_path,
            "path": str(path),
            "size": size,
        })
        selected_paths.add(path)
        total_bytes += size

    repo_tree_value = artifacts.get("repo_tree")
    if repo_tree_value:
        repo_tree_path = Path(repo_tree_value).resolve()
        add_required(repo_tree_path, "__analysis_context__/repo_tree.txt")

    selection_report_value = artifacts.get("selection_report")
    if selection_report_value:
        selection_report_path = Path(selection_report_value).resolve()
        add_required(selection_report_path, "__analysis_context__/selection-report.md")

    shard_paths = list(artifacts.get(f"{preferred_key}_context_shards") or [])
    if shard_paths:
        selected_rel_paths = set(selections.get(f"{preferred_key}_files") or [])
        lossy_paths = sorted(
            record.get("path", "")
            for record in manifest.get("files", [])
            if record.get("path") in selected_rel_paths and record.get("inline_truncated")
        )
        if lossy_paths:
            sample = ", ".join(lossy_paths[:20])
            raise ValueError(
                "Prepared direct-context shards are lossy. Rerun prepare_analysis_context.py with the current helper "
                f"before a direct analysis. Truncated paths: {sample}"
            )
        for index, shard_value in enumerate(shard_paths, start=1):
            shard_path = Path(shard_value).resolve()
            add_required(shard_path, f"__analysis_context__/{preferred_key}-context-{index:03d}.md")
    else:
        rel_paths = list(selections.get(f"{preferred_key}_files") or [])
        if not rel_paths:
            raise ValueError(f"No {preferred_key} direct-context selection exists in the manifest.")
        for rel_path in rel_paths:
            abs_path = (repo_root / rel_path).resolve()
            add_required(abs_path, rel_path)

    return selected



def upload_vector_store_files(client: Any, vector_store_name: str, root: Path,
                              rel_paths: list[str]) -> tuple[Any, list[dict[str, Any]]]:
    """Compatibility helper. Production main always supplies preverified snapshot bytes.
    Prevalidate ALL paths before creating even one external resource.
    """
    contents = {p: checked_file(root, p).read_bytes() for p in rel_paths}
    documents = normalized_documents(contents, rel_paths)
    owned = OwnedResources(client)
    try:
        return upload_documents(client, vector_store_name, documents, owned=owned,
                                snapshot_id=canonical_hash({p: d.hex() for p, d in contents.items()}),
                                selection_hash=canonical_hash(sorted(rel_paths)))
    except BaseException:
        owned.cleanup()
        raise


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", required=True)
    p.add_argument("--goal", default="", help="Must equal the prepared contract; reprepare when the request changes.")
    p.add_argument("--mode", choices=["auto", "direct", "file_search_full", "focused_file_search"], default="auto")
    p.add_argument("--model", default=DEFAULTS["model"])
    p.add_argument("--reasoning-mode", choices=["auto", "standard", "pro"], default=DEFAULTS["reasoning_mode"])
    p.add_argument("--reasoning-effort", choices=["none", "low", "medium", "high", "xhigh", "max"], default=DEFAULTS["reasoning_effort"])
    p.add_argument("--reasoning-context", choices=["auto", "current_turn", "all_turns"], default="auto")
    p.add_argument("--verbosity", choices=["low", "medium", "high"], default="medium")
    p.add_argument("--background", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--store", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--resource-retention", choices=["delete", "retain"], default="delete")
    p.add_argument("--expires-days", type=int, default=1, help="1..30; applies to newly created file/store fallback expiration.")
    p.add_argument("--max-output-tokens", type=int, default=32000)
    p.add_argument("--max-tool-calls", type=int, default=12)
    p.add_argument("--file-search-max-num-results", type=int, default=24)
    p.add_argument("--poll-interval-seconds", type=int, default=5)
    p.add_argument("--timeout-seconds", type=float, default=7200)
    p.add_argument("--ingestion-timeout-seconds", type=float, default=1800)
    p.add_argument("--env-file", default="", help="Optional explicitly trusted env file; never loaded automatically.")
    p.add_argument("--approval", help="Snapshot-bound approval JSON recorded after the user authorizes transmission.")
    p.add_argument("--dry-run", action="store_true", help="Local validation only; no SDK, credentials, uploads, or token-count API calls.")
    p.add_argument("--previous-response-id", default="")
    p.add_argument("--previous-run-meta", default="")
    p.add_argument("--vector-store-id", default="")
    p.add_argument("--reuse-receipt", default="")
    p.add_argument("--out-dir", default=".codex-analysis/gpt-pro")
    return p


def resolve_run(args: argparse.Namespace, manifest: dict[str, Any]) -> tuple[str, str]:
    contract_for(manifest, args.goal)
    args.resolved_reasoning = build_reasoning_config(args)
    mode = args.mode
    if mode == "auto":
        mode = manifest.get("mode_recommendation", "direct")
    if mode == "direct_warn":
        mode = "direct"
    key = resolve_selection(manifest, mode)
    args.resolved_mode = mode
    if not 1 <= args.expires_days <= 30:
        raise ValueError("expires-days must be between 1 and 30.")
    if args.timeout_seconds <= 0 or args.ingestion_timeout_seconds <= 0 or args.poll_interval_seconds <= 0:
        raise ValueError("Timeout and polling values must be positive.")
    if not 1 <= args.file_search_max_num_results <= 50 or args.max_tool_calls < 1:
        raise ValueError("Invalid file-search result or tool-call budget.")
    enforce_token_budget(args.model, 0, args.max_output_tokens)
    if args.previous_response_id:
        if not args.previous_run_meta:
            raise ValueError("previous-response-id requires --previous-run-meta for identity/retention checks.")
        prior = load_json(Path(args.previous_run_meta))
        if (prior.get("response_id") != args.previous_response_id or prior.get("snapshot_id") != manifest["snapshot_id"]
            or prior.get("model") != args.model or prior.get("response_status") != "completed"
            or prior.get("contract_hash") != canonical_hash(contract_for(manifest))
            or prior.get("selection_hash") != selection_hash(manifest, key)
            or prior.get("execution_options", {}).get("store") is not True):
            raise ValueError("Previous response is not a stored, completed response for the same snapshot, selection, contract and model.")
    if args.vector_store_id and (mode == "direct" or not args.reuse_receipt):
        raise ValueError("Vector-store reuse requires retrieval mode and a matching --reuse-receipt.")
    return mode, key


def request_token_count(client: Any, request: dict[str, Any]) -> int:
    fields = ("model", "instructions", "input", "tools", "previous_response_id", "reasoning")
    result = client.responses.input_tokens.count(**{k: request[k] for k in fields if k in request})
    count = getattr(result, "input_tokens", None)
    if isinstance(count, bool) or not isinstance(count, int):
        raise ValueError("Token count API returned no usable count. Submission refused.")
    return count


def coverage_ledger(manifest: dict[str, Any], key: str, mode: str, response: Any,
                    uploads: list[dict[str, Any]]) -> dict[str, Any]:
    data = serialize_sdk_object(response)
    returned_ids: set[str] = set()
    for item in data.get("output", []):
        if item.get("type") == "file_search_call":
            for result in item.get("results") or []:
                if result.get("file_id"):
                    returned_ids.add(result["file_id"])
    returned_paths = sorted({u["path"] for u in uploads if u["file_id"] in returned_ids})
    return {"snapshot_id": manifest["snapshot_id"], "available_files": selected_paths(manifest, key),
            "selection": key, "input_mode": mode, "search_returned_files": returned_paths,
            "returned_is_not_inspected": True, "analysis_validation": "pending",
            "local_verification": "pending", "verification_notes": []}


def execute(args: argparse.Namespace, client_factory: Any = None) -> int:
    manifest_path = Path(args.manifest).resolve()
    try:
        manifest = read_manifest(manifest_path)
    except Exception:
        # Even an unreadable manifest must not leave a stale active success in the requested output.
        with Attempt(Path(args.out_dir).resolve(), {"transport": "responses_api", "manifest": str(manifest_path)}):
            raise
    out_dir = resolve_tool_output_dir(manifest_path=manifest_path, manifest=manifest, tool_name="gpt-pro",
        requested_out_dir=Path(args.out_dir), default_out_dir=Path(".codex-analysis/gpt-pro"))
    base = {"transport": "responses_api", "run_id": manifest.get("run_id"),
            "snapshot_id": manifest.get("snapshot_id"), "model": args.model}
    with Attempt(out_dir, base) as attempt:
        contents = verify_manifest(manifest)
        mode, key = resolve_run(args, manifest)
        options = execution_options(args)
        attempt.meta.update(mode=mode, selection=key, input_validation="passed", execution_options=options,
                            contract_hash=canonical_hash(contract_for(manifest)), selection_hash=selection_hash(manifest, key))
        attempt.save()
        paths = selected_paths(manifest, key)
        documents = normalized_documents(contents, paths)
        summary = {"binding": {"snapshot_id": manifest["snapshot_id"], "selection_hash": selection_hash(manifest, key)},
                   "execution_options": options, "selected_file_count": len(paths),
                   "normalized_document_count": len(documents), "warnings": manifest.get("warnings", []),
                   "network_calls_performed": False,
                   "retention_notice": "store=false is not Zero Data Retention; files, vector stores, background polling, and provider safety retention are distinct."}
        write_json(out_dir / "request_summary.json", summary)
        if args.dry_run:
            attempt.meta.update(status="dry_run_completed", analysis_validation="not_run", local_verification="not_run")
            attempt.save()
            print(json.dumps(attempt.meta, indent=2))
            return 0
        if not args.approval:
            raise ValueError("--approval is required before any network or token-count request. Record actual user authorization first.")
        approval = load_json(Path(args.approval))
        validate_approval(approval, manifest, key, "responses_api", options)
        write_json(out_dir / "approval_used.json", approval)
        if args.env_file:
            load_env_file(Path(args.env_file).expanduser().resolve())
        ensure_openai_api_key()
        factory = client_factory or require_openai()
        client = factory(base_url="https://api.openai.com/v1", max_retries=0, timeout=args.timeout_seconds)
        summary["network_calls_performed"] = True
        save_json(out_dir / "request_summary.json", summary)
        owned = OwnedResources(client, out_dir / "owned_resources.json")
        response = None
        uploads: list[dict[str, Any]] = []
        normal_success = False
        try:
            instructions = build_instructions()
            prompt = build_user_prompt(args.goal or manifest["goal"], manifest["mode_recommendation"], manifest.get("warnings", []), mode, manifest)
            request: dict[str, Any] = {
                "model": args.model, "instructions": instructions,
                "reasoning": args.resolved_reasoning, "text": {"verbosity": args.verbosity},
                "store": args.store, "background": args.background,
                "max_output_tokens": args.max_output_tokens, "truncation": "disabled",
            }
            if args.previous_response_id:
                request["previous_response_id"] = args.previous_response_id
            if mode == "direct":
                payload = "\n".join(d["data"].decode("utf-8") for d in documents)
                if len(payload.encode("utf-8")) > DEFAULTS["direct_input_max_bytes"]:
                    raise ValueError("Complete direct text exceeds the local byte budget; choose full retrieval explicitly.")
                request["input"] = [{"role": "user", "content": [
                    {"type": "input_text", "text": payload}, {"type": "input_text", "text": prompt}]}]
            else:
                digest = selection_hash(manifest, key)
                if args.vector_store_id:
                    receipt = load_json(Path(args.reuse_receipt))
                    vs = verify_reused_store(client, args.vector_store_id, receipt, documents, manifest["snapshot_id"], digest)
                    uploads = receipt["files"]
                else:
                    vs, uploads = upload_documents(client, f"codebase-{manifest['run_id']}-{key}", documents,
                        owned=owned, snapshot_id=manifest["snapshot_id"], selection_hash=digest,
                        expires_days=args.expires_days, timeout_seconds=args.ingestion_timeout_seconds)
                receipt = {"vector_store_id": vs.id, "binding": {"snapshot_id": manifest["snapshot_id"],
                           "selection_hash": digest, "normalization": NORMALIZATION_VERSION}, "files": uploads}
                write_json(out_dir / "vector_store_uploads.json", receipt)
                attempt.meta["vector_store_id"] = vs.id
                request["input"] = [{"role": "user", "content": [
                    {"type": "input_text", "text": "Selected repository map (orientation only):\n" + json.dumps(paths, ensure_ascii=True)},
                    {"type": "input_text", "text": prompt}]}]
                request["tools"] = [{"type": "file_search", "vector_store_ids": [vs.id],
                                     "max_num_results": args.file_search_max_num_results}]
                request["include"] = ["file_search_call.results"]
                request["max_tool_calls"] = args.max_tool_calls
            count = request_token_count(client, request)
            # Retrieval adds dynamic context after this initial request. Reserve a conservative
            # operational margin, not an assertion about all future server-side token usage.
            retrieval_reserve = 0 if mode == "direct" else args.max_tool_calls * args.file_search_max_num_results * 1312
            report = enforce_token_budget(args.model, count, args.max_output_tokens, 8192 + retrieval_reserve)
            report["dynamic_retrieval_reserve"] = retrieval_reserve
            report["count_scope"] = "initial request including attached input text and prior response when used"
            write_json(out_dir / "token_report.json", report)
            attempt.meta.update(status="request_in_flight", exact_input_tokens=count)
            attempt.save()
            response = client.responses.create(**request)
            owned.response_id = response.id
            owned.flush()
            attempt.meta.update(response_id=response.id, response_status=response.status)
            attempt.save()
            if response.status in {"queued", "in_progress"}:
                response = poll_response(client, response, args.poll_interval_seconds,
                                         args.resolved_reasoning.get("mode", "native"), args.timeout_seconds)
            write_json(out_dir / "response.json", serialize_sdk_object(response))
            attempt.meta["response_status"] = getattr(response, "status", None)
            output, reason = completed_output_text(response)
            if reason:
                raise ValueError(reason)
            (out_dir / "analysis_report.md").write_text(output, encoding="utf-8")
            write_json(out_dir / "coverage_ledger.json", coverage_ledger(manifest, key, mode, response, uploads))
            attempt.meta.update(status="response_completed", report_path=str(out_dir / "analysis_report.md"),
                                analysis_validation="pending", local_verification="pending")
            normal_success = True
        finally:
            if response is not None and getattr(response, "status", None) in {"queued", "in_progress"}:
                try:
                    cancelled = client.responses.cancel(response.id)
                    attempt.meta["cancellation_status"] = getattr(cancelled, "status", "unknown")
                except Exception as exc:
                    attempt.meta["cancellation_status"] = "unconfirmed"
                    attempt.meta["cancellation_error_type"] = type(exc).__name__
            cleanup = owned.cleanup(retain=normal_success and args.resource_retention == "retain")
            write_json(out_dir / "cleanup_report.json", cleanup)
            attempt.meta["cleanup_status"] = cleanup["status"]
            if cleanup["status"] == "incomplete":
                attempt.meta["status"] = "response_completed_cleanup_incomplete" if normal_success else "failed_cleanup_incomplete"
            attempt.save()
        print(json.dumps(attempt.meta, indent=2))
        return 2 if attempt.meta["cleanup_status"] == "incomplete" else 0


def main() -> int:
    args = build_parser().parse_args()
    try:
        return execute(args)
    except (Exception, KeyboardInterrupt) as exc:
        safe = str(exc) if isinstance(exc, (ValueError, TimeoutError)) else type(exc).__name__
        print(f"[error] {safe}", file=sys.stderr)
        return 130 if isinstance(exc, KeyboardInterrupt) else 1


if __name__ == "__main__":
    raise SystemExit(main())
