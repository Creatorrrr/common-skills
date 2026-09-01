from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "report_index.py"


def optional_field(label: str, value: str | None) -> list[str]:
    return [f"- {label}: {value}"] if value else []


def failure_report(
    *,
    title: str,
    recorded: str,
    status: str = "open",
    signature: str | None = None,
    identifiers: str | None = None,
    search_terms: str | None = None,
    related_paths: str | None = None,
    environment: str | None = None,
    attempt: str | None = None,
    attempt_reason: str = "did not address the cause",
    related_passed: str | None = None,
    supersedes: str | None = None,
    superseded_by: str | None = None,
    extra_section: str = "",
) -> str:
    lines = [
        f"# {title}",
        "",
        f"- Recorded: {recorded}",
        f"- Status: {status}",
        *optional_field("Problem signature", signature),
        "- Goal/checkpoint: keep authentication available",
        "- Affected scope: auth client",
        *optional_field("Environment/versions", environment),
        *optional_field("Exact identifiers", identifiers),
        *optional_field("Search terms", search_terms),
        *optional_field("Related paths", related_paths),
        *optional_field("Related passed reports", related_passed),
        "",
        "## Failure",
        "",
        "- Conditions or trigger: concurrent recovery request",
        "- Expected: preserve the current session until validation",
        "- Observed: the current session was removed early",
        "- Impact on the goal: authentication became unavailable",
        "",
        "## Cause assessment",
        "",
        "- Confirmed cause or current hypothesis: replacement order was unsafe",
        "- Confidence: confirmed",
        "- Remaining unknowns: none",
    ]
    if attempt:
        lines.extend(
            [
                "",
                "## Attempts",
                "",
                "| Attempt | Result | Why it did not work |",
                "|---|---|---|",
                f"| {attempt} | failed | {attempt_reason} |",
            ]
        )
    lines.extend(
        [
            "",
            "## Resolution or next safe step",
            "",
            "- Resolution/workaround: validate before replacing the session",
            "- Verification: focused recovery test",
            "- Next safe step if unresolved: inspect the server contract",
            "",
            "## Reuse guidance",
            "",
            "- Avoid: deleting the active session before validation",
            "- Prefer: atomic session replacement",
            "- Applicable when: the client owns replacement ordering",
            "- Re-check when: the authentication contract changes",
            "",
            "## Supersession",
            "",
            *optional_field("Supersedes", supersedes),
            *optional_field("Superseded by", superseded_by),
            "- Reason: newer evidence changed the preferred handling",
        ]
    )
    if extra_section:
        lines.extend(["", "## Notes", "", extra_section])
    return "\n".join(lines).rstrip() + "\n"


def passed_report(
    *,
    title: str,
    recorded: str,
    signature: str,
    qualification: str = "non-obvious-after-default-failed",
    related_failed: str | None = None,
    do_not_apply: str = "the server already performs atomic replacement",
) -> str:
    return "\n".join(
        [
            f"# {title}",
            "",
            f"- Recorded: {recorded}",
            "- Status: active",
            f"- Qualification: {qualification}",
            f"- Goal/problem signature: {signature}",
            "- Search terms: auth, session replacement",
            "- Affected scope: auth client",
            "- Excluded scope: server-owned sessions",
            "- Environment/versions: ios-18, app-4.5",
            "- Exact identifiers: refreshSession, F0001",
            "- Related paths: src/auth/session.ts",
            *optional_field("Related failed reports", related_failed),
            "",
            "## Reproduction context",
            "",
            "- Repository/ref or artifact: fixture/main",
            "- Commit: abc123",
            "- External conditions or assumptions: fixed recovery contract",
            "",
            "## Successful approach",
            "",
            "- Prerequisites: a recoverable refresh token",
            "- Sequence: validate the new session, then replace the old session",
            "- Decisive choices: preserve the old session until validation",
            "- Avoided approaches and why: retry-loop hides the ordering defect",
            "",
            "## Evidence and completion criteria",
            "",
            "| Criterion | Direct evidence | Result |",
            "|---|---|---|",
            "| session continuity | focused recovery test | pass |",
            "",
            "## Reuse guidance",
            "",
            "- Prefer: atomic session replacement",
            "- Minimum verification when reused: focused recovery test",
            "- Applicable when: the client owns replacement ordering",
            f"- Do not apply when: {do_not_apply}",
            "- Re-check or invalidate when: the authentication contract changes",
            "",
            "## Supersession",
            "",
            "- Reason: active result",
            "",
        ]
    )


class ReportIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "docs" / "failed-reports").mkdir(parents=True)
        (self.root / "docs" / "passed-reports").mkdir(parents=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_failed(self, name: str, content: str) -> Path:
        path = self.root / "docs" / "failed-reports" / name
        path.write_text(content, encoding="utf-8")
        return path

    def write_passed(self, name: str, content: str) -> Path:
        path = self.root / "docs" / "passed-reports" / name
        path.write_text(content, encoding="utf-8")
        return path

    def write_research(self, name: str, content: str) -> Path:
        directory = self.root / "docs" / "researches"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        path.write_text(content, encoding="utf-8")
        return path

    def run_cli(self, command: str, *arguments: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), command, "--root", str(self.root), *arguments],
            check=False,
            capture_output=True,
        )

    def run_json(self, command: str, *arguments: str, expected_code: int = 0) -> tuple[dict, bytes]:
        result = self.run_cli(command, *arguments)
        self.assertEqual(result.returncode, expected_code, result.stderr.decode("utf-8"))
        return json.loads(result.stdout), result.stdout

    def test_sync_is_deterministic_and_cross_links_check(self) -> None:
        failed_name = "2026-08-13-session-order.md"
        passed_name = "2026-08-13-atomic-session-replacement.md"
        self.write_failed(
            failed_name,
            failure_report(
                title="Session replacement order",
                recorded="2026-08-13 10:00 KST",
                status="resolved",
                signature="AUTH-SESSION-ORDER",
                related_passed=f"[resolution](../passed-reports/{passed_name})",
            ),
        )
        self.write_passed(
            passed_name,
            passed_report(
                title="Atomic session replacement",
                recorded="2026-08-13 11:00 KST",
                signature="AUTH-SESSION-ORDER",
                qualification="resolved-material-failure",
                related_failed=f"[failure](../failed-reports/{failed_name})",
            ),
        )

        self.run_json("sync")
        catalog = self.root / "docs" / "report-index" / "catalog.jsonl"
        first_bytes = catalog.read_bytes()
        self.run_json("sync")
        self.assertEqual(first_bytes, catalog.read_bytes())

        checked, _ = self.run_json("check")
        self.assertTrue(checked["ok"])
        self.assertEqual(checked["report_count"], 2)
        self.assertEqual(checked["sparse_count"], 0)

    def test_research_notes_remain_outside_execution_report_catalog(self) -> None:
        self.write_failed(
            "2026-08-13-report-only.md",
            failure_report(
                title="Execution report only",
                recorded="2026-08-13 10:00 KST",
                signature="REPORT-ONLY-TOKEN",
            ),
        )
        self.write_research(
            "2026-08-13-research-only.md",
            "# Research note\n\n- Evidence status: hypothesis\n\nRESEARCH-ONLY-TOKEN\n",
        )

        self.run_json("sync")
        checked, _ = self.run_json("check")
        self.assertEqual(checked["report_count"], 1)

        queried, _ = self.run_json("query", "RESEARCH-ONLY-TOKEN")
        self.assertEqual(queried["total_matches"], 0)

    def test_catalog_preserves_rich_failure_and_success_capsules(self) -> None:
        self.write_failed(
            "2026-08-13-rich-failure.md",
            failure_report(
                title="Rich failure capsule",
                recorded="2026-08-13 10:00 KST",
                signature="AUTH-RICH-CAPSULE",
                identifiers="F0001, refreshSession",
                search_terms="session ordering",
                related_paths="src/auth/session.ts",
                environment="ios-18, app-4.5",
                attempt="retry-loop",
                attempt_reason="retry-loop preserved the unsafe replacement order",
            ),
        )
        self.write_passed(
            "2026-08-13-rich-success.md",
            passed_report(
                title="Rich success capsule",
                recorded="2026-08-13 11:00 KST",
                signature="AUTH-RICH-SUCCESS",
                do_not_apply="server-atomic-mode owns replacement",
            ),
        )
        self.run_json("sync")
        catalog = self.root / "docs" / "report-index" / "catalog.jsonl"
        records = [json.loads(line) for line in catalog.read_text(encoding="utf-8").splitlines()]
        by_path = {record["source_path"]: record for record in records[1:]}

        failed = by_path["docs/failed-reports/2026-08-13-rich-failure.md"]
        self.assertEqual(failed["routing"]["problem_signature"], "AUTH-RICH-CAPSULE")
        self.assertEqual(failed["routing"]["exact_identifiers"], "F0001, refreshSession")
        self.assertIn("ios-18", failed["routing"]["environment_versions"])
        self.assertEqual(failed["capsule"]["trigger_conditions"], "concurrent recovery request")
        self.assertEqual(failed["capsule"]["expected"], "preserve the current session until validation")
        self.assertEqual(failed["capsule"]["observed"], "the current session was removed early")
        self.assertEqual(failed["capsule"]["confidence"], "confirmed")
        self.assertEqual(failed["capsule"]["failed_attempts"][0]["attempt"], "retry-loop")
        self.assertIn("unsafe replacement order", failed["capsule"]["failed_attempts"][0]["why it did not work"])
        self.assertEqual(
            failed["capsule"]["resolution_workaround"], "validate before replacing the session"
        )
        self.assertEqual(failed["capsule"]["applicable_when"], "the client owns replacement ordering")
        self.assertEqual(failed["capsule"]["recheck_when"], "the authentication contract changes")

        passed = by_path["docs/passed-reports/2026-08-13-rich-success.md"]
        self.assertEqual(passed["capsule"]["qualification"], "non-obvious-after-default-failed")
        self.assertEqual(passed["capsule"]["prerequisites"], "a recoverable refresh token")
        self.assertIn("validate the new session", passed["capsule"]["sequence"])
        self.assertIn("preserve the old session", passed["capsule"]["decisive_choices"])
        self.assertIn("retry-loop", passed["capsule"]["avoided_approaches"])
        self.assertEqual(passed["capsule"]["completion_evidence"][0]["result"], "pass")
        self.assertEqual(
            passed["capsule"]["do_not_apply_when"], "server-atomic-mode owns replacement"
        )

    def test_old_exact_match_beats_recent_loose_match(self) -> None:
        self.write_failed(
            "2022-01-01-exact.md",
            failure_report(
                title="Old exact authentication failure",
                recorded="2022-01-01 00:00 UTC",
                signature="AUTH-F0001",
                identifiers="F0001",
            ),
        )
        self.write_failed(
            "2026-08-13-loose.md",
            failure_report(
                title="Recent general authentication recovery",
                recorded="2026-08-13 12:00 KST",
                signature="general auth recovery",
                search_terms="AUTH F0001",
            ),
        )
        self.run_json("sync")

        queried, _ = self.run_json("query", "AUTH-F0001")
        self.assertEqual(queried["results"][0]["source_path"], "docs/failed-reports/2022-01-01-exact.md")
        self.assertIn("exact problem signature", queried["results"][0]["match_reasons"])

    def test_raw_only_term_and_legacy_sparse_report_work_with_current_catalog(self) -> None:
        self.write_failed(
            "2020-01-01-legacy.md",
            failure_report(
                title="Legacy report without a signature",
                recorded="2020-01-01 00:00 UTC",
                signature=None,
                extra_section="The historical diagnostic marker is RARE-RAW-ONLY-TOKEN.",
            ),
        )

        self.run_json("sync")
        queried, _ = self.run_json("query", "RARE-RAW-ONLY-TOKEN")
        self.assertEqual(queried["catalog_status"], "current")
        self.assertEqual(queried["results"][0]["source_path"], "docs/failed-reports/2020-01-01-legacy.md")
        self.assertTrue(any("RARE-RAW-ONLY-TOKEN" in item for item in queried["results"][0]["matched_snippets"]))

        checked, _ = self.run_json("check")
        self.assertEqual(checked["sparse_count"], 1)

    def test_old_raw_exact_phrase_beats_recent_structured_loose_tokens(self) -> None:
        self.write_failed(
            "2020-01-01-legacy-exact.md",
            failure_report(
                title="Legacy transport note",
                recorded="2020-01-01 00:00 UTC",
                signature=None,
                extra_section="The decisive marker is legacy transport sentinel.",
            ),
        )
        self.write_failed(
            "2026-08-13-many-loose-fields.md",
            failure_report(
                title="Legacy sentinel around current transport",
                recorded="2026-08-13 12:00 KST",
                signature="legacy sentinel around transport",
                identifiers="transport legacy sentinel",
                search_terms="sentinel legacy transport",
                related_paths="src/transport/legacy-sentinel.ts",
                environment="legacy client with transport sentinel mode",
                attempt="transport sentinel legacy retry",
            ),
        )
        self.run_json("sync")

        queried, _ = self.run_json("query", "legacy transport sentinel")
        self.assertEqual(
            queried["results"][0]["source_path"],
            "docs/failed-reports/2020-01-01-legacy-exact.md",
        )
        self.assertIn("exact raw report", queried["results"][0]["match_reasons"])

    def test_superseded_match_returns_current_successor(self) -> None:
        old_name = "2024-01-01-old.md"
        new_name = "2026-08-13-new.md"
        self.write_failed(
            old_name,
            failure_report(
                title="Old transport handling",
                recorded="2024-01-01 00:00 UTC",
                status="superseded",
                signature="TRANSPORT-OLD-EXACT",
                superseded_by=f"[current]({new_name})",
            ),
        )
        self.write_failed(
            new_name,
            failure_report(
                title="Current transport handling",
                recorded="2026-08-13 12:00 KST",
                signature="TRANSPORT-CURRENT",
                supersedes=f"[old]({old_name})",
            ),
        )
        self.run_json("sync")
        checked, _ = self.run_json("check")
        self.assertTrue(checked["ok"])

        queried, _ = self.run_json("query", "TRANSPORT-OLD-EXACT")
        self.assertEqual(
            queried["results"][0]["current_successors"],
            ["docs/failed-reports/2026-08-13-new.md"],
        )

    def test_failed_approach_and_exclusion_are_searchable(self) -> None:
        self.write_failed(
            "2026-08-13-retry.md",
            failure_report(
                title="Retry did not repair ordering",
                recorded="2026-08-13 10:00 KST",
                signature="AUTH-RETRY-ORDER",
                attempt="retry-loop",
                attempt_reason="retry-loop preserved the unsafe replacement order",
            ),
        )
        self.write_passed(
            "2026-08-13-client-only.md",
            passed_report(
                title="Client-owned replacement",
                recorded="2026-08-13 11:00 KST",
                signature="AUTH-CLIENT-OWNED",
                do_not_apply="server-atomic-mode owns replacement",
            ),
        )
        self.run_json("sync")

        retry, _ = self.run_json("query", "retry-loop")
        self.assertEqual(retry["results"][0]["source_path"], "docs/failed-reports/2026-08-13-retry.md")
        exclusion, _ = self.run_json("query", "server-atomic-mode")
        self.assertEqual(
            exclusion["results"][0]["source_path"], "docs/passed-reports/2026-08-13-client-only.md"
        )

    def test_check_detects_stale_source_and_manual_catalog_edit(self) -> None:
        report = self.write_failed(
            "2026-08-13-stale.md",
            failure_report(
                title="Stale detection",
                recorded="2026-08-13 10:00 KST",
                signature="STALE-CHECK",
            ),
        )
        self.run_json("sync")
        report.write_text(report.read_text(encoding="utf-8") + "\nChanged after sync.\n", encoding="utf-8")
        stale, _ = self.run_json("check", expected_code=1)
        self.assertFalse(stale["ok"])
        self.assertTrue(any("differs" in error or "metadata" in error for error in stale["errors"]))

        self.run_json("sync")
        catalog = self.root / "docs" / "report-index" / "catalog.jsonl"
        lines = catalog.read_text(encoding="utf-8").splitlines()
        entry = json.loads(lines[1])
        entry["capsule"]["invented"] = "content not present in the report"
        lines[1] = json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        catalog.write_text("\n".join(lines) + "\n", encoding="utf-8")
        edited, _ = self.run_json("check", expected_code=1)
        self.assertTrue(any("Derived catalog entry differs" in error for error in edited["errors"]))

    def test_check_detects_broken_lifecycle_link(self) -> None:
        self.write_failed(
            "2024-01-01-broken.md",
            failure_report(
                title="Broken lifecycle",
                recorded="2024-01-01 00:00 UTC",
                status="superseded",
                signature="BROKEN-LINK",
                superseded_by="[missing](2099-01-01-missing.md)",
            ),
        )
        self.run_json("sync")
        checked, _ = self.run_json("check", expected_code=1)
        self.assertTrue(any("Broken supersession link" in error for error in checked["errors"]))

    def test_check_detects_missing_and_orphan_catalog_entries(self) -> None:
        self.write_failed(
            "2026-08-13-parity.md",
            failure_report(
                title="Catalog parity",
                recorded="2026-08-13 10:00 KST",
                signature="CATALOG-PARITY",
            ),
        )
        self.run_json("sync")
        catalog = self.root / "docs" / "report-index" / "catalog.jsonl"
        lines = catalog.read_text(encoding="utf-8").splitlines()
        entry = json.loads(lines[1])
        entry["source_path"] = "docs/failed-reports/2099-01-01-orphan.md"
        entry["id"] = "failed:docs/failed-reports/2099-01-01-orphan.md"
        lines[1] = json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        catalog.write_text("\n".join(lines) + "\n", encoding="utf-8")

        checked, _ = self.run_json("check", expected_code=1)
        self.assertTrue(any("Missing catalog entry" in error for error in checked["errors"]))
        self.assertTrue(any("Orphan catalog entry" in error for error in checked["errors"]))

    def test_query_output_is_bounded_and_default_candidate_limit_is_fifteen(self) -> None:
        for index in range(25):
            self.write_failed(
                f"2026-08-{index + 1:02d}-bounded-{index:02d}.md",
                failure_report(
                    title=f"Bounded output report {index}",
                    recorded=f"2026-08-{index + 1:02d} 00:00 UTC",
                    signature=f"BOUNDED-{index}",
                    search_terms="shared-bounded-token",
                    extra_section="shared-bounded-token " + ("detail " * 80),
                ),
            )
        self.run_json("sync")

        default_query, _ = self.run_json("query", "shared-bounded-token")
        self.assertEqual(default_query["returned_matches"], 15)
        self.assertTrue(default_query["truncated"])

        queried, raw = self.run_json("query", "--max-output-bytes", "1000", "shared-bounded-token")
        self.assertLessEqual(len(raw), 1000)
        self.assertLessEqual(queried["returned_matches"], 15)
        self.assertTrue(queried["truncated"])

    def test_deleted_catalog_falls_back_and_can_be_rebuilt(self) -> None:
        self.write_failed(
            "2026-08-13-rebuild.md",
            failure_report(
                title="Rebuild catalog",
                recorded="2026-08-13 10:00 KST",
                signature="CATALOG-REBUILD",
            ),
        )
        self.run_json("sync")
        catalog = self.root / "docs" / "report-index" / "catalog.jsonl"
        catalog.unlink()

        queried, _ = self.run_json("query", "CATALOG-REBUILD")
        self.assertEqual(queried["catalog_status"], "missing-fallback")
        self.run_json("sync")
        checked, _ = self.run_json("check")
        self.assertTrue(checked["ok"])


if __name__ == "__main__":
    unittest.main()
