#!/usr/bin/env python3
"""Small self-contained probe. --fault deliberately selects the wrong baseline.

This is a mechanics example, not a performance benchmark or research result.
It prints JSON and performs no writes or network requests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from pathlib import Path


class NoCache:
    def put(self, key: str, value: str) -> None:
        pass

    def get(self, key: str) -> str | None:
        return None

    def reset(self) -> None:
        pass


class MemoryCache(NoCache):
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def put(self, key: str, value: str) -> None:
        self.values[key] = value

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def reset(self) -> None:
        self.values.clear()


def make_variant(name: str, fault: bool = False) -> NoCache:
    # Actual factory branch, not a serializer of the intended spec.
    if name == "candidate" or fault:
        return MemoryCache()
    if name == "baseline":
        return NoCache()
    raise ValueError("unknown variant")


def probe(instance: NoCache) -> dict[str, object]:
    instance.put("example", "value")
    active = instance.get("example") == "value"
    instance.reset()
    assert instance.get("example") is None, "reset did not clear the test entry"
    return {"cache_active": active, "reset_postcondition": "test_entry_absent",
            "initial_state": "empty", "workload_id": "probe-only-v1", "evaluator_id": "probe-only-v1"}


def capture(fault: bool = False) -> dict[str, object]:
    source = Path(__file__)
    return {"schema_version": 1, "experiment_id": "cache-probe-example",
            "run_id": "probe-" + uuid.uuid4().hex, "capture_method": "runtime-probe",
            "arms": {arm: probe(make_variant(arm, fault)) for arm in ("candidate", "baseline")},
            "evidence": [{"path": "demo_runtime.py", "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fault", action="store_true")
    print(json.dumps(capture(parser.parse_args().fault), indent=2))
