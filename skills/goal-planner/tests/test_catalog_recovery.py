"""Regression tests for malformed catalogs, with CLI-level recovery checks."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "report_index.py"
SPEC = importlib.util.spec_from_file_location("goal_planner_report_index_recovery", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
index = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = index
SPEC.loader.exec_module(index)


class CatalogRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        directory = self.root / "docs" / "failed-reports"
        directory.mkdir(parents=True)
        self.report = directory / "2026-09-05-recovery.md"
        self.report.write_text(
            "# Recovery fixture\n\n- Recorded: 2026-09-05 12:00 KST\n"
            "- Status: open\n- Problem signature: RECOVERY-SENTINEL\n"
            "\n## Failure\n\n- Expected: recover from raw reports\n"
            "- Observed: malformed catalog\n",
            encoding="utf-8",
        )
        self.catalog = self.root / "docs" / "report-index" / "catalog.jsonl"
        self.catalog.parent.mkdir(parents=True)
        self.entries = index.build_entries(index.discover_reports(self.root))
        self.header = index.catalog_records(self.entries)[0]

    def cli(self, command: str, *arguments: str) -> subprocess.CompletedProcess[bytes]:
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT), command, "--root", str(self.root), *arguments],
            capture_output=True, check=False, timeout=30, env=environment,
        )

    def write_records(self, *records: object) -> None:
        self.catalog.write_text(
            "\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8"
        )

    def test_non_object_headers_rejected_with_domain_error(self) -> None:
        # Both '_meta' in a string and '_meta' in an array used to reach unsafe indexing.
        for header in (42, 1.5, None, True, False, "_meta", "text", [], ["_meta"], ["_meta", {}]):
            with self.subTest(header=header):
                self.write_records(header, *self.entries)
                with self.assertRaisesRegex(index.ReportIndexError, "_meta object record"):
                    index.read_catalog(self.root)
                status, entries, warnings = index.validate_catalog(self.root, self.entries)
                self.assertEqual(status, "invalid-fallback")
                self.assertEqual(entries, self.entries)
                self.assertTrue(warnings)

    def test_non_object_metadata_rejected(self) -> None:
        for value in (42, 1.5, None, True, "metadata", [], ["schema_version"]):
            with self.subTest(value=value):
                self.write_records({"_meta": value})
                with self.assertRaisesRegex(index.ReportIndexError, "_meta must be an object"):
                    index.read_catalog(self.root)

    def test_non_object_body_records_rejected(self) -> None:
        for value in (42, None, True, "source_path", [], ["source_path"]):
            with self.subTest(value=value):
                self.write_records(self.header, value)
                with self.assertRaisesRegex(index.ReportIndexError, "entry must be an object"):
                    index.read_catalog(self.root)

    def test_empty_invalid_json_and_invalid_utf8_use_fallback(self) -> None:
        for content in (b"", b"\n\n", b"{not-json}\n", b"\xff\xfe\n"):
            with self.subTest(content=content):
                self.catalog.write_bytes(content)
                status, entries, warnings = index.validate_catalog(self.root, self.entries)
                self.assertEqual(status, "invalid-fallback")
                self.assertEqual(entries, self.entries)
                self.assertTrue(warnings)

    def test_cli_query_recovers_without_rewriting_bad_catalog(self) -> None:
        original_report = self.report.read_bytes()
        for header in (42, None, "_meta", ["_meta"]):
            with self.subTest(header=header):
                self.write_records(header)
                bad_bytes = self.catalog.read_bytes()
                catalog_mtime = self.catalog.stat().st_mtime_ns
                paths_before = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
                result = self.cli("query", "RECOVERY-SENTINEL")
                self.assertEqual(result.returncode, 0, result.stderr.decode())
                self.assertNotIn(b"Traceback", result.stderr)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["catalog_status"], "invalid-fallback")
                self.assertEqual(payload["total_matches"], 1)
                self.assertEqual(payload["results"][0]["source_path"],
                                 "docs/failed-reports/2026-09-05-recovery.md")
                self.assertEqual(self.catalog.read_bytes(), bad_bytes)
                self.assertEqual(self.catalog.stat().st_mtime_ns, catalog_mtime)
                self.assertEqual(self.report.read_bytes(), original_report)
                self.assertEqual(paths_before, sorted(str(p.relative_to(self.root))
                                                      for p in self.root.rglob("*")))

    def test_cli_check_reports_bad_catalog_without_traceback(self) -> None:
        for content in (b"42\n", b"\xff\n"):
            with self.subTest(content=content):
                self.catalog.write_bytes(content)
                result = self.cli("check")
                self.assertEqual(result.returncode, 1, result.stderr.decode())
                self.assertNotIn(b"Traceback", result.stderr)
                payload = json.loads(result.stdout)
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["catalog_status"], "invalid-fallback")
                self.assertEqual(self.catalog.read_bytes(), content)

    def test_explicit_sync_repairs_catalog_and_check_passes(self) -> None:
        self.write_records(42)
        original_report = self.report.read_bytes()
        synced = self.cli("sync")
        self.assertEqual(synced.returncode, 0, synced.stderr.decode())
        checked = self.cli("check")
        self.assertEqual(checked.returncode, 0, checked.stderr.decode())
        self.assertTrue(json.loads(checked.stdout)["ok"])
        self.assertEqual(self.report.read_bytes(), original_report)
        meta, entries = index.read_catalog(self.root)
        self.assertEqual(meta["generator_version"], "1.0.1")
        self.assertEqual(meta["schema_version"], 1)
        self.assertEqual(entries, self.entries)

    def test_legacy_generator_metadata_falls_back_until_rebuilt(self) -> None:
        header = json.loads(json.dumps(self.header))
        header["_meta"]["generator_version"] = "1.0.0"
        self.write_records(header, *self.entries)
        status, entries, warnings = index.validate_catalog(self.root, self.entries)
        self.assertEqual(status, "stale-fallback")
        self.assertEqual(entries, self.entries)
        self.assertTrue(warnings)
        index.write_catalog(self.root, self.entries)
        self.assertEqual(index.validate_catalog(self.root, self.entries)[0], "current")

    def test_invalid_source_paths_do_not_crash_catalog_validation(self) -> None:
        for source_path in (None, 42, [], {}, ""):
            with self.subTest(source_path=source_path):
                self.write_records(self.header, {"source_path": source_path})
                status, entries, warnings = index.validate_catalog(self.root, self.entries)
                self.assertEqual(status, "stale-fallback")
                self.assertEqual(entries, self.entries)
                self.assertTrue(any("valid source_path" in w for w in warnings))

    def test_bad_catalog_with_no_reports_returns_empty_query(self) -> None:
        self.report.unlink()
        self.write_records(42)
        result = self.cli("query", "RECOVERY-SENTINEL")
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        payload = json.loads(result.stdout)
        self.assertEqual(payload["catalog_status"], "invalid-fallback")
        self.assertEqual(payload["total_matches"], 0)
        self.assertEqual(payload["results"], [])


if __name__ == "__main__":
    unittest.main()
