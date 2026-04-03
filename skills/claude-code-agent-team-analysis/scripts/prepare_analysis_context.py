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
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from analysis_run import prepare_run_layout

DEFAULT_CONFIG = {
    "direct_token_threshold": 180000,
    "long_context_threshold": 272000,
    "direct_hard_token_threshold": 900000,
    "direct_total_bytes_warn": 25_000_000,
    "direct_total_bytes_hard": 50_000_000,
    "full_retrieval_file_count_threshold": 2000,
    "full_retrieval_total_bytes_threshold": 200_000_000,
    "focused_token_budget": 180000,
    "focused_context_shard_chars": 350000,
    "max_inline_file_bytes": 400000,
    "include_docs": True,
    "include_tests": True,
    "include_lockfiles": False,
    "skip_archives": False,
    "archive_warn_bytes": 500_000_000,
    "archive_hard_bytes": 1_500_000_000,
}

TEXT_EXTENSIONS = {
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".java", ".kt", ".kts",
    ".go", ".rs", ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hh", ".cs", ".rb", ".php",
    ".swift", ".scala", ".sql", ".sh", ".bash", ".zsh", ".fish", ".ps1", ".yaml", ".yml",
    ".toml", ".json", ".jsonc", ".json5", ".md", ".mdx", ".rst", ".txt", ".csv", ".tsv",
    ".ini", ".cfg", ".conf", ".env", ".example", ".sample", ".properties", ".proto", ".graphql",
    ".gql", ".html", ".css", ".scss", ".sass", ".less", ".vue", ".svelte", ".xml", ".xsd",
    ".lock", ".gradle", ".tf", ".tfvars", ".hcl", ".dockerignore", ".gitignore", ".editorconfig",
}

ROOT_HIGH_SIGNAL_BASENAMES = {
    "README.md", "README.mdx", "AGENTS.md", "PLANS.md", "ARCHITECTURE.md", "CONTRIBUTING.md",
    "Makefile", "Dockerfile", "docker-compose.yml", "docker-compose.yaml", "package.json",
    "pnpm-workspace.yaml", "turbo.json", "nx.json", "tsconfig.json", "vite.config.ts", "vite.config.js",
    "next.config.js", "next.config.mjs", "pyproject.toml", "requirements.txt", "Cargo.toml",
    "Cargo.lock", "go.mod", "go.sum", "pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle",
    "settings.gradle.kts", "composer.json", "Gemfile", "Procfile",
}

LOCKFILES = {
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb", "poetry.lock", "Pipfile.lock",
    "Cargo.lock", "composer.lock", "Gemfile.lock", "go.sum",
}

LOW_SIGNAL_DIR_PARTS = {
    ".git", ".hg", ".svn", "node_modules", "vendor", "dist", "build", "coverage", ".next",
    ".nuxt", ".svelte-kit", ".turbo", ".cache", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "target", "out", "bin", "obj", "__pycache__", ".idea", ".vscode", ".parcel-cache", ".codex-analysis",
}

LOW_SIGNAL_FILE_REGEXES = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"(^|/)coverage[^/]*$",
        r"(^|/)npm-debug\.log$",
        r"\.min\.(js|css)$",
        r"\.snap$",
        r"(^|/)(storybook-static|site|public/build)(/|$)",
        r"(^|/)(fixtures?|__snapshots__|snapshots)(/|$)",
        r"(^|/)(generated|gen|autogen|auto-generated)(/|$)",
        r"(^|/)CHANGELOG\.md$",
    ]
]

MARKER_REGEX = re.compile(r"\b(TODO|FIXME|HACK|XXX|BUG|DEPRECATED|OBSOLETE|UNUSED|LEGACY|WIP|TBD)\b", re.IGNORECASE)
WORD_REGEX = re.compile(r"[A-Za-z0-9_\-]{3,}")
LANGUAGE_BY_EXTENSION = {
    ".py": "python", ".pyi": "python", ".js": "javascript", ".jsx": "jsx", ".ts": "typescript",
    ".tsx": "tsx", ".java": "java", ".kt": "kotlin", ".go": "go", ".rs": "rust", ".c": "c",
    ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp", ".h": "c", ".hpp": "cpp", ".cs": "csharp",
    ".rb": "ruby", ".php": "php", ".swift": "swift", ".scala": "scala", ".sql": "sql",
    ".sh": "bash", ".bash": "bash", ".zsh": "bash", ".ps1": "powershell", ".yaml": "yaml",
    ".yml": "yaml", ".toml": "toml", ".json": "json", ".md": "markdown", ".mdx": "mdx",
    ".rst": "rst", ".html": "html", ".css": "css", ".scss": "scss", ".less": "less",
    ".vue": "vue", ".svelte": "svelte", ".xml": "xml", ".proto": "proto", ".graphql": "graphql",
}

STOPWORDS = {
    "the", "and", "for", "with", "from", "into", "that", "this", "those", "these", "use", "using",
    "code", "repo", "repository", "project", "analysis", "design", "review", "refactor", "refactoring",
    "workflow", "usecase", "use", "case", "test", "tests", "performance", "improve", "improvement",
    "module", "system", "service", "files", "overall", "structure", "architectural", "inspection",
    "validation", "strengthening", "content", "audit", "investigation", "cleanup", "missing",
    "unimplemented", "deprecated",
}


@dataclass
class FileRecord:
    path: str
    size: int
    category: str
    language: str | None
    status: str
    reasons: list[str] = field(default_factory=list)
    markers: list[str] = field(default_factory=list)
    score: float = 0.0
    inline_truncated: bool = False
    bytes_inlined: int = 0


@dataclass
class PreparedArtifacts:
    manifest_path: str
    repo_tree_path: str
    full_archive_path: str | None
    focused_archive_path: str | None
    full_context_shards: list[str]
    focused_context_shards: list[str]


def debug(msg: str) -> None:
    print(msg, file=sys.stderr)


def load_config(path: Path | None) -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if path is None:
        return cfg
    with path.open("r", encoding="utf-8") as fh:
        user_cfg = json.load(fh)
    cfg.update(user_cfg)
    return cfg


def run_git(args: Sequence[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def find_repo_root(start: Path) -> Path:
    code, out, _ = run_git(["rev-parse", "--show-toplevel"], start)
    if code == 0:
        return Path(out.strip())
    return start.resolve()


def list_files_with_git(root: Path) -> list[Path] | None:
    code, out, err = run_git(["ls-files", "-co", "--exclude-standard"], root)
    if code != 0:
        debug(f"[warn] git ls-files failed, falling back to manual scan: {err.strip()}")
        return None
    paths: list[Path] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        paths.append(root / line)
    return paths


def manual_scan(root: Path) -> list[Path]:
    paths: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        dirnames[:] = [d for d in dirnames if d not in LOW_SIGNAL_DIR_PARTS]
        for filename in filenames:
            path = current / filename
            if path.is_symlink():
                continue
            paths.append(path)
    return paths


def relative_posix(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def is_within(parent: Path, child: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def path_parts(path_str: str) -> list[str]:
    return [part for part in Path(path_str).parts if part not in {".", ""}]


def is_low_signal_path(path_str: str) -> bool:
    parts = set(path_parts(path_str))
    if parts & LOW_SIGNAL_DIR_PARTS:
        return True
    return any(regex.search(path_str) for regex in LOW_SIGNAL_FILE_REGEXES)


def is_binary_file(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            sample = fh.read(8192)
    except OSError:
        return True
    if b"\x00" in sample:
        return True
    try:
        sample.decode("utf-8")
        return False
    except UnicodeDecodeError:
        try:
            sample.decode("latin-1")
            return False
        except UnicodeDecodeError:
            return True


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1", errors="replace")


def classify_file(rel_path: str, include_docs: bool, include_tests: bool) -> str:
    p = Path(rel_path)
    name = p.name
    suffix = p.suffix.lower()
    lower_path = rel_path.lower()
    if name in ROOT_HIGH_SIGNAL_BASENAMES:
        if name in {"README.md", "README.mdx", "ARCHITECTURE.md", "CONTRIBUTING.md", "AGENTS.md", "PLANS.md"}:
            return "doc"
        if name in {"Dockerfile", "docker-compose.yml", "docker-compose.yaml", "Procfile"}:
            return "infra"
        return "config"
    if include_tests and (
        "/tests/" in f"/{lower_path}/"
        or "/__tests__/" in f"/{lower_path}/"
        or re.search(r"(^|/).*(test|spec)\.[^.]+$", lower_path)
    ):
        return "test"
    if include_docs and (
        suffix in {".md", ".mdx", ".rst", ".txt"}
        or "/docs/" in f"/{lower_path}/"
        or "/adr/" in f"/{lower_path}/"
        or "/architecture/" in f"/{lower_path}/"
    ):
        return "doc"
    if any(token in lower_path for token in ["docker", "k8s", "helm", "terraform", ".github/workflows", "ansible", "deploy", "infra"]):
        return "infra"
    if suffix in {".yaml", ".yml", ".toml", ".json", ".jsonc", ".json5", ".ini", ".cfg", ".conf", ".env", ".properties"}:
        return "config"
    return "source"


def language_for_path(path: Path) -> str | None:
    if path.name == "Dockerfile":
        return "dockerfile"
    if path.name == "Makefile":
        return "make"
    return LANGUAGE_BY_EXTENSION.get(path.suffix.lower())


def extract_markers(text: str) -> list[str]:
    found = sorted({m.group(1).upper() for m in MARKER_REGEX.finditer(text)})
    return found


def goal_keywords(goal: str) -> set[str]:
    words = {w.lower() for w in WORD_REGEX.findall(goal)}
    return {w for w in words if w not in STOPWORDS}


def score_file(
    rel_path: str,
    category: str,
    size: int,
    markers: Sequence[str],
    scopes: Sequence[str],
    g_keywords: set[str],
) -> float:
    score = 0.0
    lower_path = rel_path.lower()
    name = Path(rel_path).name.lower()
    parts = lower_path.split("/")

    if category == "source":
        score += 25
    elif category == "test":
        score += 18
    elif category == "config":
        score += 16
    elif category == "infra":
        score += 14
    elif category == "doc":
        score += 12

    if name in {n.lower() for n in ROOT_HIGH_SIGNAL_BASENAMES}:
        score += 25

    if any(token in lower_path for token in ["main", "app", "server", "router", "route", "handler", "controller", "service", "domain", "usecase", "workflow", "bootstrap"]):
        score += 12

    if any(token in lower_path for token in ["deprecated", "legacy", "obsolete", "migration"]):
        score += 10

    if markers:
        score += 6 + 2 * len(markers)

    if size <= 64_000:
        score += 4
    elif size <= 256_000:
        score += 2
    elif size > 800_000:
        score -= 4

    scope_norms = [s.strip("/").lower() for s in scopes if s.strip()]
    for scope in scope_norms:
        if lower_path == scope or lower_path.startswith(scope + "/"):
            score += 100
        elif scope in lower_path:
            score += 40

    for word in g_keywords:
        if word in name:
            score += 18
        elif word in lower_path:
            score += 8
        elif word in parts:
            score += 10

    return score


def should_skip_text_file(path: Path, rel_path: str, cfg: dict) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if path.is_symlink():
        reasons.append("symlink")
        return True, reasons
    if not path.is_file():
        reasons.append("not-a-regular-file")
        return True, reasons
    if is_low_signal_path(rel_path):
        reasons.append("low-signal-artifact")
        return True, reasons
    if path.name in LOCKFILES and not cfg.get("include_lockfiles", False):
        reasons.append("lockfile-skipped-by-default")
        return True, reasons
    if is_binary_file(path):
        reasons.append("binary")
        return True, reasons
    suffix = path.suffix.lower()
    if suffix and suffix not in TEXT_EXTENSIONS and path.name not in ROOT_HIGH_SIGNAL_BASENAMES:
        try:
            text = read_text(path)
        except OSError:
            reasons.append("unreadable")
            return True, reasons
        if not text.strip():
            reasons.append("empty")
            return True, reasons
    try:
        if path.stat().st_size == 0:
            reasons.append("empty")
            return True, reasons
    except OSError:
        reasons.append("unreadable")
        return True, reasons
    return False, reasons


def select_focused_files(
    candidates: list[tuple[Path, FileRecord, str]],
    cfg: dict,
    scopes: Sequence[str],
) -> list[tuple[Path, FileRecord, str]]:
    budget_tokens = int(cfg["focused_token_budget"])
    budget_chars = budget_tokens * 4

    counts_by_category: Counter[str] = Counter()
    quotas = {"doc": 24, "config": 40, "infra": 30, "source": 220, "test": 80}

    required: list[tuple[Path, FileRecord, str]] = []
    optional: list[tuple[Path, FileRecord, str]] = []
    seen: set[str] = set()

    scope_norms = [s.strip("/").lower() for s in scopes if s.strip()]
    for item in candidates:
        path, rec, text = item
        lower_path = rec.path.lower()
        is_scope = any(lower_path == scope or lower_path.startswith(scope + "/") for scope in scope_norms)
        if path.name in ROOT_HIGH_SIGNAL_BASENAMES or is_scope:
            if rec.path not in seen:
                required.append(item)
                seen.add(rec.path)
        else:
            optional.append(item)

    optional.sort(key=lambda row: (row[1].score, -row[1].size), reverse=True)

    selected: list[tuple[Path, FileRecord, str]] = []
    used_chars = 0

    def maybe_add(item: tuple[Path, FileRecord, str], force: bool = False) -> None:
        nonlocal used_chars
        path, rec, text = item
        if rec.path in {r.path for _, r, _ in selected}:
            return
        projected = used_chars + len(text)
        quota = quotas.get(rec.category, 50)
        if not force and counts_by_category[rec.category] >= quota:
            return
        if not force and projected > budget_chars:
            return
        selected.append(item)
        counts_by_category[rec.category] += 1
        used_chars = projected

    for item in required:
        maybe_add(item, force=True)

    for item in optional:
        maybe_add(item, force=False)
        if used_chars >= budget_chars:
            break

    return selected


def make_repo_tree(paths: Iterable[str]) -> str:
    sorted_paths = sorted(paths)
    lines = ["Repository file map", "====================", ""]
    for rel_path in sorted_paths:
        depth = max(rel_path.count("/"), 0)
        lines.append(f"{'  ' * depth}- {rel_path}")
    return "\n".join(lines) + "\n"


def truncate_for_inline(text: str, max_bytes: int) -> tuple[str, bool]:
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text, False
    target_chars = max(1000, max_bytes // 2)
    head = text[: target_chars]
    tail = text[-target_chars:]
    combined = (
        head
        + "\n\n[... TRUNCATED FOR DIRECT MODE ...]\n\n"
        + tail
    )
    return combined, True


def render_file_block(path: str, category: str, language: str | None, text: str) -> str:
    fence = language or "text"
    return textwrap.dedent(
        f"""
        ===== BEGIN FILE: {path} | category={category} =====
        ```{fence}
        {text}
        ```
        ===== END FILE: {path} =====
        """
    ).strip() + "\n\n"


def shard_context(
    items: list[tuple[Path, FileRecord, str]],
    out_dir: Path,
    prefix: str,
    shard_chars: int,
    max_inline_file_bytes: int,
) -> list[str]:
    if not items:
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    shard_paths: list[str] = []
    current_lines: list[str] = []
    current_chars = 0
    shard_index = 1

    def flush() -> None:
        nonlocal current_lines, current_chars, shard_index
        if not current_lines:
            return
        shard_name = f"{prefix}-{shard_index:03d}.md"
        target = out_dir / shard_name
        target.write_text("".join(current_lines), encoding="utf-8")
        shard_paths.append(str(target))
        current_lines = []
        current_chars = 0
        shard_index += 1

    for _, rec, raw_text in items:
        prepared_text, truncated = truncate_for_inline(raw_text, max_inline_file_bytes)
        rec.inline_truncated = truncated
        rec.bytes_inlined = len(prepared_text.encode("utf-8"))
        block = render_file_block(rec.path, rec.category, rec.language, prepared_text)
        if current_chars and current_chars + len(block) > shard_chars:
            flush()
        current_lines.append(block)
        current_chars += len(block)
    flush()
    return shard_paths


def zip_selected_files(root: Path, members: list[Path], output: Path) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in members:
            arcname = relative_posix(root, path)
            zf.write(path, arcname=arcname)
    return str(output)


def estimated_tokens_from_text(text: str) -> int:
    return max(1, len(text) // 4)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare repository context for local Claude Code agent-team analysis.")
    parser.add_argument("--root", default=".", help="Root directory to inspect.")
    parser.add_argument("--out-dir", default=".codex-analysis/context", help="Output directory for manifests and bundles.")
    parser.add_argument("--goal", default="", help="Analysis goal used for scoring and manifest metadata.")
    parser.add_argument("--scope", nargs="*", default=[], help="Optional paths or subsystem hints to prioritize.")
    parser.add_argument("--mode", choices=["auto", "full", "focused"], default="auto", help="Preparation bias.")
    parser.add_argument("--config", help="Optional JSON config overriding default thresholds.")
    parser.add_argument("--skip-archives", action="store_true", help="Do not produce zip archives.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    start_root = Path(args.root).resolve()
    out_dir = Path(args.out_dir).resolve()
    run_layout = prepare_run_layout(out_dir)
    cfg = load_config(Path(args.config).resolve() if args.config else None)
    if args.skip_archives:
        cfg["skip_archives"] = True

    repo_root = find_repo_root(start_root)
    goal = args.goal.strip()
    scopes = list(args.scope)
    g_keywords = goal_keywords(goal)

    git_paths = list_files_with_git(repo_root)
    file_paths = git_paths if git_paths is not None else manual_scan(repo_root)

    records: list[FileRecord] = []
    text_candidates: list[tuple[Path, FileRecord, str]] = []

    for path in sorted(file_paths):
        if not path.exists():
            continue
        if is_within(out_dir, path):
            continue
        rel_path = relative_posix(repo_root, path)
        skip, reasons = should_skip_text_file(path, rel_path, cfg)
        size = 0
        try:
            size = path.stat().st_size
        except OSError:
            reasons.append("unreadable")
            skip = True
        category = classify_file(rel_path, bool(cfg["include_docs"]), bool(cfg["include_tests"]))
        language = language_for_path(path)

        if skip:
            rec = FileRecord(
                path=rel_path,
                size=size,
                category=category,
                language=language,
                status="skipped",
                reasons=reasons,
            )
            records.append(rec)
            continue

        try:
            text = read_text(path)
        except OSError:
            rec = FileRecord(
                path=rel_path,
                size=size,
                category=category,
                language=language,
                status="skipped",
                reasons=["unreadable"],
            )
            records.append(rec)
            continue

        markers = extract_markers(text)
        score = score_file(rel_path, category, size, markers, scopes, g_keywords)
        rec = FileRecord(
            path=rel_path,
            size=size,
            category=category,
            language=language,
            status="included",
            markers=markers,
            score=round(score, 2),
        )
        records.append(rec)
        text_candidates.append((path, rec, text))

    # Full set in score-desc order for easier context construction.
    text_candidates.sort(key=lambda row: (row[1].score, -row[1].size), reverse=True)

    full_paths = [path for path, _, _ in text_candidates]
    full_text = "\n".join(text for _, _, text in text_candidates)
    full_est_tokens = estimated_tokens_from_text(full_text) if full_text else 0
    full_est_bytes = sum(path.stat().st_size for path in full_paths if path.exists())

    focused_candidates = select_focused_files(text_candidates, cfg, scopes)
    focused_text = "\n".join(text for _, _, text in focused_candidates)
    focused_est_tokens = estimated_tokens_from_text(focused_text) if focused_text else 0
    focused_est_bytes = sum(path.stat().st_size for path, _, _ in focused_candidates if path.exists())

    full_context_items = text_candidates if args.mode == "full" else [
        item for item in text_candidates
        if full_est_tokens <= int(cfg["long_context_threshold"])
    ]

    warnings: list[str] = []
    packaging_recommendation = "direct"

    if full_est_tokens > int(cfg["direct_token_threshold"]):
        warnings.append(
            f"Estimated broad local analysis surface is {full_est_tokens:,} tokens, above the preferred direct-review threshold of {cfg['direct_token_threshold']:,}."
        )
        packaging_recommendation = "direct_warn"
    if full_est_tokens > int(cfg["long_context_threshold"]):
        warnings.append(
            f"Estimated broad local analysis surface is {full_est_tokens:,} tokens, above the long-context warning threshold of {cfg['long_context_threshold']:,}."
        )
        packaging_recommendation = "file_search_full"
    if full_est_bytes > int(cfg["direct_total_bytes_warn"]):
        warnings.append(
            f"Estimated local review payload is {full_est_bytes:,} bytes, above the direct warning threshold of {cfg['direct_total_bytes_warn']:,} bytes."
        )
    if full_est_bytes > int(cfg["direct_total_bytes_hard"]):
        warnings.append(
            f"Estimated local review payload is {full_est_bytes:,} bytes, above the direct hard limit of {cfg['direct_total_bytes_hard']:,} bytes."
        )
        packaging_recommendation = "file_search_full"
    if full_est_bytes > int(cfg["archive_warn_bytes"]):
        warnings.append(
            f"Estimated repository text payload is {full_est_bytes:,} bytes, above the broad-analysis warning threshold of {cfg['archive_warn_bytes']:,} bytes. Broad repo exploration may be slow."
        )
    if full_est_bytes > int(cfg["archive_hard_bytes"]):
        warnings.append(
            f"Estimated repository text payload is {full_est_bytes:,} bytes, above the broad-analysis hard threshold of {cfg['archive_hard_bytes']:,} bytes. A focused local team pass is recommended unless full coverage is explicitly required."
        )
        packaging_recommendation = "focused_file_search"
    if len(text_candidates) > int(cfg["full_retrieval_file_count_threshold"]) or full_est_bytes > int(cfg["full_retrieval_total_bytes_threshold"]):
        warnings.append(
            "A broad full-repository local pass may be operationally heavy; a focused local team pass is recommended unless the user explicitly wants whole-repository coverage."
        )
        packaging_recommendation = "focused_file_search"
    if full_est_tokens > int(cfg["direct_hard_token_threshold"]):
        warnings.append(
            f"Estimated broad local analysis surface is {full_est_tokens:,} tokens, which leaves little response headroom for a single monolithic pass."
        )
        packaging_recommendation = "focused_file_search"
    if scopes:
        warnings.append("Explicit scope hints were provided; a focused local team analysis may produce a better signal-to-noise ratio.")
        if packaging_recommendation == "file_search_full":
            packaging_recommendation = "focused_file_search"
    if args.mode == "focused":
        packaging_recommendation = "focused_file_search"
    elif args.mode == "full" and packaging_recommendation == "focused_file_search":
        warnings.append("Mode was forced to full, but the repository exceeds the focused-team recommendation band.")

    if packaging_recommendation == "focused_file_search":
        mode_recommendation = "focused_team"
    else:
        mode_recommendation = "full_repo_team"

    out_dir.mkdir(parents=True, exist_ok=True)
    repo_tree_path = out_dir / "repo_tree.txt"
    repo_tree_path.write_text(make_repo_tree([rec.path for rec in records if rec.status == "included"]), encoding="utf-8")

    full_context_dir = out_dir / "full_context"
    focused_context_dir = out_dir / "focused_context"

    full_context_shards = []
    if full_est_tokens <= int(cfg["long_context_threshold"]) or args.mode == "full":
        full_context_shards = shard_context(
            text_candidates,
            full_context_dir,
            "full-context",
            int(cfg["focused_context_shard_chars"]),
            int(cfg["max_inline_file_bytes"]),
        )

    focused_context_shards = shard_context(
        focused_candidates,
        focused_context_dir,
        "focused-context",
        int(cfg["focused_context_shard_chars"]),
        int(cfg["max_inline_file_bytes"]),
    )

    full_archive_path: str | None = None
    focused_archive_path: str | None = None
    if not bool(cfg["skip_archives"]):
        full_archive_path = zip_selected_files(repo_root, full_paths, out_dir / "full-source.zip")
        focused_archive_path = zip_selected_files(
            repo_root,
            [path for path, _, _ in focused_candidates],
            out_dir / "focused-source.zip",
        )

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo_root),
        "goal": goal,
        "scope": scopes,
        "run_id": run_layout.run_id,
        "analysis_root": str(run_layout.analysis_root),
        "history_root": str(run_layout.history_root),
        "layout_version": run_layout.layout_version,
        "archived_previous_run_id": run_layout.archived_previous_run_id,
        "keywords": sorted(g_keywords),
        "preparation_mode": args.mode,
        "mode_recommendation": mode_recommendation,
        "packaging_recommendation": packaging_recommendation,
        "warnings": warnings,
        "stats": {
            "included_file_count": len(text_candidates),
            "skipped_file_count": sum(1 for rec in records if rec.status == "skipped"),
            "included_bytes": full_est_bytes,
            "included_estimated_tokens": full_est_tokens,
            "focused_file_count": len(focused_candidates),
            "focused_bytes": focused_est_bytes,
            "focused_estimated_tokens": focused_est_tokens,
        },
        "artifacts": {
            "repo_tree": str(repo_tree_path),
            "full_archive": full_archive_path,
            "focused_archive": focused_archive_path,
            "full_context_shards": full_context_shards,
            "focused_context_shards": focused_context_shards,
        },
        "selections": {
            "full_files": [rec.path for _, rec, _ in text_candidates],
            "focused_files": [rec.path for _, rec, _ in focused_candidates],
        },
        "files": [asdict(rec) for rec in sorted(records, key=lambda r: (r.status != "included", r.path))],
        "config": cfg,
    }

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    summary = {
        "manifest": str(manifest_path),
        "mode_recommendation": mode_recommendation,
        "packaging_recommendation": packaging_recommendation,
        "warnings": warnings,
        "stats": manifest["stats"],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
