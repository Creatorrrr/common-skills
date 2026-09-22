#!/usr/bin/env python3
"""Inspect declared experiment records. Read-only; no evaluator or model is run.

This is a small comparison/selection aid, not UCB1/MAP-Elites, a scientific
verifier, a scheduler, or an authorization system. Python 3.10+, stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

MAX_BYTES = 4 * 1024 * 1024
MAX_CANDIDATES = 512
COHORT_KEYS = {"evaluator", "data", "compute", "environment"}
STATES = {"pass", "fail", "pending", "not_run"}
SHA = re.compile(r"[0-9a-f]{64}\Z")


class InputError(ValueError):
    """The snapshot cannot be interpreted safely."""


def _object(value: Any, where: str, required: set[str], optional: set[str] | None = None) -> dict:
    if not isinstance(value, dict):
        raise InputError(f"{where}: expected object")
    missing = required - value.keys()
    extra = value.keys() - required - (optional or set())
    if missing or extra:
        raise InputError(f"{where}: missing={sorted(missing)}, unknown={sorted(extra)}")
    return value


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise InputError(f"{where}: expected nonempty string, at most 4096 characters")
    return value


def _number(value: Any, where: str, *, nullable: bool = False, nonnegative: bool = False) -> float | int | None:
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"{where}: expected finite number" + (" or null" if nullable else ""))
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite or (nonnegative and value < 0):
        raise InputError(f"{where}: invalid finite numeric range")
    return value


def _list(value: Any, where: str, *, maximum: int, minimum: int = 0) -> list:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise InputError(f"{where}: expected array of length {minimum}..{maximum}")
    return value


def _texts(value: Any, where: str, *, maximum: int = 64) -> list[str]:
    result = [_text(v, where) for v in _list(value, where, maximum=maximum)]
    if len(result) != len(set(result)):
        raise InputError(f"{where}: duplicate values")
    return result


def _cohort(value: Any, where: str) -> dict:
    item = _object(value, where, COHORT_KEYS)
    for key in COHORT_KEYS:
        _text(item[key], f"{where}.{key}")
    return item


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise InputError(f"non-finite JSON constant: {value}")


def load_snapshot(path: Path) -> dict:
    # Bounded read rather than stat-then-unbounded-read (file can change).
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise InputError(f"snapshot exceeds {MAX_BYTES} bytes")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicate_keys,
                           parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise InputError(f"invalid UTF-8 JSON: {exc}") from exc
    validate(value)
    return value


def validate(snapshot: Any) -> None:
    top = _object(snapshot, "snapshot", {"schema_version", "comparison", "stages", "promotion_stage",
                                          "objectives", "constraints", "resources", "candidates"}, {"notes"})
    if type(top["schema_version"]) is not int or top["schema_version"] != 1:
        raise InputError("schema_version must be integer 1")
    _cohort(top["comparison"], "comparison")
    stages = _texts(top["stages"], "stages", maximum=10)
    if not stages or top["promotion_stage"] != stages[-1]:
        raise InputError("promotion_stage must be the last declared stage; stages must be nonempty")
    if "notes" in top:
        _text(top["notes"], "notes")
    names: set[str] = set()
    for i, obj in enumerate(_list(top["objectives"], "objectives", minimum=1, maximum=8)):
        _object(obj, f"objective[{i}]", {"name", "direction"})
        name = _text(obj["name"], "objective.name")
        if name in names or obj["direction"] not in ("min", "max"):
            raise InputError("duplicate objective or invalid direction")
        names.add(name)
    constraint_names: set[str] = set()
    for con in _list(top["constraints"], "constraints", maximum=32):
        _object(con, "constraint", {"name", "operator", "limit"})
        name = _text(con["name"], "constraint.name")
        if name in constraint_names or con["operator"] not in (">=", "<="):
            raise InputError("duplicate constraint or invalid operator")
        constraint_names.add(name)
        _number(con["limit"], "constraint.limit")
    if not isinstance(top["resources"], dict) or len(top["resources"]) > 32:
        raise InputError("resources: expected object with at most 32 separate units")
    for unit, row in top["resources"].items():
        _text(unit, "resource unit")
        _object(row, f"resource.{unit}", {"limit", "used", "reserved"})
        for key in row:
            _number(row[key], f"resource.{unit}.{key}", nullable=True, nonnegative=True)
    ids: set[str] = set()
    candidates = _list(top["candidates"], "candidates", maximum=MAX_CANDIDATES)
    metric_names = names | constraint_names
    for c in candidates:
        _object(c, "candidate", {"id", "parent_ids", "family", "fingerprint", "comparison", "validity",
                                   "stages", "measurements", "confirmation"}, {"notes"})
        cid = _text(c["id"], "candidate.id")
        if cid in ids:
            raise InputError(f"duplicate candidate id: {cid}")
        ids.add(cid)
        _text(c["family"], f"{cid}.family")
        if not isinstance(c["fingerprint"], str) or not SHA.fullmatch(c["fingerprint"]):
            raise InputError(f"{cid}.fingerprint: expected lowercase SHA-256")
        parents = _texts(c["parent_ids"], f"{cid}.parent_ids")
        if cid in parents:
            raise InputError(f"{cid}: self-parent is not permitted")
        _cohort(c["comparison"], f"{cid}.comparison")
        if c["validity"] not in ("valid", "invalid", "pending"):
            raise InputError(f"{cid}: invalid validity")
        _object(c["stages"], f"{cid}.stages", set(), set(stages))
        if any(not isinstance(v, str) or v not in STATES for v in c["stages"].values()):
            raise InputError(f"{cid}: invalid stage state")
        _object(c["measurements"], f"{cid}.measurements", set(), set(stages))
        for measurement_stage, metrics in c["measurements"].items():
            _object(metrics, f"{cid}.measurements.{measurement_stage}", set(), metric_names)
            for name, value in metrics.items():
                _number(value, f"{cid}.measurements.{measurement_stage}.{name}", nullable=True)
        confirmation = _object(c["confirmation"], f"{cid}.confirmation", {"status"},
                               {"artifact_sha256", "evaluator", "evidence_refs"})
        if confirmation["status"] not in ("pass", "fail", "inconclusive", "not_run"):
            raise InputError(f"{cid}: invalid confirmation status")
        for key in ("artifact_sha256", "evaluator"):
            if key in confirmation:
                _text(confirmation[key], f"{cid}.confirmation.{key}")
        if "evidence_refs" in confirmation:
            _texts(confirmation["evidence_refs"], f"{cid}.confirmation.evidence_refs")
        if "notes" in c:
            _text(c["notes"], f"{cid}.notes")
    # Validate cycles only among included nodes. Historical parents may be external.
    parents_by_id = {c["id"]: c["parent_ids"] for c in candidates}
    done: set[str] = set()
    active: set[str] = set()
    def visit(node: str) -> None:
        if node in active:
            raise InputError(f"lineage cycle at {node}")
        if node in done or node not in parents_by_id:
            return
        active.add(node)
        for parent in parents_by_id[node]:
            visit(parent)
        active.remove(node)
        done.add(node)
    for cid in sorted(ids):
        visit(cid)


def _base_reasons(c: dict, s: dict, stage: str) -> list[str]:
    reasons: list[str] = []
    if c["comparison"] != s["comparison"]:
        reasons.append("different_comparison_cohort")
    if c["validity"] != "valid":
        reasons.append("run_validity_" + c["validity"])
    for required in s["stages"][:s["stages"].index(stage) + 1]:
        status = c["stages"].get(required, "not_run")
        if status != "pass":
            reasons.append(f"stage:{required}:{status}")
    metrics = c["measurements"].get(stage, {})
    for obj in s["objectives"]:
        if metrics.get(obj["name"]) is None:
            reasons.append("missing_objective:" + obj["name"])
    for con in s["constraints"]:
        value = metrics.get(con["name"])
        if value is None:
            reasons.append("missing_constraint:" + con["name"])
        elif (con["operator"] == "<=" and value > con["limit"]) or (
                con["operator"] == ">=" and value < con["limit"]):
            reasons.append("violated_constraint:" + con["name"])
    return reasons


def _confirmation_reasons(c: dict, s: dict) -> list[str]:
    reasons = _base_reasons(c, s, s["promotion_stage"])
    cf = c["confirmation"]
    if cf["status"] != "pass":
        reasons.append("confirmation_" + cf["status"])
    if cf.get("artifact_sha256") != c["fingerprint"]:
        reasons.append("confirmation_artifact_mismatch")
    if cf.get("evaluator") != s["comparison"]["evaluator"]:
        reasons.append("confirmation_evaluator_mismatch")
    if not cf.get("evidence_refs"):
        reasons.append("confirmation_evidence_missing")
    return reasons


def _dominates(a: dict, b: dict, objectives: list[dict], stage: str) -> bool:
    weak, strict = True, False
    for obj in objectives:
        av, bv = a["measurements"][stage][obj["name"]], b["measurements"][stage][obj["name"]]
        if obj["direction"] == "min":
            weak = weak and av <= bv
            strict = strict or av < bv
        else:
            weak = weak and av >= bv
            strict = strict or av > bv
    return weak and strict


def analyze(snapshot: dict, stage: str, limit: int = 5) -> dict:
    """Return reproducible advisory output; caller retains every adoption decision."""
    validate(snapshot)
    if stage not in snapshot["stages"]:
        raise InputError("requested stage is not declared")
    if type(limit) is not int or not 1 <= limit <= 50:
        raise InputError("reference limit must be integer 1..50")
    rows = sorted(snapshot["candidates"], key=lambda c: c["id"])
    eligible, excluded, duplicate_groups = [], {}, []
    groups: dict[tuple, list] = defaultdict(list)
    for c in rows:
        groups[(tuple(sorted(c["comparison"].items())), c["fingerprint"])].append(c)
    suppressed: dict[str, str] = {}
    for group in groups.values():
        if len(group) < 2:
            continue
        # Replicate outcomes must be reconciled, not silently renamed as novelty.
        signatures = {json.dumps({k: c[k] for k in ("measurements", "stages", "validity")}, sort_keys=True)
                      for c in group}
        # An unrun copy may lack confirmation, but completed verdicts and their
        # artifact/evaluator bindings must agree before choosing a reference.
        confirmations = {(c["confirmation"]["status"], c["confirmation"].get("artifact_sha256"),
                          c["confirmation"].get("evaluator")) for c in group
                         if c["confirmation"]["status"] != "not_run"}
        conflict = len(signatures) > 1 or len(confirmations) > 1
        canonical = min(group, key=lambda c: (bool(_confirmation_reasons(c, snapshot)), c["id"]))
        duplicate_groups.append({"ids": [c["id"] for c in group], "conflicting_records": conflict,
                                 "canonical_reference": None if conflict else canonical["id"]})
        for c in group:
            if conflict:
                suppressed[c["id"]] = "duplicate_conflict_requires_reconciliation"
            elif c["id"] != canonical["id"]:
                suppressed[c["id"]] = "duplicate_reference:" + canonical["id"]
    confirmation_blockers = {}
    confirmed = []
    for c in rows:
        reasons = _base_reasons(c, snapshot, stage)
        conf_reasons = _confirmation_reasons(c, snapshot)
        if c["id"] in suppressed:
            reasons.append(suppressed[c["id"]])
            conf_reasons.append(suppressed[c["id"]])
        if reasons:
            excluded[c["id"]] = reasons
        else:
            eligible.append(c)
        if conf_reasons:
            confirmation_blockers[c["id"]] = conf_reasons
        else:
            confirmed.append(c["id"])
    frontier = [c for c in eligible if not any(_dominates(d, c, snapshot["objectives"], stage) for d in eligible)]
    selected: list[str] = []
    used_families: set[str] = set()
    # Family coverage among non-dominated references, then remaining frontier.
    for c in frontier:
        if len(selected) < limit and c["family"] not in used_families:
            selected.append(c["id"])
            used_families.add(c["family"])
    for c in frontier:
        if len(selected) < limit and c["id"] not in selected:
            selected.append(c["id"])
    # With spare space, preserve an alternative feasible family, even if dominated.
    for c in eligible:
        if len(selected) < limit and c["family"] not in used_families:
            selected.append(c["id"])
            used_families.add(c["family"])
    resources = {}
    for unit, row in sorted(snapshot["resources"].items()):
        unknown = any(v is None for v in row.values())
        remaining = None if unknown else row["limit"] - row["used"] - row["reserved"]
        try:
            remaining_finite = remaining is None or math.isfinite(remaining)
        except OverflowError:
            remaining_finite = False
        if not remaining_finite:
            remaining, unknown = None, True
        resources[unit] = {**row, "remaining": remaining,
                           "state": "unknown" if unknown else ("exceeded" if remaining < 0 else
                                                               "exhausted" if remaining == 0 else "within_declared_limit")}
    payload = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
    return {
        "schema_version": 1, "assessment_basis": "supplied_records_only",
        "snapshot_sha256": hashlib.sha256(payload).hexdigest(),
        "stage": stage, "comparison": snapshot["comparison"],
        "eligible_ids": [c["id"] for c in eligible],
        "pareto_ids": [c["id"] for c in frontier],
        "reference_ids": selected, "excluded": excluded, "duplicate_groups": duplicate_groups,
        "declared_confirmed_ids": confirmed, "confirmation_blockers": confirmation_blockers,
        "resources": resources, "execution_authorized": False, "adoption": "not_decided",
        "limitations": ["Evidence references and fingerprints are not independently verified.",
                        "Comparison IDs do not prove semantic equivalence or evaluator correctness.",
                        "Family labels do not establish novelty; this is not UCB1 or MAP-Elites.",
                        "No uncertainty, causal effect, total research cost, or permission is inferred.",
                        "Existing best artifacts and raw evidence must be preserved by the authorized workflow."]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="strict JSON snapshot; never modified")
    parser.add_argument("--stage", required=True, help="declared comparison stage, e.g. pilot")
    parser.add_argument("--limit", type=int, default=5, help="advisory reference count, not an experiment budget")
    args = parser.parse_args(argv)
    try:
        report = analyze(load_snapshot(args.input), args.stage, args.limit)
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (OSError, ValueError, RecursionError, TypeError) as exc:
        print(json.dumps({"error": str(exc), "execution_authorized": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
