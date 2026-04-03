#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
import textwrap
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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


def build_prompt(manifest: dict, goal: str, selection: Selection, notes: list[str], warnings: list[str]) -> str:
    scope = ", ".join(manifest.get("scope", [])) or "(none provided)"
    keywords = ", ".join(manifest.get("keywords", [])) or "(none)"
    warnings_block = "\n".join(f"- {item}" for item in warnings) if warnings else "- none"
    notes_block = "\n".join(f"- {item}" for item in notes) if notes else "- none"

    return textwrap.dedent(
        f"""
        Analyze the uploaded repository archive as the primary source of truth.

        Primary goal:
        {goal or manifest.get('goal') or '(none provided)'}

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
        - Separate confirmed findings from inference or uncertainty.
        - Do not use external web research unless I ask for it explicitly.
        - Use concise Markdown.
        - Do not reveal chain-of-thought.

        Required output sections unless I later ask for something else:
        1. Scope and assumptions
        2. Short system map
        3. Top findings (prioritized)
        4. Evidence for each finding
        5. Confirmed facts vs inference
        6. Test gaps
        7. Refactoring or redesign recommendations
        8. Quick wins vs deeper changes
        9. Suggested next design steps
        """
    ).strip() + "\n"


def build_next_steps(selection: Selection, upload_zip_path: Path, prompt_path: Path, response_template_path: Path, notes: list[str], warnings: list[str]) -> str:
    notes_block = "\n".join(f"- {item}" for item in notes) if notes else "- none"
    warnings_block = "\n".join(f"- {item}" for item in warnings) if warnings else "- none"
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

    return textwrap.dedent(
        f"""
        Manual ChatGPT Web handoff
        ==========================

        This path is fully manual. It does not open a browser, drive ChatGPT, scrape the page, or auto-submit anything.

        Files prepared for you:
        - Upload this file in ChatGPT: `{upload_zip_path}`
        - Paste this prompt into ChatGPT: `{prompt_path}`
        - After ChatGPT finishes, return its answer using this template: `{response_template_path}`

        Preparation notes:
        {notes_block}

        Local warnings:
        {warnings_block}

        Additional upload cautions:
        {size_note}{token_note or '- none\n'}

        What to do next:
        1. Open ChatGPT manually.
        2. Start a new chat.
        3. In the model picker, manually choose `Pro` if that is the user-approved model for this run.
        4. Upload `{upload_zip_path.name}`.
        5. Open `{prompt_path.name}`, copy all of its contents, and paste them as the message.
        6. Submit the message and let ChatGPT finish.
        7. Copy the full final answer.
        8. Open `{response_template_path.name}`, replace the placeholder area with the full answer, then return to Codex and paste the same content or attach that file.

        Important rules:
        - Do not switch to `responses_api` automatically if upload or analysis fails.
        - Do not narrow or broaden the scope automatically after failure.
        - If ChatGPT says it cannot inspect the archive reliably, bring that result back here first.
        - Any change of mode must be explicitly requested by the user.
        """
    ).strip() + "\n"


def build_return_template(selection: Selection, upload_zip_path: Path, prompt_path: Path) -> str:
    return textwrap.dedent(
        f"""
        [BEGIN CHATGPT WEB ANALYSIS]
        mode=chatgpt_web_assisted
        selected_archive={selection.label}
        uploaded_file={upload_zip_path.name}
        prompt_file={prompt_path.name}

        Paste the full ChatGPT response below this line.

        [END CHATGPT WEB ANALYSIS]
        """
    ).lstrip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare a fully manual ChatGPT Web handoff for repository analysis. This script does not use Playwright or browser automation."
    )
    parser.add_argument("--manifest", required=True, help="Path to manifest.json produced by prepare_analysis_context.py")
    parser.add_argument("--goal", default="", help="Analysis goal.")
    parser.add_argument(
        "--selection-mode",
        choices=["auto", "full", "focused"],
        default="auto",
        help="Which prepared code selection to package for manual ChatGPT Web upload. 'auto' keeps the full-first policy unless focused is recommended or the full archive is too large.",
    )
    parser.add_argument("--out-dir", default=DEFAULTS["out_dir"], help="Directory for the manual handoff artifacts.")
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
    out_dir = Path(args.out_dir).resolve()
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

    prompt_path = handoff_dir / "chatgpt-prompt.txt"
    prompt_text = build_prompt(manifest, goal, selection, notes, warnings)
    write_text(prompt_path, prompt_text)

    response_template_path = handoff_dir / "return-to-agent-template.md"
    write_text(response_template_path, build_return_template(selection, upload_zip_path, prompt_path))

    next_steps_path = handoff_dir / "next-steps.md"
    next_steps_text = build_next_steps(selection, upload_zip_path, prompt_path, response_template_path, notes, warnings)
    write_text(next_steps_path, next_steps_text)

    request_meta = {
        "transport": "chatgpt_web_assisted",
        "execution": "manual_only",
        "manifest": str(manifest_path),
        "selection_mode": args.selection_mode,
        "selection_label": selection.label,
        "selection_key": selection.key,
        "selection_generated_archive": selection.generated_archive,
        "upload_zip_path": str(upload_zip_path),
        "upload_zip_bytes": upload_zip_path.stat().st_size,
        "prompt_path": str(prompt_path),
        "response_template_path": str(response_template_path),
        "next_steps_path": str(next_steps_path),
        "estimated_selected_tokens": selection.estimated_tokens,
        "estimated_selected_bytes": selection.estimated_bytes,
        "selected_file_count": selection.file_count,
        "notes": notes,
        "warnings": warnings,
        "no_automatic_browser_automation": True,
        "no_automatic_mode_fallback": True,
    }
    save_json(out_dir / "request_meta.json", request_meta)
    save_json(out_dir / "run_meta.json", request_meta)

    print(json.dumps(request_meta, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
