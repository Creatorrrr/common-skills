#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import textwrap
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from analysis_contract import render_finding_contract, render_required_output_sections  # noqa: E402
from analysis_run import resolve_tool_output_dir  # noqa: E402


DEFAULTS = {
    "chatgpt_max_file_bytes": 512 * 1024 * 1024,
    "chatgpt_warn_file_bytes": 400 * 1024 * 1024,
    "chatgpt_warn_tokens": 1_500_000,
    "chatgpt_hard_tokens": 2_000_000,
    "out_dir": ".codex-analysis/chatgpt-web",
}

RESPONSE_TEMPLATE = textwrap.dedent(
    """
    [BEGIN CHATGPT WEB ANALYSIS]
    Paste the full ChatGPT response here.
    [END CHATGPT WEB ANALYSIS]
    """
).lstrip()


@dataclass
class Selection:
    key: str
    label: str
    archive_path: Path
    generated_archive: bool
    file_count: int
    estimated_bytes: int
    estimated_tokens: int
    invalid_reasons: list[str]
    rel_paths: list[str] = field(default_factory=list)
    archive_member_count: int = 0
    archive_validation_status: str = "unknown"

    @property
    def size_bytes(self) -> int:
        return self.archive_path.stat().st_size if self.archive_path.exists() else 0

    @property
    def is_valid_for_chatgpt_upload(self) -> bool:
        return self.archive_path.exists() and not self.invalid_reasons


@dataclass(frozen=True)
class HandoffIdentity:
    run_id: str | None
    goal: str
    handoff_dir: Path
    upload_zip_path: Path
    upload_zip_sha256: str
    attachment_path: Path
    attachment_sha256: str
    computer_use_handoff: bool
    accessible_upload_copy_path: Path | None
    accessible_upload_copy_sha256: str | None
    prompt_path: Path
    request_meta_path: Path

    def prompt_block(self) -> str:
        lines = [
            "Handoff identity:",
            f"- run_id: {self.run_id or '(none)'}",
            f"- canonical upload archive filename: {self.upload_zip_path.name}",
            f"- canonical upload archive path: {self.upload_zip_path}",
            f"- ChatGPT attachment filename: {self.attachment_path.name}",
            f"- ChatGPT attachment path: {self.attachment_path}",
            f"- upload archive sha256: {self.upload_zip_sha256}",
            f"- ChatGPT attachment sha256: {self.attachment_sha256}",
        ]
        if self.accessible_upload_copy_path is not None:
            lines.extend(
                [
                    f"- Computer Use accessible upload copy path: {self.accessible_upload_copy_path}",
                    f"- Computer Use accessible upload copy sha256: {self.accessible_upload_copy_sha256}",
                ]
            )
        lines.extend(
            [
                f"- Computer Use handoff prepared: {str(self.computer_use_handoff).lower()}",
                f"- prompt path: {self.prompt_path}",
                f"- primary goal: {self.goal or '(none provided)'}",
            ]
        )
        return "\n".join(lines)

    def prompt_block_sha256(self) -> str:
        return sha256_text(self.prompt_block())

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "goal": self.goal,
            "handoff_dir": str(self.handoff_dir),
            "upload_zip_path": str(self.upload_zip_path),
            "upload_zip_name": self.upload_zip_path.name,
            "upload_zip_sha256": self.upload_zip_sha256,
            "attachment_path": str(self.attachment_path),
            "attachment_name": self.attachment_path.name,
            "attachment_sha256": self.attachment_sha256,
            "computer_use_handoff": self.computer_use_handoff,
            "accessible_upload_copy_path": str(self.accessible_upload_copy_path)
            if self.accessible_upload_copy_path is not None
            else None,
            "accessible_upload_copy_name": self.accessible_upload_copy_path.name
            if self.accessible_upload_copy_path is not None
            else None,
            "accessible_upload_copy_sha256": self.accessible_upload_copy_sha256,
            "prompt_path": str(self.prompt_path),
            "request_meta_path": str(self.request_meta_path),
            "prompt_handoff_identity_sha256": self.prompt_block_sha256(),
        }


def current_artifact_paths(
    *,
    out_dir: Path,
    handoff_dir: Path,
    upload_zip_path: Path,
    attachment_path: Path,
    accessible_upload_copy_path: Path | None,
    prompt_path: Path,
    response_template_path: Path,
    next_steps_path: Path,
    request_meta_path: Path,
) -> dict[str, Any]:
    return {
        "out_dir": str(out_dir),
        "handoff_dir": str(handoff_dir),
        "upload_zip_path": str(upload_zip_path),
        "attachment_path": str(attachment_path),
        "accessible_upload_copy_path": str(accessible_upload_copy_path) if accessible_upload_copy_path is not None else None,
        "prompt_path": str(prompt_path),
        "response_template_path": str(response_template_path),
        "next_steps_path": str(next_steps_path),
        "request_meta_path": str(request_meta_path),
        "run_meta_path": str(out_dir / "run_meta.json"),
    }


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, default=str)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_filename_part(value: str | None) -> str:
    text = (value or "unknown-run").strip() or "unknown-run"
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in text)
    return safe.strip(".-") or "unknown-run"


def default_accessible_copy_dir() -> Path:
    home = Path.home()
    for candidate in (home / "Downloads", home / "Desktop"):
        if candidate.exists() and candidate.is_dir():
            return candidate
    return home


def create_accessible_upload_copy(source: Path, run_id: str | None, copy_dir: Path) -> Path:
    copy_dir.mkdir(parents=True, exist_ok=True)
    target = copy_dir / f"upload-source-{safe_filename_part(run_id)}.zip"
    if source.resolve() != target.resolve():
        shutil.copy2(source, target)
    return target


def zip_selected_files(root: Path, rel_paths: list[str], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    missing = [rel for rel in rel_paths if not (root / rel).exists() or not (root / rel).is_file()]
    if missing:
        raise ValueError(f"Missing selected files for archive regeneration: {', '.join(missing[:20])}")
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in rel_paths:
            abs_path = root / rel
            zf.write(abs_path, arcname=rel)
    return output


def zip_member_names(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as zf:
        return sorted(name for name in zf.namelist() if not name.endswith("/"))


def validate_selected_members(archive_path: Path, rel_paths: list[str]) -> tuple[str, int, list[str]]:
    if not archive_path.exists():
        return "missing_archive", 0, rel_paths
    names = zip_member_names(archive_path)
    missing = sorted(set(rel_paths) - set(names))
    status = "ok" if not missing else "missing_selected_files"
    return status, len(names), missing


def context_artifacts_for_upload(manifest: dict) -> list[tuple[Path, str]]:
    artifacts = manifest.get("artifacts", {})
    candidates = [
        (artifacts.get("selection_manifest"), "__analysis_context__/selection-manifest.json"),
        (artifacts.get("selection_report"), "__analysis_context__/selection-report.md"),
        (artifacts.get("repo_tree"), "__analysis_context__/repo_tree.txt"),
    ]
    result: list[tuple[Path, str]] = []
    for path_value, arcname in candidates:
        if path_value and Path(path_value).exists():
            result.append((Path(path_value), arcname))
    return result


def create_minimal_selection_manifest(manifest: dict, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "repo_root": manifest.get("repo_root"),
        "goal": manifest.get("goal"),
        "scope": manifest.get("scope", []),
        "stats": manifest.get("stats", {}),
        "selections": manifest.get("selections", {}),
        "selection_report": manifest.get("selection_report", {}),
    }
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def create_minimal_selection_report(manifest: dict, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    stats = manifest.get("stats", {})
    report = manifest.get("selection_report", {})
    lines = [
        "# Analysis Context Selection Report",
        "",
        f"- Policy decision: {report.get('policy_decision_reason', '(not recorded in manifest)')}",
        f"- Included files: {stats.get('included_file_count', '(unknown)')}",
        f"- Skipped files: {stats.get('skipped_file_count', '(unknown)')}",
    ]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def ensure_context_artifacts(manifest: dict, handoff_dir: Path) -> list[tuple[Path, str]]:
    artifacts = context_artifacts_for_upload(manifest)
    arcnames = {arcname for _, arcname in artifacts}
    if "__analysis_context__/selection-manifest.json" not in arcnames:
        artifacts.append(
            (
                create_minimal_selection_manifest(manifest, handoff_dir / "selection-manifest.json"),
                "__analysis_context__/selection-manifest.json",
            )
        )
    if "__analysis_context__/selection-report.md" not in arcnames:
        artifacts.append(
            (
                create_minimal_selection_report(manifest, handoff_dir / "selection-report.md"),
                "__analysis_context__/selection-report.md",
            )
        )
    if "__analysis_context__/repo_tree.txt" not in arcnames and manifest.get("artifacts", {}).get("repo_tree"):
        repo_tree = Path(manifest["artifacts"]["repo_tree"])
        if repo_tree.exists():
            artifacts.append((repo_tree, "__analysis_context__/repo_tree.txt"))
    return artifacts


def copy_archive_with_context(source: Path, output: Path, context_artifacts: list[tuple[Path, str]]) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    target = output
    temp_output = output.with_suffix(output.suffix + ".tmp") if source.resolve() == output.resolve() else output
    with zipfile.ZipFile(source, mode="r") as source_zip, zipfile.ZipFile(temp_output, mode="w", compression=zipfile.ZIP_DEFLATED) as target_zip:
        existing: set[str] = set()
        for info in source_zip.infolist():
            if info.is_dir():
                continue
            existing.add(info.filename)
            target_zip.writestr(info, source_zip.read(info.filename))
        for path, arcname in context_artifacts:
            if arcname in existing:
                continue
            target_zip.write(path, arcname=arcname)
            existing.add(arcname)
    if temp_output != output:
        shutil.move(temp_output, target)
    return target


def build_selection(manifest: dict, root: Path, out_dir: Path, key: str, max_file_bytes: int) -> Selection:
    artifacts = manifest.get("artifacts", {})
    stats = manifest.get("stats", {})
    selections = manifest.get("selections", {})

    if key == "full":
        label = "full_archive"
        archive_value = artifacts.get("full_archive")
        rel_paths = list(selections.get("full_files") or [])
        estimated_bytes = int(stats.get("included_bytes") or 0)
        estimated_tokens = int(stats.get("included_estimated_tokens") or 0)
    elif key == "focused":
        label = "focused_archive"
        archive_value = artifacts.get("focused_archive")
        rel_paths = list(selections.get("focused_files") or [])
        estimated_bytes = int(stats.get("focused_bytes") or 0)
        estimated_tokens = int(stats.get("focused_estimated_tokens") or 0)
    else:  # pragma: no cover - parser prevents this
        raise ValueError(f"Unsupported selection key: {key}")

    archive_path = Path(archive_value).resolve() if archive_value else out_dir / f"generated-{key}-source.zip"
    generated_archive = False

    if not archive_path.exists():
        if not rel_paths:
            return Selection(
                key=key,
                label=label,
                archive_path=archive_path,
                generated_archive=False,
                file_count=0,
                estimated_bytes=estimated_bytes,
                estimated_tokens=estimated_tokens,
                invalid_reasons=[f"No {key} file selection exists in the manifest."],
                rel_paths=rel_paths,
            )
        missing = [rel for rel in rel_paths if not (root / rel).exists() or not (root / rel).is_file()]
        if missing:
            return Selection(
                key=key,
                label=label,
                archive_path=archive_path,
                generated_archive=False,
                file_count=len(rel_paths),
                estimated_bytes=estimated_bytes,
                estimated_tokens=estimated_tokens,
                invalid_reasons=[f"Missing selected files for archive regeneration: {', '.join(missing[:20])}"],
                rel_paths=rel_paths,
            )
        archive_path = zip_selected_files(root, rel_paths, out_dir / f"generated-{key}-source.zip")
        generated_archive = True

    invalid_reasons: list[str] = []
    if archive_path.stat().st_size > max_file_bytes:
        invalid_reasons.append(
            f"The {label} file is {archive_path.stat().st_size:,} bytes, above ChatGPT's per-file upload cap of {max_file_bytes:,} bytes."
        )
    archive_validation_status, archive_member_count, missing_members = validate_selected_members(archive_path, rel_paths)
    if missing_members:
        invalid_reasons.append(f"Archive is missing selected files: {', '.join(missing_members[:20])}")

    return Selection(
        key=key,
        label=label,
        archive_path=archive_path,
        generated_archive=generated_archive,
        file_count=len(rel_paths),
        estimated_bytes=estimated_bytes,
        estimated_tokens=estimated_tokens,
        invalid_reasons=invalid_reasons,
        rel_paths=rel_paths,
        archive_member_count=archive_member_count,
        archive_validation_status=archive_validation_status,
    )


def choose_selection(manifest: dict, root: Path, out_dir: Path, selection_mode: str, max_file_bytes: int) -> tuple[Selection, list[str]]:
    full = build_selection(manifest, root, out_dir, "full", max_file_bytes)
    focused = build_selection(manifest, root, out_dir, "focused", max_file_bytes)
    recommendation = str(manifest.get("mode_recommendation") or "")
    notes: list[str] = []

    if selection_mode == "full":
        if not full.is_valid_for_chatgpt_upload:
            reasons = " ".join(full.invalid_reasons) or "The full archive is unavailable."
            raise SystemExit(
                f"Full selection was explicitly requested, but it is not usable for ChatGPT Web upload. {reasons} Narrow the scope or choose responses_api explicitly."
            )
        return full, notes

    if selection_mode == "focused":
        if not focused.is_valid_for_chatgpt_upload:
            reasons = " ".join(focused.invalid_reasons) or "The focused archive is unavailable."
            raise SystemExit(
                f"Focused selection was explicitly requested, but it is not usable for ChatGPT Web upload. {reasons} Narrow the scope or choose responses_api explicitly."
            )
        return focused, notes

    # auto: keep full-first behavior unless the local preparation step strongly points to focused,
    # or the full archive is not uploadable within ChatGPT's file limit.
    if recommendation == "focused_file_search" and focused.is_valid_for_chatgpt_upload:
        notes.append("Auto selection chose the focused archive because the local preparation step recommended focused analysis.")
        return focused, notes

    if full.is_valid_for_chatgpt_upload:
        notes.append("Full archive selected because it is uploadable and minimizes omitted-file risk.")
        return full, notes

    if focused.is_valid_for_chatgpt_upload:
        notes.append("Auto selection fell back from full archive to focused archive because the full archive was not uploadable as a single ChatGPT file.")
        return focused, notes

    raise SystemExit(
        "Neither the full nor the focused archive is usable for ChatGPT Web upload. "
        f"Full issues: {' '.join(full.invalid_reasons) or 'unavailable'}. "
        f"Focused issues: {' '.join(focused.invalid_reasons) or 'unavailable'}. "
        "Narrow the scope or explicitly choose responses_api."
    )


def build_prompt(
    manifest: dict,
    goal: str,
    selection: Selection,
    notes: list[str],
    warnings: list[str],
    *,
    handoff_identity: HandoffIdentity,
) -> str:
    scope = ", ".join(manifest.get("scope", [])) or "(none provided)"
    warnings_block = "\n".join(f"- {item}" for item in warnings) if warnings else "- none"
    notes_block = "\n".join(f"- {item}" for item in notes) if notes else "- none"
    resolved_goal = goal or manifest.get("goal") or "(none provided)"
    if handoff_identity.goal != resolved_goal:
        raise ValueError("Handoff identity goal does not match the prompt goal.")
    finding_fields = render_finding_contract()
    sections = render_required_output_sections()

    return "\n".join(
        [
            "Act as a senior repository auditor. Analyze the uploaded repository archive as the only source of truth.",
            "",
            handoff_identity.prompt_block(),
            "",
            "Prepared context:",
            f"- selected archive: {selection.label}",
            f"- explicit scope: {scope}",
            f"- local recommendation: {manifest.get('mode_recommendation')}",
            f"- selected file count: {selection.file_count}",
            f"- selected estimated tokens: {selection.estimated_tokens:,}",
            "- audit files: __analysis_context__/selection-manifest.json, selection-report.md, and repo_tree.txt when present",
            "",
            "Local preparation notes:",
            notes_block,
            "",
            "Local warnings:",
            warnings_block,
            "",
            "Evidence contract:",
            "- Base every material claim on concrete files from the archive.",
            "- Do not make repository-wide claims unless inspected coverage supports them.",
            f"- Each finding must contain: {finding_fields}.",
            "- Cite path:line only when stable line information exists; otherwise cite path and symbol or section. Never invent line numbers.",
            "- A missing, dead, duplicate, deprecated, or unused claim must check definitions, callers or wiring, configuration, and relevant tests. Otherwise label it unconfirmed.",
            "- Put unsupported questions under Unknowns and missing context instead of guessing.",
            "- If the archive cannot be inspected reliably, say so before making file-specific claims.",
            "- Do not use external web research unless explicitly requested.",
            "",
            "Method:",
            "1. Map only the goal-relevant modules and runtime boundaries.",
            "2. Trace one to three concrete end-to-end workflows.",
            "3. Rank consequential findings and check each against callers, tests, and configuration.",
            "4. State which relevant areas were not inspected.",
            "",
            "In Verdict, repeat the visible handoff identity values so the caller can verify this answer belongs to the current handoff.",
            "",
            "Required output sections unless I later request another format:",
            sections,
            "",
        ]
    )


def build_next_steps(
    selection: Selection,
    upload_zip_path: Path,
    attachment_path: Path,
    prompt_path: Path,
    response_template_path: Path,
    notes: list[str],
    warnings: list[str],
    *,
    request_meta_path: Path | None = None,
    handoff_identity: HandoffIdentity | None = None,
    accessible_upload_copy_path: Path | None = None,
) -> str:
    notes_block = "\n".join(f"- {item}" for item in notes) if notes else "- none"
    warnings_block = "\n".join(f"- {item}" for item in warnings) if warnings else "- none"
    request_meta_line = f"- Handoff metadata: `{request_meta_path}`" if request_meta_path else ""
    identity_sha_line = (
        f"- Prompt handoff identity SHA-256: `{handoff_identity.prompt_block_sha256()}`"
        if handoff_identity
        else ""
    )
    token_note = ""
    if selection.estimated_tokens >= DEFAULTS["chatgpt_hard_tokens"]:
        token_note = (
            f"- The selected source set is estimated at {selection.estimated_tokens:,} tokens. "
            "That is at or above the 2,000,000-token cap documented for text/document files, so archive analysis quality or acceptance may be poor. "
            "If ChatGPT cannot handle it, return here and explicitly choose responses_api or a narrower focused scope.\n"
        )
    elif selection.estimated_tokens >= DEFAULTS["chatgpt_warn_tokens"]:
        token_note = (
            f"- The selected source set is estimated at {selection.estimated_tokens:,} tokens. "
            "This is large for ChatGPT Web analysis and may lead to weaker coverage or slower processing.\n"
        )
    size_note = ""
    if selection.size_bytes >= DEFAULTS["chatgpt_warn_file_bytes"]:
        size_note = (
            f"- The upload zip is {selection.size_bytes:,} bytes, close to the 512MB per-file upload cap. "
            "Uploads may be slow or fail depending on the environment.\n"
        )
    upload_cautions = size_note + (token_note or "- none\n")
    accessible_copy_line = (
        f"- Computer Use accessible copy: `{accessible_upload_copy_path}`"
        if accessible_upload_copy_path is not None
        else "- Computer Use accessible copy: not created; manual handoff uses the canonical archive in place"
    )

    return textwrap.dedent(
        f"""
        ChatGPT Web handoff package
        ===========================

        This helper only prepares the handoff files. It does not open a browser, drive ChatGPT, scrape the page, or auto-submit anything.

        Files prepared for you:
        - Attach this file in ChatGPT: `{attachment_path}`
        - Canonical handoff archive: `{upload_zip_path}`
        {accessible_copy_line}
        - Paste this prompt into ChatGPT: `{prompt_path}`
        - After ChatGPT finishes, return its answer using this template: `{response_template_path}`
        {request_meta_line}
        {identity_sha_line}

        Preparation notes:
        {notes_block}

        Local warnings:
        {warnings_block}

        Additional upload cautions:
        {upload_cautions}

        What to do next:
        1. Open ChatGPT manually.
        2. Start a new chat.
        3. In the model picker, manually choose `Pro` with `Extended(확장)` reasoning unless the user explicitly requested another reasoning level.
        4. Use ChatGPT's attach-file button and select `{attachment_path.name}` from `{attachment_path.parent}`.
        5. Open `{prompt_path.name}`, copy all of its contents, and paste them as the message.
        6. Submit the message and let ChatGPT finish. Pro Extended analysis can take more than 30 minutes.
        7. Copy the full final answer.
        8. Open `{response_template_path.name}`, replace the placeholder area with the full answer, then return to Codex and paste the same content or attach that file.

        Important rules:
        - Do not switch to `responses_api` automatically if upload or analysis fails.
        - Do not narrow or broaden the scope automatically after failure.
        - If ChatGPT says it cannot inspect the archive reliably, bring that result back here first.
        - Any change of mode must be explicitly requested by the user.
        - If ChatGPT displays the uploaded archive with a renamed filename, verify the answer using the handoff identity block in `{prompt_path.name}` rather than the displayed filename alone.
        - Before importing a completed answer, compare the answer's first section against `request_meta.json` values for `run_id`, `goal`, upload SHA, attached filename, and `prompt_handoff_identity_sha256`.
        """
    ).strip() + "\n"


def build_return_template(
    selection: Selection,
    upload_zip_path: Path,
    attachment_path: Path,
    prompt_path: Path,
    *,
    handoff_identity: HandoffIdentity,
    goal: str,
) -> str:
    return textwrap.dedent(
        f"""
        [BEGIN CHATGPT WEB ANALYSIS]
        mode=chatgpt_web_assisted
        run_id={handoff_identity.run_id or ''}
        selected_archive={selection.label}
        canonical_uploaded_file={upload_zip_path.name}
        attached_file={attachment_path.name}
        upload_sha256={handoff_identity.upload_zip_sha256}
        prompt_handoff_identity_sha256={handoff_identity.prompt_block_sha256()}
        prompt_file={prompt_path.name}
        goal={goal}
        verified_current_session=
        verification_evidence=
        matched_run_id=
        matched_goal=
        matched_prompt_identity_sha256=
        matched_upload_sha_or_reason_unavailable=
        matched_attached_file_or_reason_unavailable=

        Paste the full ChatGPT response below this line.

        [END CHATGPT WEB ANALYSIS]
        """
    ).lstrip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare a ChatGPT Web handoff package for repository analysis. This script does not use Playwright or browser automation."
    )
    parser.add_argument("--manifest", required=True, help="Path to manifest.json produced by prepare_analysis_context.py")
    parser.add_argument("--goal", default="", help="Analysis goal.")
    parser.add_argument(
        "--selection-mode",
        choices=["auto", "full", "focused"],
        default="auto",
        help="Which prepared code selection to package for ChatGPT Web upload. 'auto' keeps the full-first policy unless focused is recommended or the full archive is too large.",
    )
    parser.add_argument("--out-dir", default=DEFAULTS["out_dir"], help="Directory for the manual handoff artifacts.")
    parser.add_argument(
        "--accessible-copy-dir",
        default="",
        help="Directory for the run_id-named Computer Use upload copy. Only used with --computer-use-handoff. Defaults to ~/Downloads, then ~/Desktop, then the home directory.",
    )
    parser.add_argument(
        "--computer-use-handoff",
        action="store_true",
        help="Create a run_id-named upload copy for a Computer Use ChatGPT Web handoff. Without this flag, the canonical handoff archive is used in place.",
    )
    parser.add_argument(
        "--max-chatgpt-file-bytes",
        type=int,
        default=DEFAULTS["chatgpt_max_file_bytes"],
        help="Per-file ChatGPT upload cap used for validation.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    manifest = load_json(manifest_path)
    root = Path(manifest["repo_root"]).resolve()
    requested_out_dir = Path(args.out_dir).resolve()
    out_dir = resolve_tool_output_dir(
        manifest_path=manifest_path,
        manifest=manifest,
        tool_name="chatgpt-web",
        requested_out_dir=requested_out_dir,
        default_out_dir=Path(DEFAULTS["out_dir"]),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    handoff_dir = out_dir / "handoff"
    handoff_dir.mkdir(parents=True, exist_ok=True)

    goal = args.goal.strip() or manifest.get("goal", "")
    warnings = list(manifest.get("warnings", []))

    selection, notes = choose_selection(
        manifest=manifest,
        root=root,
        out_dir=handoff_dir,
        selection_mode=args.selection_mode,
        max_file_bytes=args.max_chatgpt_file_bytes,
    )

    upload_zip_path = handoff_dir / "upload-source.zip"
    context_artifacts = ensure_context_artifacts(manifest, handoff_dir)
    upload_zip_path = copy_archive_with_context(selection.archive_path, upload_zip_path, context_artifacts)
    upload_members = zip_member_names(upload_zip_path)
    missing_upload_members = sorted(set(selection.rel_paths) - set(upload_members))
    if missing_upload_members:
        raise SystemExit(f"Upload archive is missing selected files: {', '.join(missing_upload_members[:20])}")
    upload_sha256 = sha256_file(upload_zip_path)
    accessible_upload_copy_path: Path | None = None
    accessible_upload_sha256: str | None = None
    attachment_path = upload_zip_path
    attachment_sha256 = upload_sha256
    if args.computer_use_handoff:
        accessible_copy_dir = Path(args.accessible_copy_dir).expanduser().resolve() if args.accessible_copy_dir else default_accessible_copy_dir()
        accessible_upload_copy_path = create_accessible_upload_copy(
            source=upload_zip_path,
            run_id=manifest.get("run_id"),
            copy_dir=accessible_copy_dir,
        )
        accessible_upload_sha256 = sha256_file(accessible_upload_copy_path)
        if accessible_upload_sha256 != upload_sha256:
            raise SystemExit(
                "The accessible ChatGPT upload copy does not match the canonical handoff archive SHA-256. "
                f"canonical={upload_sha256} accessible_copy={accessible_upload_sha256}"
            )
        attachment_path = accessible_upload_copy_path
        attachment_sha256 = accessible_upload_sha256
    elif args.accessible_copy_dir:
        notes.append("--accessible-copy-dir was ignored because --computer-use-handoff was not set; manual handoff uses the canonical archive in place.")

    prompt_path = handoff_dir / "chatgpt-prompt.txt"
    response_template_path = handoff_dir / "return-to-agent-template.md"
    next_steps_path = handoff_dir / "next-steps.md"
    request_meta_path = out_dir / "request_meta.json"
    handoff_identity = HandoffIdentity(
        run_id=manifest.get("run_id"),
        goal=goal,
        handoff_dir=handoff_dir,
        upload_zip_path=upload_zip_path,
        upload_zip_sha256=upload_sha256,
        attachment_path=attachment_path,
        attachment_sha256=attachment_sha256,
        computer_use_handoff=args.computer_use_handoff,
        accessible_upload_copy_path=accessible_upload_copy_path,
        accessible_upload_copy_sha256=accessible_upload_sha256,
        prompt_path=prompt_path,
        request_meta_path=request_meta_path,
    )
    prompt_text = build_prompt(
        manifest,
        goal,
        selection,
        notes,
        warnings,
        handoff_identity=handoff_identity,
    )
    write_text(prompt_path, prompt_text)

    write_text(
        response_template_path,
        build_return_template(
            selection,
            upload_zip_path,
            attachment_path,
            prompt_path,
            handoff_identity=handoff_identity,
            goal=goal,
        ),
    )

    next_steps_text = build_next_steps(
        selection,
        upload_zip_path,
        attachment_path,
        prompt_path,
        response_template_path,
        notes,
        warnings,
        request_meta_path=request_meta_path,
        handoff_identity=handoff_identity,
        accessible_upload_copy_path=accessible_upload_copy_path,
    )
    write_text(next_steps_path, next_steps_text)

    prepared_handoff_identity = handoff_identity.to_dict()
    prompt_handoff_identity_block = handoff_identity.prompt_block()
    prompt_handoff_identity_sha256 = handoff_identity.prompt_block_sha256()
    artifact_paths = current_artifact_paths(
        out_dir=out_dir,
        handoff_dir=handoff_dir,
        upload_zip_path=upload_zip_path,
        attachment_path=attachment_path,
        accessible_upload_copy_path=accessible_upload_copy_path,
        prompt_path=prompt_path,
        response_template_path=response_template_path,
        next_steps_path=next_steps_path,
        request_meta_path=request_meta_path,
    )

    request_meta = {
        "transport": "chatgpt_web_assisted",
        "execution": "handoff_package_only",
        "handoff_lifecycle": "prepared",
        "manifest": str(manifest_path),
        "run_id": manifest.get("run_id"),
        "goal": goal,
        "handoff_dir": str(handoff_dir),
        "selection_mode": args.selection_mode,
        "selection_label": selection.label,
        "selection_key": selection.key,
        "selection_generated_archive": selection.generated_archive,
        "selection_source_archive_member_count": selection.archive_member_count,
        "selection_source_archive_validation_status": selection.archive_validation_status,
        "upload_zip_path": str(upload_zip_path),
        "upload_zip_bytes": upload_zip_path.stat().st_size,
        "upload_zip_sha256": upload_sha256,
        "archive_validation_status": "ok",
        "archive_selected_file_count": len(selection.rel_paths),
        "archive_member_count": len(upload_members),
        "archive_context_member_count": len([name for name in upload_members if name.startswith("__analysis_context__/")]),
        "archive_missing_selected_files": missing_upload_members,
        "attachment_path": str(attachment_path),
        "attachment_name": attachment_path.name,
        "attachment_bytes": attachment_path.stat().st_size,
        "attachment_sha256": attachment_sha256,
        "attachment_source": "computer_use_accessible_copy" if args.computer_use_handoff else "canonical_handoff_archive",
        "computer_use_handoff_requested": args.computer_use_handoff,
        "accessible_upload_copy_path": str(accessible_upload_copy_path) if accessible_upload_copy_path is not None else None,
        "accessible_upload_copy_name": accessible_upload_copy_path.name if accessible_upload_copy_path is not None else None,
        "accessible_upload_copy_bytes": accessible_upload_copy_path.stat().st_size if accessible_upload_copy_path is not None else None,
        "accessible_upload_copy_sha256": accessible_upload_sha256,
        "prompt_path": str(prompt_path),
        "response_template_path": str(response_template_path),
        "next_steps_path": str(next_steps_path),
        "handoff_identity": prepared_handoff_identity,
        "prepared_handoff_identity": prepared_handoff_identity,
        "prompt_handoff_identity_block": prompt_handoff_identity_block,
        "prompt_handoff_identity_sha256": prompt_handoff_identity_sha256,
        "current_artifact_paths": artifact_paths,
        "estimated_selected_tokens": selection.estimated_tokens,
        "estimated_selected_bytes": selection.estimated_bytes,
        "selected_file_count": selection.file_count,
        "notes": notes,
        "warnings": warnings,
        "helper_does_not_perform_browser_automation": True,
        "browser_automation_performed_by_helper": False,
        "computer_use_handoff_prepared": args.computer_use_handoff,
        "computer_use_handoff_possible_when_user_explicitly_requested": True,
        "browser_automation_allowed_only_by_explicit_computer_use": True,
        "no_automatic_mode_fallback": True,
    }
    save_json(request_meta_path, request_meta)
    save_json(out_dir / "run_meta.json", request_meta)

    print(json.dumps(request_meta, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
