#!/usr/bin/env python3
"""Read-only consistency checks for declared and runtime-observed comparisons.

Python 3.10+, standard library only. No target imports, execution, network or writes.
Exit 0: supplied facts/hashes consistent; 1: mismatch; 2: malformed/unreadable input.
Neither exit 0 nor a hash proves scientific validity or exporter completeness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_EVIDENCE_BYTES = 64 * 1024 * 1024
KINDS = {"isolated-change", "joint-change", "system-comparison"}


class InputError(ValueError):
    """Malformed input, distinct from a valid input describing a mismatch."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise InputError(message)


def text(value: Any, label: str) -> str:
    require(isinstance(value, str) and bool(value.strip()), f"{label}: expected nonempty string")
    return value


def keys(value: Any, required: set[str], optional: set[str], label: str) -> None:
    require(isinstance(value, dict), f"{label}: expected object")
    require(required <= value.keys(), f"{label}: missing keys {sorted(required - value.keys())}")
    require(value.keys() <= required | optional,
            f"{label}: unexpected keys {sorted(value.keys() - required - optional)}")


def json_value(value: Any, label: str) -> None:
    """Reject nonfinite numbers and Python-only values; retain bool/int distinction."""
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        require(math.isfinite(value), f"{label}: nonfinite number")
        return
    if isinstance(value, list):
        for i, item in enumerate(value):
            json_value(item, f"{label}[{i}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            text(key, f"{label} key")
            json_value(item, f"{label}.{key}")
        return
    raise InputError(f"{label}: not a JSON value")


def same(left: Any, right: Any) -> bool:
    # JSON encoding prevents True == 1 and distinguishes explicitly different numeric types.
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(
        right, sort_keys=True, allow_nan=False)


def unique_strings(value: Any, label: str, allow_empty: bool = False) -> list[str]:
    require(isinstance(value, list), f"{label}: expected list")
    require(allow_empty or bool(value), f"{label}: empty list")
    for item in value:
        text(item, label)
    require(len(value) == len(set(value)), f"{label}: duplicate entries")
    return value


def strict_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    # Bounded read, including files growing after stat. Do not echo input contents.
    with path.open("rb") as handle:
        raw = handle.read(MAX_JSON_BYTES + 1)
    require(len(raw) <= MAX_JSON_BYTES, "JSON input exceeds 2 MiB")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=strict_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InputError(f"invalid UTF-8 JSON: {type(exc).__name__}") from exc
    require(isinstance(value, dict), "top-level JSON must be an object")
    json_value(value, "input")
    return value


def validate_shape(spec: dict[str, Any], observed: dict[str, Any]) -> None:
    keys(spec, {"schema_version", "experiment_id", "arms", "contrasts"}, {"claim"}, "spec")
    keys(observed, {"schema_version", "experiment_id", "run_id", "capture_method", "arms", "evidence"},
         set(), "observed")
    for name, doc in (("spec", spec), ("observed", observed)):
        json_value(doc, name)
        require(type(doc["schema_version"]) is int and doc["schema_version"] == 1,
                f"{name}: schema_version must be integer 1")
        text(doc["experiment_id"], f"{name}.experiment_id")
        require(isinstance(doc["arms"], dict) and len(doc["arms"]) >= 2,
                f"{name}.arms: at least two arms required")
        for arm, facts in doc["arms"].items():
            text(arm, f"{name}.arm")
            require(isinstance(facts, dict) and bool(facts), f"{name}.{arm}: nonempty facts required")
            for fact in facts:
                text(fact, f"{name}.{arm}.fact")
    if "claim" in spec:
        text(spec["claim"], "spec.claim")
    text(observed["run_id"], "observed.run_id")
    require(observed["capture_method"] in ("runtime-probe", "runtime-export"),
            "capture_method must describe a runtime-probe or runtime-export (self-reported)")
    expected_keys = [set(facts) for facts in spec["arms"].values()]
    require(all(k == expected_keys[0] for k in expected_keys),
            "spec arms must explicitly declare the same fact keys")
    require(isinstance(spec["contrasts"], list) and bool(spec["contrasts"]),
            "spec.contrasts: nonempty list required")
    ids: set[str] = set()
    for contrast in spec["contrasts"]:
        keys(contrast, {"id", "candidate", "comparator", "claim_kind", "expected_differences"},
             set(), "contrast")
        cid = text(contrast["id"], "contrast.id")
        require(cid not in ids, "duplicate contrast ID")
        ids.add(cid)
        for role in ("candidate", "comparator"):
            text(contrast[role], f"contrast.{role}")
            require(contrast[role] in spec["arms"], f"contrast.{role}: unknown arm")
        require(contrast["candidate"] != contrast["comparator"], "contrast cannot compare an arm to itself")
        require(isinstance(contrast["claim_kind"], str) and contrast["claim_kind"] in KINDS,
                "unknown claim_kind")
        differences = unique_strings(contrast["expected_differences"], "expected_differences")
        require(set(differences) <= expected_keys[0], "contrast refers to unknown fact keys")
        count = len(differences)
        if contrast["claim_kind"] == "isolated-change":
            require(count == 1, "isolated-change requires exactly one declared differing fact")
        elif contrast["claim_kind"] == "joint-change":
            require(count >= 2, "joint-change requires at least two declared differing facts")
        planned = {key for key in expected_keys[0]
                   if not same(spec["arms"][contrast["candidate"]][key],
                               spec["arms"][contrast["comparator"]][key])}
        require(planned == set(differences), "spec contrast differences do not match expected arm facts")
    require(isinstance(observed["evidence"], list) and bool(observed["evidence"]),
            "observed.evidence: nonempty list required")
    paths: set[str] = set()
    for item in observed["evidence"]:
        keys(item, {"path", "sha256"}, set(), "evidence")
        name = text(item["path"], "evidence.path")
        p = PurePosixPath(name)
        require(not p.is_absolute() and ".." not in p.parts and "\\" not in name
                and ":" not in name and str(p) == name,
                "evidence paths must be normalized, relative POSIX paths inside --root")
        require(name not in paths, "duplicate evidence path")
        paths.add(name)
        require(isinstance(item["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) is not None,
                "evidence.sha256: expected 64 lowercase hexadecimal digits")


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            total += len(chunk)
            require(total <= MAX_EVIDENCE_BYTES, "evidence file exceeds 64 MiB; use a small provenance manifest")
            digest.update(chunk)
    return digest.hexdigest()


def check(spec: dict[str, Any], observed: dict[str, Any], root: Path) -> dict[str, Any]:
    validate_shape(spec, observed)
    root = root.resolve(strict=True)
    require(root.is_dir(), "evidence root must be a directory")
    issues: list[dict[str, str]] = []

    def issue(code: str, location: str, message: str) -> None:
        # Do not return actual fact values or file contents; they may contain sensitive material.
        issues.append({"code": code, "location": location, "message": message})

    if spec["experiment_id"] != observed["experiment_id"]:
        issue("EXPERIMENT_ID_MISMATCH", "experiment_id", "Observed capture belongs to another experiment.")
    expected_arms, actual_arms = spec["arms"], observed["arms"]
    if set(expected_arms) != set(actual_arms):
        issue("ARM_SET_MISMATCH", "arms", "Missing or unexpected observed arms.")
    for arm in expected_arms.keys() & actual_arms.keys():
        expected, actual = expected_arms[arm], actual_arms[arm]
        if set(expected) != set(actual):
            issue("FACT_SET_MISMATCH", f"arms.{arm}", "Missing or unexpected observed fact keys.")
        for fact in expected.keys() & actual.keys():
            if not same(expected[fact], actual[fact]):
                issue("DECLARATION_MISMATCH", f"arms.{arm}.{fact}", "Declared and observed values differ.")
    contrasts: list[dict[str, Any]] = []
    for contrast in spec["contrasts"]:
        a, b = contrast["candidate"], contrast["comparator"]
        if a not in actual_arms or b not in actual_arms:
            continue
        left, right = actual_arms[a], actual_arms[b]
        differences = sorted(key for key in left.keys() | right.keys()
                             if key not in left or key not in right or not same(left[key], right[key]))
        contrasts.append({"id": contrast["id"], "claim_kind": contrast["claim_kind"],
                          "actual_differences": differences})
        if set(differences) != set(contrast["expected_differences"]):
            issue("CONTRAST_MISMATCH", f"contrasts.{contrast['id']}",
                  "Actual changes differ from the predeclared contrast, including no-op or extra changes.")
    checked = 0
    for item in observed["evidence"]:
        try:
            target = (root / item["path"]).resolve(strict=True)
            require(target.is_relative_to(root), "evidence resolves outside --root")
            require(target.is_file(), "evidence must be a regular file")
            digest = file_digest(target)
            checked += 1
            if digest != item["sha256"]:
                issue("EVIDENCE_HASH_MISMATCH", item["path"], "Evidence file changed since capture.")
        except FileNotFoundError:
            issue("EVIDENCE_MISSING", item["path"], "Evidence file is absent; this is not scientific refutation.")
    return {
        "schema_version": 1,
        "status": "mismatch" if issues else "consistent",
        "experiment_id": spec["experiment_id"],
        "run_id": observed["run_id"],
        "contrasts": contrasts,
        "evidence_files_hashed": checked,
        "issues": sorted(issues, key=lambda item: (item["location"], item["code"])),
        "scientific_validity": "not_established",
        "source_coverage_and_exporter_truth": "not_established",
        "notice": "Consistency of supplied facts and hashes only; not execution authorization or causal proof.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path, help="Predeclared comparison JSON")
    parser.add_argument("--observed", required=True, type=Path, help="Actual runtime facts JSON")
    parser.add_argument("--root", required=True, type=Path, help="Allowed root for evidence files")
    args = parser.parse_args(argv)
    try:
        result = check(load_json(args.spec), load_json(args.observed), args.root)
        code = 0 if result["status"] == "consistent" else 1
    # Native JSON/path limits raise ValueError. Older pathlib versions report
    # symlink loops as RuntimeError, which also covers recursion-limit failures.
    except (ValueError, OSError, RuntimeError, TypeError) as exc:
        result = {"schema_version": 1, "status": "input_error", "scientific_validity": "not_established",
                  "error": str(exc) if isinstance(exc, InputError) else type(exc).__name__}
        code = 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
