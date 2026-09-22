"""Executed checks of mechanics, not an evaluation of an agent's judgment."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTPATH = ROOT / "scripts/experiment_preflight.py"
spec = importlib.util.spec_from_file_location("experiment_preflight", SCRIPTPATH)
assert spec and spec.loader
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)
DEMO = ROOT / "examples/preflight"


class ExperimentPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "runner.txt"
        self.source.write_text("synthetic source identity fixture\n")
        self.spec = {"schema_version": 1, "experiment_id": "test-comparison", "arms": {
            "candidate": {"enabled": True, "initial_state": "empty", "reset": ["cache"], "evaluator": "v1"},
            "baseline": {"enabled": False, "initial_state": "empty", "reset": ["cache"], "evaluator": "v1"}},
            "contrasts": [{"id": "effect", "candidate": "candidate", "comparator": "baseline",
                           "claim_kind": "isolated-change", "expected_differences": ["enabled"]}]}
        self.observed = {"schema_version": 1, "experiment_id": "test-comparison", "run_id": "fixture-1",
                         "capture_method": "runtime-probe", "arms": copy.deepcopy(self.spec["arms"]),
                         "evidence": [{"path": "runner.txt", "sha256": hashlib.sha256(self.source.read_bytes()).hexdigest()}]}

    def result(self):
        return preflight.check(self.spec, self.observed, self.root)

    def codes(self):
        return {issue["code"] for issue in self.result()["issues"]}

    def cli(self, spec_text=None, observed_text=None):
        sp, op = self.root / "spec.json", self.root / "observed.json"
        sp.write_text(spec_text if spec_text is not None else json.dumps(self.spec))
        op.write_text(observed_text if observed_text is not None else json.dumps(self.observed))
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, "-B", str(SCRIPTPATH), "--spec", str(sp), "--observed",
                               str(op), "--root", str(self.root)], capture_output=True, text=True, env=env,
                              check=False)

    def test_consistent_facts_do_not_assert_scientific_validity(self):
        result = self.result()
        self.assertEqual(result["status"], "consistent")
        self.assertEqual(result["scientific_validity"], "not_established")
        self.assertEqual(result["source_coverage_and_exporter_truth"], "not_established")
        self.assertEqual(result["contrasts"][0]["actual_differences"], ["enabled"])

    def test_misnamed_baseline_is_detected_even_when_labels_look_correct(self):
        self.observed["arms"]["baseline"]["enabled"] = True
        self.assertEqual(self.codes(), {"DECLARATION_MISMATCH", "CONTRAST_MISMATCH"})

    def test_hidden_extra_reset_is_detected(self):
        self.observed["arms"]["baseline"]["reset"] = ["cache", "statistics"]
        self.assertIn("CONTRAST_MISMATCH", self.codes())

    def test_initialization_mismatch_is_detected(self):
        self.observed["arms"]["baseline"]["initial_state"] = "warm"
        self.assertIn("DECLARATION_MISMATCH", self.codes())

    def test_evaluator_change_is_detected(self):
        self.observed["arms"]["baseline"]["evaluator"] = "v2"
        self.assertIn("CONTRAST_MISMATCH", self.codes())

    def test_same_drift_in_both_arms_is_still_detected(self):
        for arm in self.observed["arms"].values():
            arm["evaluator"] = "v2"
        self.assertEqual(self.codes(), {"DECLARATION_MISMATCH"})

    def test_missing_fact_is_not_equal_to_null(self):
        del self.observed["arms"]["baseline"]["reset"]
        self.assertIn("FACT_SET_MISMATCH", self.codes())

    def test_unexpected_fact_is_not_silently_ignored(self):
        self.observed["arms"]["baseline"]["new_control"] = None
        self.assertIn("FACT_SET_MISMATCH", self.codes())

    def test_missing_and_unexpected_arms(self):
        self.observed["arms"]["unknown"] = self.observed["arms"].pop("baseline")
        self.assertIn("ARM_SET_MISMATCH", self.codes())

    def test_boolean_does_not_equal_integer(self):
        self.observed["arms"]["candidate"]["enabled"] = 1
        self.assertIn("DECLARATION_MISMATCH", self.codes())

    def test_cross_experiment_capture_rejected(self):
        self.observed["experiment_id"] = "other"
        self.assertIn("EXPERIMENT_ID_MISMATCH", self.codes())

    def test_empty_run_id_rejected(self):
        self.observed["run_id"] = " "
        with self.assertRaises(preflight.InputError):
            self.result()

    def test_empty_evidence_rejected(self):
        self.observed["evidence"] = []
        with self.assertRaises(preflight.InputError):
            self.result()

    def test_planned_only_capture_is_not_runtime_evidence(self):
        self.observed["capture_method"] = "copied-from-spec"
        with self.assertRaises(preflight.InputError):
            self.result()

    def test_multiple_changes_cannot_use_isolated_kind(self):
        self.spec["arms"]["baseline"]["initial_state"] = "warm"
        self.spec["contrasts"][0]["expected_differences"].append("initial_state")
        with self.assertRaises(preflight.InputError):
            self.result()

    def test_declared_joint_change_and_system_comparison_are_allowed(self):
        self.spec["arms"]["baseline"]["initial_state"] = "warm"
        self.observed["arms"] = copy.deepcopy(self.spec["arms"])
        self.spec["contrasts"][0]["expected_differences"].append("initial_state")
        for kind in ("joint-change", "system-comparison"):
            with self.subTest(kind=kind):
                self.spec["contrasts"][0]["claim_kind"] = kind
                self.assertEqual(self.result()["status"], "consistent")

    def test_malformed_contrasts_rejected(self):
        original = copy.deepcopy(self.spec)
        mutations = [lambda c: c.update(candidate="unknown"), lambda c: c.update(comparator="candidate"),
                     lambda c: c.update(expected_differences=[]), lambda c: c.update(claim_kind="causal-proof"),
                     lambda c: c.update(expected_differences=["enabled", "enabled"]),
                     lambda c: c.update(expected_differences=["not_a_fact"]),
                     lambda c: c.update(expected_differences=["initial_state"]),
                     lambda c: c.update(claim_kind="joint-change")]
        for mutation in mutations:
            self.spec = copy.deepcopy(original)
            mutation(self.spec["contrasts"][0])
            with self.subTest(contrast=self.spec["contrasts"][0]), self.assertRaises(preflight.InputError):
                self.result()

    def test_duplicate_contrast_rejected(self):
        self.spec["contrasts"].append(copy.deepcopy(self.spec["contrasts"][0]))
        with self.assertRaises(preflight.InputError):
            self.result()

    def test_invalid_top_level_and_schema_rejected(self):
        for version in (True, 1.0, 2, "1", None):
            with self.subTest(version=version):
                self.spec["schema_version"] = version
                with self.assertRaises(preflight.InputError):
                    self.result()
        self.spec["schema_version"] = 1
        self.spec["allow_unsafe"] = True
        with self.assertRaises(preflight.InputError):
            self.result()

    def test_nonfinite_numbers_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                self.observed["arms"]["baseline"]["evaluator"] = value
                with self.assertRaises(preflight.InputError):
                    self.result()

    def test_nested_fact_equality_ignores_object_key_order(self):
        for doc in (self.spec, self.observed):
            for facts in doc["arms"].values():
                facts["evaluator"] = {"name": "v1", "sizes": [1, 2]}
        self.observed["arms"]["baseline"]["evaluator"] = {"sizes": [1, 2], "name": "v1"}
        self.assertEqual(self.result()["status"], "consistent")

    def test_changed_evidence_hash_detected(self):
        self.source.write_text("changed")
        self.assertIn("EVIDENCE_HASH_MISMATCH", self.codes())

    def test_missing_evidence_is_not_refutation(self):
        self.source.unlink()
        self.assertIn("EVIDENCE_MISSING", self.codes())
        self.assertEqual(self.result()["scientific_validity"], "not_established")

    def test_path_traversal_absolute_and_windows_paths_rejected(self):
        for path in ("../secret", "/etc/passwd", "C:/file", "a\\b", "./runner.txt", "a//b"):
            with self.subTest(path=path):
                self.observed["evidence"][0]["path"] = path
                with self.assertRaises(preflight.InputError):
                    self.result()

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "external"
            target.write_text("outside")
            link = self.root / "link.txt"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable on this platform")
            self.observed["evidence"][0]["path"] = "link.txt"
            with self.assertRaises(preflight.InputError):
                self.result()

    def test_invalid_hash_and_duplicate_evidence_rejected(self):
        original = copy.deepcopy(self.observed)
        for digest in ("BAD", 7, None, "A" * 64):
            self.observed = copy.deepcopy(original)
            self.observed["evidence"][0]["sha256"] = digest
            with self.subTest(digest=digest), self.assertRaises(preflight.InputError):
                self.result()
        self.observed = original
        self.observed["evidence"].append(copy.deepcopy(self.observed["evidence"][0]))
        with self.assertRaises(preflight.InputError):
            self.result()

    def test_evidence_size_limit(self):
        with self.source.open("wb") as f:
            f.truncate(preflight.MAX_EVIDENCE_BYTES + 1)
        with self.assertRaises(preflight.InputError):
            self.result()

    def test_cli_exit_codes_and_json(self):
        run = self.cli()
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)["status"], "consistent")
        self.observed["arms"]["baseline"]["enabled"] = True
        run = self.cli()
        self.assertEqual(run.returncode, 1, run.stderr)
        self.assertEqual(json.loads(run.stdout)["status"], "mismatch")
        run = self.cli(spec_text="{broken")
        self.assertEqual(run.returncode, 2, run.stderr)
        self.assertEqual(json.loads(run.stdout)["status"], "input_error")

    def test_cli_duplicate_json_keys_and_oversize_rejected(self):
        for contents in ('{"schema_version":1,"schema_version":2}', " " * (preflight.MAX_JSON_BYTES + 1)):
            with self.subTest(size=len(contents)):
                run = self.cli(spec_text=contents)
                self.assertEqual(run.returncode, 2)
                self.assertEqual(json.loads(run.stdout)["status"], "input_error")

    def test_cli_missing_file_and_nonobject_rejected(self):
        run = self.cli(spec_text="[]")
        self.assertEqual(run.returncode, 2)
        run = subprocess.run([sys.executable, "-B", str(SCRIPTPATH), "--spec", str(self.root / "absent"),
                              "--observed", str(self.root / "absent"), "--root", str(self.root)],
                             capture_output=True, text=True, check=False)
        self.assertEqual(run.returncode, 2)
        self.assertEqual(json.loads(run.stdout)["status"], "input_error")

    def test_cli_oversize_integer_returns_input_error(self):
        run = self.cli(spec_text='{"value":' + "1" * 5000 + "}")
        self.assertEqual(run.returncode, 2, run.stderr)
        self.assertEqual(json.loads(run.stdout)["status"], "input_error")
        self.assertEqual(run.stderr, "")

    def test_cli_null_evidence_path_returns_input_error(self):
        self.observed["evidence"][0]["path"] = "runner\x00.txt"
        run = self.cli()
        self.assertEqual(run.returncode, 2, run.stderr)
        self.assertEqual(json.loads(run.stdout)["status"], "input_error")
        self.assertEqual(run.stderr, "")

    def test_cli_cyclic_evidence_symlink_returns_input_error(self):
        link = self.root / "loop"
        try:
            link.symlink_to("loop")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable on this platform")
        self.observed["evidence"][0]["path"] = "loop"
        run = self.cli()
        self.assertEqual(run.returncode, 2, run.stderr)
        self.assertEqual(json.loads(run.stdout)["status"], "input_error")
        self.assertEqual(run.stderr, "")

    def test_read_only_and_no_sensitive_value_echo(self):
        self.observed["arms"]["candidate"]["evaluator"] = "FAKE_PRIVATE_VALUE"
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        result = self.result()
        self.assertNotIn("FAKE_PRIVATE_VALUE", json.dumps(result))
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_real_factory_example_detects_deliberate_fault(self):
        spec = json.loads((DEMO / "spec.json").read_text())
        for fault in (False, True):
            with self.subTest(fault=fault):
                run = subprocess.run([sys.executable, "-B", str(DEMO / "demo_runtime.py")]
                                     + (["--fault"] if fault else []), capture_output=True, text=True, check=True)
                result = preflight.check(spec, json.loads(run.stdout), DEMO)
                self.assertEqual(result["status"], "mismatch" if fault else "consistent")
                if fault:
                    self.assertEqual(result["contrasts"][0]["actual_differences"], [])


if __name__ == "__main__":
    unittest.main()
