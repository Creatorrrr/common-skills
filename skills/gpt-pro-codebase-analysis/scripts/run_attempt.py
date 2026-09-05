"""Exclusive attempt lifecycle: preserve old evidence but never leave a stale success active."""
from __future__ import annotations
import os
import shutil
from pathlib import Path
from typing import Any
from analysis_run import generate_run_id
from context_integrity import write_json

ATTEMPT_ARTIFACTS = (
    "analysis_report.md", "response.json", "run_meta.json", "token_report.json",
    "direct_input_files.json", "vector_store_uploads.json", "owned_resources.json",
    "cleanup_report.json", "request_summary.json", "coverage_ledger.json", "approval_used.json",
    "request_meta.json", "handoff", "next-steps.md",
)


class Attempt:
    def __init__(self, out_dir: Path, base_meta: dict[str, Any]) -> None:
        self.out_dir = out_dir
        self.meta = {**base_meta, "attempt_id": generate_run_id("attempt"), "status": "initializing",
                     "terminal_failure": False, "response_status": None, "report_path": None,
                     "input_validation": "pending", "analysis_validation": "pending",
                     "local_verification": "pending"}
        self.fd: int | None = None
        self.lock = out_dir / ".run.lock"

    def __enter__(self) -> "Attempt":
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            os.write(self.fd, str(os.getpid()).encode("ascii"))
            old = [self.out_dir / name for name in ATTEMPT_ARTIFACTS if (self.out_dir / name).exists()]
            if old:
                history = self.out_dir / "attempts" / self.meta["attempt_id"]
                history.mkdir(parents=True)
                for path in old:
                    shutil.move(str(path), str(history / path.name))
            self.save()
            return self
        except BaseException:
            os.close(self.fd)
            self.fd = None
            self.lock.unlink(missing_ok=True)
            raise

    def save(self) -> None:
        write_json(self.out_dir / "run_meta.json", self.meta)

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        try:
            if exc is not None:
                (self.out_dir / "analysis_report.md").unlink(missing_ok=True)
                self.meta.update(status="failed", terminal_failure=True, report_path=None,
                                 error_type=exc_type.__name__, no_retry_performed=True)
                # Avoid leaking credentials/request bodies through arbitrary SDK error strings.
                self.meta["failure_reason"] = str(exc) if isinstance(exc, (ValueError, TimeoutError)) else "Execution error; see error_type. No automatic retry."
                self.save()
        finally:
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None
                self.lock.unlink(missing_ok=True)
        return False
