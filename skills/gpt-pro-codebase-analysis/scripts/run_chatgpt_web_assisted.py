#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import textwrap
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from analysis_contract import render_required_output_sections
from analysis_run import resolve_tool_output_dir


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
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in rel_paths:
            abs_path = root / rel
            if not abs_path.exists() or not abs_path.is_file():
                continue
            zf.write(abs_path, arcname=rel)
    return output


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
            )
        archive_path = zip_selected_files(root, rel_paths, out_dir / f"generated-{key}-source.zip")
        generated_archive = True

    invalid_reasons: list[str] = []
    if archive_path.stat().st_size > max_file_bytes:
        invalid_reasons.append(
            f"The {label} file is {archive_path.stat().st_size:,} bytes, above ChatGPT's per-file upload cap of {max_file_bytes:,} bytes."
        )

    return Selection(
        key=key,
        label=label,
        archive_path=archive_path,
        generated_archive=generated_archive,
        file_count=len(rel_paths),
        estimated_bytes=estimated_bytes,
        estimated_tokens=estimated_tokens,
        invalid_reasons=invalid_reasons,
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
    keywords = ", ".join(manifest.get("keywords", [])) or "(none)"
    warnings_block = "\n".join(f"- {item}" for item in warnings) if warnings else "- none"
    notes_block = "\n".join(f"- {item}" for item in notes) if notes else "- none"
    resolved_goal = goal or manifest.get("goal") or "(none provided)"

    body = textwrap.dedent(
        f"""
        Preparation context:
        - selected archive: {selection.label}
        - repo root: {manifest.get('repo_root')}
        - explicit scope hints: {scope}
        - preparation mode: {manifest.get('preparation_mode')}
        - local recommendation: {manifest.get('mode_recommendation')}
        - selected file count: {selection.file_count}
        - selected estimated bytes: {selection.estimated_bytes:,}
        - selected estimated tokens: {selection.estimated_tokens:,}
        - extracted keywords: {keywords}

        Local preparation notes:
        {notes_block}

        Local warnings:
        {warnings_block}

        Instructions:
        - Follow the user's goal first.
        - If the goal is ambiguous, prioritize correctness, workflow/design validity, missing implementation, tests, refactoring, performance, then deprecated or unused logic.
        - Build a short system map first if the repo shape is unclear.
        - Trace at least one relevant end-to-end workflow.
        - Base claims on concrete evidence from the uploaded archive.
        - If the archive cannot be inspected reliably in this chat, say that clearly before making file-specific claims.
        - In the first output section, repeat the handoff identity values that are visible from this prompt so the caller can verify this answer belongs to the current handoff.
        - Separate confirmed findings from inference or uncertainty.
        - Do not use external web research unless I ask for it explicitly.
        - Use concise Markdown.
        - Do not reveal chain-of-thought.

        Required output sections unless I later ask for something else:
        """
    ).strip()
    return "\n\n".join(
        [
            "Analyze the uploaded repository archive as the primary source of truth.",
            handoff_identity.prompt_block(),
            f"Primary goal:\n{resolved_goal}",
            body,
            render_required_output_sections(),
        ]
    ) + "\n"


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
        {size_note}{token_note or '- none\n'}

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
    if selection.archive_path.resolve() != upload_zip_path.resolve():
        shutil.copy2(selection.archive_path, upload_zip_path)
    else:
        upload_zip_path = selection.archive_path
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
        "upload_zip_path": str(upload_zip_path),
        "upload_zip_bytes": upload_zip_path.stat().st_size,
        "upload_zip_sha256": upload_sha256,
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
