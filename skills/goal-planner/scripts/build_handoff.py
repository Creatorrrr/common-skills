#!/usr/bin/env python3
"""Compile selected portable contracts once; stdout only, no project execution.

A handoff is authored text, never an authorization token. The goal file must
state actual operation, limits and success criteria. Python 3.10+, stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ORDER = ("Core", "Program", "Experiment", "Direction", "Research", "Retrieval", "Persistence")
CONTRACT = Path(__file__).resolve().parents[1] / "references" / "execution-contract.md"
MAX_INPUT = 512 * 1024
MARKER = re.compile(r"\{\{[^{}]+\}\}")
BLOCK = re.compile(r"^## ([A-Za-z]+)[^\n]*\n+```text\n(.*?)\n```", re.MULTILINE | re.DOTALL)


class HandoffError(ValueError):
    pass


def read_text(path: Path) -> str:
    with path.open("rb") as stream:
        raw = stream.read(MAX_INPUT + 1)
    if len(raw) > MAX_INPUT:
        raise HandoffError("input exceeds 512 KiB; use a bounded relevant goal/contract file")
    return raw.decode("utf-8")


def parse_blocks(text: str) -> dict[str, str]:
    found = BLOCK.findall(text)
    if len(found) != len(ORDER) or {name for name, _ in found} != set(ORDER):
        raise HandoffError("expected exactly seven unique named contract blocks")
    blocks = dict(found)
    if any(not body.strip() or MARKER.search(body) for body in blocks.values()):
        raise HandoffError("empty contract or unresolved contract marker")
    return blocks


def compile_handoff(goal: str, blocks: dict[str, str], selected: list[str], max_bytes: int | None = None) -> tuple[str, dict]:
    if not goal.strip() or MARKER.search(goal):
        raise HandoffError("goal must be nonempty and have no unresolved {{markers}}")
    if set(blocks) != set(ORDER) or any(not isinstance(v, str) or not v.strip() for v in blocks.values()):
        raise HandoffError("incomplete contract source")
    if not selected or "Core" not in selected:
        raise HandoffError("Core is required")
    if len(selected) != len(set(selected)) or set(selected) - set(ORDER):
        raise HandoffError("duplicate or unknown selected contract")
    if max_bytes is not None and (type(max_bytes) is not int or max_bytes <= 0):
        raise HandoffError("max-bytes must be positive")
    for name in ORDER:
        if blocks[name] in goal:
            raise HandoffError("goal already embeds a contract; provide goal-specific content only")
    chosen = [name for name in ORDER if name in selected]
    text = "# Goal handoff\n\n## Requested outcome and boundaries\n\n" + goal.strip() + "\n\n"
    text += "\n\n".join(f"## {name}\n\n{blocks[name]}" for name in chosen) + "\n"
    if MARKER.search(text):
        raise HandoffError("unresolved marker in rendered handoff")
    raw = text.encode("utf-8")
    if max_bytes is not None and len(raw) > max_bytes:
        raise HandoffError(f"handoff needs {len(raw)} bytes, cap is {max_bytes}; no content emitted or truncated. "
                           "Use an accessible durable plan plus a short launcher; do not drop active rules.")
    stats = {"selected_blocks": chosen, "block_count": len(chosen), "utf8_bytes": len(raw),
             "characters": len(text), "sha256": hashlib.sha256(raw).hexdigest(),
             "token_count": "not_measured", "execution_authorized": False}
    return text, stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--goal-file", required=True, type=Path)
    parser.add_argument("--blocks", default="Core", help="comma-separated names; selection does not grant authority")
    parser.add_argument("--max-bytes", type=int)
    parser.add_argument("--stats", action="store_true", help="print exact size/hash to stderr, not guessed tokens")
    args = parser.parse_args(argv)
    try:
        text, stats = compile_handoff(read_text(args.goal_file), parse_blocks(read_text(CONTRACT)),
                                      [x.strip() for x in args.blocks.split(",")], args.max_bytes)
        sys.stdout.write(text)
        if args.stats:
            print(json.dumps(stats, ensure_ascii=False), file=sys.stderr)
        return 0
    except (OSError, UnicodeError, HandoffError) as exc:
        print(json.dumps({"error": str(exc), "execution_authorized": False}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
