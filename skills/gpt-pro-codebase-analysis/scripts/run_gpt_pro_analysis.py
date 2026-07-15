#!/usr/bin/env python3
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

from analysis_contract import render_finding_contract, render_required_output_sections  # noqa: E402
from analysis_run import resolve_tool_output_dir  # noqa: E402


def require_openai() -> Any:
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as exc:  # pragma: no cover - runtime guidance
        raise SystemExit(
            "The official OpenAI Python SDK is required. Install it with: pip install openai"
        ) from exc
    return OpenAI


DEFAULTS = {
    "model": "gpt-5.6-sol",
    "reasoning_mode": "pro",
    "reasoning_effort": "high",
    "reasoning_context": "auto",
    "verbosity": "high",
    "background": True,
    "store": True,
    "direct_input_max_bytes": 45_000_000,
    "direct_input_max_files": 200,
    "file_search_max_num_results": 24,
    "poll_interval_seconds": 5,
    "env_file": ".env",
}


def load_env_file(path: Path) -> dict[str, str]:
    loaded: dict[str, str] = {}
    if not path.exists():
        return loaded

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value and len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key not in os.environ:
            os.environ[key] = value
        loaded[key] = value
    return loaded


def ensure_openai_api_key(env_file: Path) -> str:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if api_key:
        return api_key
    raise SystemExit(
        "OPENAI_API_KEY is not set. "
        f"Add it to the current environment or to {env_file} and rerun."
    )


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, default=str)


def serialize_sdk_object(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, (list, tuple)):
        return [serialize_sdk_object(item) for item in obj]
    return str(obj)


def build_instructions() -> str:
    sections = render_required_output_sections()
    finding_fields = render_finding_contract()
    return "\n".join(
        [
            "Act as a senior repository auditor. Produce an evidence-driven engineering analysis of the provided repository context.",
            "",
            "Evidence contract:",
            "- Treat the provided repository files as the only source of truth.",
            "- Do not make repository-wide claims unless the inspected coverage supports them.",
            f"- Each finding must contain: {finding_fields}.",
            "- Cite path:line only when stable line information exists; otherwise cite path and symbol or section. Never invent line numbers.",
            "- A claim that logic is missing, dead, duplicate, deprecated, or unused must check definitions, callers or wiring, configuration, and relevant tests. Otherwise label it unconfirmed.",
            "- Put unsupported questions under Unknowns and missing context instead of guessing.",
            "",
            "Method:",
            "1. Map only the modules and runtime boundaries relevant to the goal.",
            "2. Trace one to three concrete end-to-end workflows that matter to the goal.",
            "3. Rank the most consequential findings and check each against callers, tests, and configuration.",
            "4. State which relevant areas were not inspected.",
            "",
            "Required output sections unless the user requests another format:",
            sections,
        ]
    )


def build_user_prompt(
    goal: str,
    recommendation: str,
    warnings: list[str],
    mode: str,
    manifest: dict[str, Any] | None = None,
) -> str:
    manifest = manifest or {}
    warning_block = "\n".join(f"- {item}" for item in warnings) if warnings else "- none"
    if mode == "direct":
        has_shards = bool(manifest.get("artifacts", {}).get("full_context_shards"))
        direct_sources = "lossless selected-source context shards" if has_shards else "the complete selected raw-file set"
        context_block = f"A repository map, selection audit, and {direct_sources} are attached as input_file items."
    elif mode in {"file_search_full", "focused_file_search"}:
        context_block = "A repository map is included for orientation and selected raw files are available through file_search. Retrieve entrypoints, wiring, tests, and configuration before making important claims."
    else:
        context_block = "Repository context is provided through attachments or retrieval."

    stats = manifest.get("stats", {})
    scope = ", ".join(manifest.get("scope", [])) or "(none provided)"
    return "\n".join(
        [
            "Goal:",
            goal or "(none provided)",
            "",
            "Prepared context:",
            f"- execution mode: {mode}",
            f"- local recommendation: {recommendation}",
            f"- explicit scope: {scope}",
            f"- selected full files: {stats.get('included_file_count', 'unknown')}",
            f"- selected focused files: {stats.get('focused_file_count', 'unknown')}",
            f"- context contract: {context_block}",
            "",
            "Local warnings:",
            warning_block,
            "",
            "Start with the verdict. Keep the report concise enough to prioritize action, while preserving evidence and material caveats.",
        ]
    )


def compute_pro_poll_interval_seconds(elapsed_seconds: int) -> int:
    if elapsed_seconds < 1800:
        return 60
    if elapsed_seconds < 2400:
        return 45
    if elapsed_seconds < 3000:
        return 30
    return 15


def build_reasoning_config(args: argparse.Namespace) -> dict[str, str]:
    if args.reasoning_mode == "pro" and args.reasoning_effort in {"none", "low"}:
        raise ValueError("GPT-5.6 Pro mode requires reasoning effort medium or higher.")
    config = {
        "mode": args.reasoning_mode,
        "effort": args.reasoning_effort,
    }
    if args.reasoning_context != "auto":
        config["context"] = args.reasoning_context
    return config


def poll_response(client: Any, response: Any, interval_seconds: int, reasoning_mode: str) -> Any:
    poll_started_at = monotonic()
    use_pro_schedule = reasoning_mode == "pro"

    while getattr(response, "status", None) in {"queued", "in_progress"}:
        print(f"[info] Response status: {response.status}", file=sys.stderr)
        if use_pro_schedule:
            elapsed_seconds = int(max(0, monotonic() - poll_started_at))
            next_interval = compute_pro_poll_interval_seconds(elapsed_seconds)
        else:
            next_interval = interval_seconds
        sleep(next_interval)
        response = client.responses.retrieve(response.id)
    if getattr(response, "status", None) != "completed":
        print(f"[warn] Response ended with status={getattr(response, 'status', None)}. Not retrying.", file=sys.stderr)
    return response


def completed_output_text(response: Any) -> tuple[str | None, str | None]:
    status = getattr(response, "status", None)
    if status != "completed":
        return None, f"response_status={status or 'unknown'}"
    output_text = getattr(response, "output_text", None)
    if not isinstance(output_text, str) or not output_text.strip():
        return None, "completed_response_missing_output_text"
    return output_text, None


def build_run_meta(
    *,
    manifest: dict,
    args: argparse.Namespace,
    out_dir: Path,
    mode: str,
    response: Any,
    vector_store: Any,
    exact_input_tokens: int | None,
    report_path: Path | None,
    terminal_failure: bool,
    failure_reason: str | None = None,
) -> dict[str, Any]:
    run_meta = {
        "transport": "responses_api",
        "run_id": manifest.get("run_id"),
        "model": args.model,
        "reasoning_mode": args.reasoning_mode,
        "reasoning_effort": args.reasoning_effort,
        "reasoning_context": args.reasoning_context,
        "mode": mode,
        "response_id": getattr(response, "id", None),
        "status": getattr(response, "status", None),
        "previous_response_id": args.previous_response_id or None,
        "vector_store_id": getattr(vector_store, "id", None) if vector_store else None,
        "exact_input_tokens": exact_input_tokens,
        "direct_input_manifest": str(out_dir / "direct_input_files.json") if mode == "direct" else None,
        "report_path": str(report_path) if report_path else None,
        "response_json_path": str(out_dir / "response.json"),
        "terminal_failure": terminal_failure,
        "failure_reason": failure_reason,
    }
    if terminal_failure:
        run_meta["no_retry_performed"] = True
    return run_meta


def write_terminal_failure_artifacts(
    *,
    out_dir: Path,
    manifest: dict,
    args: argparse.Namespace,
    mode: str,
    response: Any,
    response_dict: Any,
    vector_store: Any = None,
    exact_input_tokens: int | None = None,
    failure_reason: str | None = None,
) -> dict[str, Any]:
    save_json(out_dir / "response.json", response_dict)
    report_path = out_dir / "analysis_report.md"
    if report_path.exists():
        report_path.unlink()
    run_meta = build_run_meta(
        manifest=manifest,
        args=args,
        out_dir=out_dir,
        mode=mode,
        response=response,
        vector_store=vector_store,
        exact_input_tokens=exact_input_tokens,
        report_path=None,
        terminal_failure=True,
        failure_reason=failure_reason,
    )
    save_json(out_dir / "run_meta.json", run_meta)
    return run_meta


def write_success_artifacts(
    *,
    out_dir: Path,
    manifest: dict,
    args: argparse.Namespace,
    mode: str,
    response: Any,
    response_dict: Any,
    output_text: str,
    vector_store: Any,
    exact_input_tokens: int | None,
) -> dict[str, Any]:
    save_json(out_dir / "response.json", response_dict)
    report_path = out_dir / "analysis_report.md"
    report_path.write_text(output_text, encoding="utf-8")
    run_meta = build_run_meta(
        manifest=manifest,
        args=args,
        out_dir=out_dir,
        mode=mode,
        response=response,
        vector_store=vector_store,
        exact_input_tokens=exact_input_tokens,
        report_path=report_path,
        terminal_failure=False,
    )
    save_json(out_dir / "run_meta.json", run_meta)
    return run_meta


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


def upload_user_data_files(client: Any, input_files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    uploaded = []
    for item in input_files:
        path = Path(item["path"])
        print(f"[info] Uploading direct input file: {item['logical_path']}", file=sys.stderr)
        with path.open("rb") as fh:
            file_obj = client.files.create(file=fh, purpose="user_data")
        uploaded.append({
            **item,
            "file_id": file_obj.id,
        })
    return uploaded


def upload_vector_store_files(client: Any, vector_store_name: str, root: Path, rel_paths: list[str]) -> tuple[Any, list[dict]]:
    vector_store = client.vector_stores.create(name=vector_store_name)
    uploaded_meta: list[dict] = []

    for rel_path in rel_paths:
        abs_path = root / rel_path
        if not abs_path.exists():
            print(f"[warn] Skipping missing file during vector-store upload: {rel_path}", file=sys.stderr)
            continue
        print(f"[info] Uploading file-search source: {rel_path}", file=sys.stderr)
        with abs_path.open("rb") as fh:
            file_obj = client.files.create(file=fh, purpose="assistants")
        client.vector_stores.files.create(vector_store_id=vector_store.id, file_id=file_obj.id)
        uploaded_meta.append({"path": rel_path, "file_id": file_obj.id})

    if not uploaded_meta:
        raise RuntimeError("No files were uploaded to the vector store.")

    # Poll every uploaded file explicitly so pagination cannot hide a failed or
    # still-ingesting item. Retrieval runs must never proceed with a partial store.
    while True:
        statuses: dict[str, str | None] = {}
        for item in uploaded_meta:
            vector_file = client.vector_stores.files.retrieve(
                vector_store_id=vector_store.id,
                file_id=item["file_id"],
            )
            statuses[item["path"]] = getattr(vector_file, "status", None)
        if not any(status in {"in_progress", "queued"} for status in statuses.values()):
            break
        print(f"[info] Waiting for vector-store ingestion: {statuses}", file=sys.stderr)
        sleep(3)

    failed = {path: status for path, status in statuses.items() if status != "completed"}
    if failed:
        sample = ", ".join(f"{path}={status}" for path, status in list(failed.items())[:20])
        raise RuntimeError(f"Vector-store ingestion was incomplete; refusing a partial analysis: {sample}")

    return vector_store, uploaded_meta


def estimate_exact_tokens(client: Any, model: str, instructions: str, input_files: list[dict[str, Any]], user_prompt: str) -> int | None:
    if not input_files:
        return None
    content_parts = []
    for item in input_files:
        path = Path(item["path"])
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:  # pragma: no cover - runtime variability
            print(f"[warn] Skipping token count for unreadable file {item['logical_path']}: {exc}", file=sys.stderr)
            continue
        content_parts.append({
            "type": "input_text",
            "text": "\n".join(
                [
                    f"===== BEGIN FILE: {item['logical_path']} =====",
                    text,
                    f"===== END FILE: {item['logical_path']} =====",
                ]
            ),
        })
    content_parts.append({"type": "input_text", "text": user_prompt})
    try:
        result = client.responses.input_tokens.count(
            model=model,
            instructions=instructions,
            input=[{"role": "user", "content": content_parts}],
        )
        return int(result.input_tokens)
    except Exception as exc:  # pragma: no cover - SDK/network variability
        print(f"[warn] Exact token counting failed, continuing without it: {exc}", file=sys.stderr)
        return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run repository analysis through the Responses API. This script does not drive ChatGPT Web and does not auto-fallback to another transport.")
    parser.add_argument("--manifest", required=True, help="Path to manifest.json produced by prepare_analysis_context.py")
    parser.add_argument("--goal", default="", help="Analysis goal.")
    parser.add_argument("--env-file", default=DEFAULTS["env_file"], help="Environment file to load before constructing the OpenAI client.")
    parser.add_argument(
        "--mode",
        choices=["auto", "direct", "file_search_full", "focused_file_search"],
        default="auto",
        help="Execution mode. 'auto' follows the manifest recommendation.",
    )
    parser.add_argument("--model", default=DEFAULTS["model"], help="OpenAI model id.")
    parser.add_argument("--reasoning-mode", choices=["standard", "pro"], default=DEFAULTS["reasoning_mode"])
    parser.add_argument(
        "--reasoning-effort",
        choices=["none", "low", "medium", "high", "xhigh", "max"],
        default=DEFAULTS["reasoning_effort"],
    )
    parser.add_argument(
        "--reasoning-context",
        choices=["auto", "current_turn", "all_turns"],
        default=DEFAULTS["reasoning_context"],
        help="Persisted reasoning policy. Use all_turns only when the prior response keeps the same goal and assumptions.",
    )
    parser.add_argument("--verbosity", choices=["low", "medium", "high"], default=DEFAULTS["verbosity"])
    parser.add_argument("--background", dest="background", action="store_true", default=DEFAULTS["background"])
    parser.add_argument("--no-background", dest="background", action="store_false")
    parser.add_argument("--store", dest="store", action="store_true", default=DEFAULTS["store"])
    parser.add_argument("--no-store", dest="store", action="store_false")
    parser.add_argument("--poll-interval-seconds", type=int, default=DEFAULTS["poll_interval_seconds"])
    parser.add_argument("--file-search-max-num-results", type=int, default=DEFAULTS["file_search_max_num_results"])
    parser.add_argument("--previous-response-id", default="", help="Optional previous response id for follow-up design work.")
    parser.add_argument("--vector-store-id", default="", help="Reuse an existing vector store instead of uploading again.")
    parser.add_argument("--out-dir", default=".codex-analysis/gpt-pro", help="Directory where reports and metadata are stored.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    env_file = Path(args.env_file).resolve()
    load_env_file(env_file)
    ensure_openai_api_key(env_file)

    manifest_path = Path(args.manifest).resolve()
    manifest = load_json(manifest_path)
    repo_root = Path(manifest["repo_root"]).resolve()
    requested_out_dir = Path(args.out_dir).resolve()
    out_dir = resolve_tool_output_dir(
        manifest_path=manifest_path,
        manifest=manifest,
        tool_name="gpt-pro",
        requested_out_dir=requested_out_dir,
        default_out_dir=Path(".codex-analysis/gpt-pro"),
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    goal = args.goal.strip() or manifest.get("goal", "")
    recommendation = manifest.get("mode_recommendation", "direct")
    warnings = list(manifest.get("warnings", []))

    mode = args.mode
    if mode == "auto":
        if recommendation == "direct_warn":
            mode = "direct"
        else:
            mode = recommendation

    OpenAI = require_openai()
    client = OpenAI()

    instructions = build_instructions()
    user_prompt = build_user_prompt(goal, recommendation, warnings, mode, manifest)
    try:
        reasoning = build_reasoning_config(args)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    exact_input_tokens = None
    response = None
    vector_store = None
    uploaded_meta: list[dict] = []

    if mode == "direct":
        try:
            direct_input_files = select_direct_input_files(
                manifest,
                repo_root,
                preferred_key="full",
                max_total_bytes=DEFAULTS["direct_input_max_bytes"],
                max_files=DEFAULTS["direct_input_max_files"],
            )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        if not direct_input_files:
            raise SystemExit("No direct input files were found in the manifest.")

        exact_input_tokens = estimate_exact_tokens(
            client,
            args.model,
            instructions,
            direct_input_files,
            user_prompt,
        )
        if exact_input_tokens is not None:
            token_report = {
                "exact_input_tokens": exact_input_tokens,
                "preferred_direct_threshold": manifest.get("config", {}).get("direct_token_threshold"),
                "long_context_threshold": manifest.get("config", {}).get("long_context_threshold"),
            }
            save_json(out_dir / "token_report.json", token_report)
            print(json.dumps(token_report, indent=2, ensure_ascii=False), file=sys.stderr)

        uploaded = upload_user_data_files(client, direct_input_files)
        save_json(
            out_dir / "direct_input_files.json",
            {
                "files": [
                    {
                        "logical_path": item["logical_path"],
                        "path": item["path"],
                        "size": item["size"],
                        "file_id": item["file_id"],
                    }
                    for item in uploaded
                ]
            },
        )
        content = [{"type": "input_file", "file_id": item["file_id"]} for item in uploaded]
        content.append({"type": "input_text", "text": user_prompt})

        request = {
            "model": args.model,
            "instructions": instructions,
            "input": [{"role": "user", "content": content}],
            "reasoning": reasoning,
            "text": {"verbosity": args.verbosity},
            "background": args.background,
            "store": args.store,
        }
        if args.previous_response_id:
            request["previous_response_id"] = args.previous_response_id
        response = client.responses.create(**request)

    elif mode in {"file_search_full", "focused_file_search"}:
        if args.vector_store_id:
            class ReusedVS:
                def __init__(self, vs_id: str) -> None:
                    self.id = vs_id
            vector_store = ReusedVS(args.vector_store_id)
        else:
            rel_paths = manifest["selections"]["full_files" if mode == "file_search_full" else "focused_files"]
            vector_store_name = f"gpt-pro-analysis-{repo_root.name}-{mode}"
            vector_store, uploaded_meta = upload_vector_store_files(client, vector_store_name, repo_root, rel_paths)
            save_json(out_dir / "vector_store_uploads.json", {"vector_store_id": vector_store.id, "files": uploaded_meta})

        repo_tree_path = Path(manifest["artifacts"]["repo_tree"])
        repo_tree = repo_tree_path.read_text(encoding="utf-8") if repo_tree_path.exists() else ""
        seed_summary = "\n".join(
            [
                "Repository map:",
                repo_tree[:20000],
                "",
                "Use file_search to retrieve the concrete files needed for the analysis.",
                "Prefer the repo map for orientation, not as your only evidence.",
            ]
        )

        request = {
            "model": args.model,
            "instructions": instructions,
            "input": [{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": seed_summary},
                    {"type": "input_text", "text": user_prompt},
                ],
            }],
            "tools": [{
                "type": "file_search",
                "vector_store_ids": [vector_store.id],
                "max_num_results": args.file_search_max_num_results,
            }],
            "include": ["file_search_call.results"],
            "reasoning": reasoning,
            "text": {"verbosity": args.verbosity},
            "background": args.background,
            "store": args.store,
        }
        if args.previous_response_id:
            request["previous_response_id"] = args.previous_response_id
        response = client.responses.create(**request)

    else:
        raise SystemExit(f"Unsupported mode: {mode}")

    if args.background:
        response = poll_response(client, response, args.poll_interval_seconds, args.reasoning_mode)

    response_dict = serialize_sdk_object(response)
    output_text, failure_reason = completed_output_text(response)
    if failure_reason:
        print(f"[warn] Response did not produce a completed report ({failure_reason}). Saving failure artifacts and exiting non-zero.", file=sys.stderr)
        run_meta = write_terminal_failure_artifacts(
            out_dir=out_dir,
            manifest=manifest,
            args=args,
            mode=mode,
            response=response,
            response_dict=response_dict,
            vector_store=vector_store,
            exact_input_tokens=exact_input_tokens,
            failure_reason=failure_reason,
        )
        print(json.dumps(run_meta, indent=2, ensure_ascii=False))
        return 1

    assert output_text is not None
    run_meta = write_success_artifacts(
        out_dir=out_dir,
        manifest=manifest,
        args=args,
        mode=mode,
        response=response,
        response_dict=response_dict,
        output_text=output_text,
        vector_store=vector_store,
        exact_input_tokens=exact_input_tokens,
    )

    print(json.dumps(run_meta, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
