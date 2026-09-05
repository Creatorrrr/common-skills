"""Owned-resource lifecycle and normalized retrieval inputs. No credentials in logs."""
from __future__ import annotations
import json
from pathlib import Path
from time import monotonic, sleep
from typing import Any
from context_integrity import NORMALIZATION_VERSION, canonical_hash, sha256_bytes, write_json
from prepare_analysis_context import decode_source


def normalized_documents(contents: dict[str, bytes], paths: list[str], chunk_chars: int = 160_000) -> list[dict[str, Any]]:
    """Every source character is retained. A fragment records original line and column.
    Generated UTF-8 .txt files avoid relying on service support for source extensions.
    """
    if chunk_chars < 1:
        raise ValueError("chunk_chars must be positive")
    documents = []
    for path in paths:
        if path not in contents:
            raise ValueError(f"Selected file missing from verified snapshot: {path}")
        raw = contents[path]
        text, _ = decode_source(raw)
        chunks = [text[i:i + chunk_chars] for i in range(0, len(text), chunk_chars)] or [""]
        offset = 0
        for index, chunk in enumerate(chunks, 1):
            line_start = text.count("\n", 0, offset) + 1
            prior_newline = text.rfind("\n", 0, offset)
            column_start = offset - prior_newline
            header = {"original_path": path, "source_sha256": sha256_bytes(raw),
                      "normalization": NORMALIZATION_VERSION, "part": index, "parts": len(chunks),
                      "character_offset": offset, "original_line_start": line_start,
                      "original_column_start": column_start}
            numbered = []
            line = line_start
            # split on LF only: CR is preserved, and source line numbers remain reproducible.
            segments = chunk.split("\n")
            for n, segment in enumerate(segments):
                if n == len(segments) - 1 and segment == "":
                    continue
                newline = "\n" if n < len(segments) - 1 else ""
                numbered.append(f"{line:06d}: {segment}{newline}")
                line += bool(newline)
            body = (json.dumps(header, ensure_ascii=True) + "\nBEGIN UNTRUSTED SOURCE\n" +
                    "".join(numbered) + "\nEND UNTRUSTED SOURCE\n").encode("utf-8")
            name = canonical_hash({"path": path})[:24] + f"-{index:05d}.txt"
            documents.append({"path": path, "filename": name, "data": body,
                              "sha256": sha256_bytes(body), "source_sha256": header["source_sha256"],
                              "part": index, "parts": len(chunks), "line_start": line_start,
                              "column_start": column_start, "character_offset": offset,
                              "character_length": len(chunk)})
            offset += len(chunk)
    if set(x["path"] for x in documents) != set(paths):
        raise ValueError("Normalized document set is incomplete.")
    return documents


class OwnedResources:
    def __init__(self, client: Any, journal: Path | None = None) -> None:
        self.client = client
        self.journal = journal
        self.files: list[str] = []
        self.vector_stores: list[str] = []
        self.response_id: str | None = None
        self.flush()

    def flush(self) -> None:
        if self.journal:
            write_json(self.journal, {"owned_file_ids": self.files, "owned_vector_store_ids": self.vector_stores,
                                      "created_response_id": self.response_id})

    def add_file(self, file_id: str) -> None:
        self.files.append(file_id)
        self.flush()

    def add_vector_store(self, store_id: str) -> None:
        self.vector_stores.append(store_id)
        self.flush()

    def cleanup(self, *, retain: bool = False) -> dict[str, Any]:
        if retain:
            return {"status": "retained_by_approval", "owned_file_ids": self.files,
                    "owned_vector_store_ids": self.vector_stores, "events": []}
        events: list[dict[str, Any]] = []
        for kind, ids, resource in [("vector_store", self.vector_stores, self.client.vector_stores),
                                     ("file", self.files, self.client.files)]:
            for resource_id in ids:
                try:
                    result = resource.delete(resource_id)
                    if getattr(result, "deleted", None) is not True:
                        raise RuntimeError("Deletion not acknowledged")
                    events.append({"kind": kind, "id": resource_id, "deleted": True})
                except Exception as exc:
                    if getattr(exc, "status_code", None) == 404:
                        events.append({"kind": kind, "id": resource_id, "deleted": True, "already_absent": True})
                    else:
                        events.append({"kind": kind, "id": resource_id, "deleted": False,
                                       "error_type": type(exc).__name__})
        return {"status": "completed" if all(x["deleted"] for x in events) else "incomplete", "events": events}


def upload_documents(client: Any, name: str, documents: list[dict[str, Any]], *, owned: OwnedResources,
                     snapshot_id: str, selection_hash: str, expires_days: int = 1,
                     timeout_seconds: float = 1800) -> tuple[Any, list[dict[str, Any]]]:
    if not documents or len({d["filename"] for d in documents}) != len(documents):
        raise ValueError("Empty or duplicate normalized input set.")
    for d in documents:
        if sha256_bytes(d["data"]) != d["sha256"] or len(d["data"]) > 4_000_000:
            raise ValueError("Invalid or oversized normalized input; refusing partial upload.")
    vs = client.vector_stores.create(name=name, expires_after={"anchor": "last_active_at", "days": expires_days},
        metadata={"snapshot_id": snapshot_id, "selection_hash": selection_hash, "normalization": NORMALIZATION_VERSION})
    owned.add_vector_store(vs.id)
    uploaded: list[dict[str, Any]] = []
    for d in documents:
        obj = client.files.create(file=(d["filename"], d["data"], "text/plain"), purpose="assistants",
                                  expires_after={"anchor": "created_at", "seconds": expires_days * 86400})
        owned.add_file(obj.id)  # Journal before attaching: attachment failure must not orphan an owned file.
        client.vector_stores.files.create(vector_store_id=vs.id, file_id=obj.id,
            chunking_strategy={"type": "static", "static": {"max_chunk_size_tokens": 800, "chunk_overlap_tokens": 400}})
        uploaded.append({k: v for k, v in d.items() if k != "data"} | {"file_id": obj.id})
    deadline = monotonic() + timeout_seconds
    while True:
        statuses = [getattr(client.vector_stores.files.retrieve(vector_store_id=vs.id, file_id=d["file_id"]),
                            "status", None) for d in uploaded]
        if any(s not in {"completed", "queued", "in_progress"} for s in statuses):
            raise RuntimeError("Vector-store ingestion incomplete; refusing a partial analysis.")
        if all(s == "completed" for s in statuses):
            return vs, uploaded
        if monotonic() >= deadline:
            raise TimeoutError("Vector-store ingestion timed out; no analysis request submitted.")
        sleep(min(3, max(0, deadline - monotonic())))


def verify_reused_store(client: Any, store_id: str, receipt: dict[str, Any], documents: list[dict[str, Any]],
                        snapshot_id: str, selection_hash: str) -> Any:
    expected_binding = {"snapshot_id": snapshot_id, "selection_hash": selection_hash,
                        "normalization": NORMALIZATION_VERSION}
    if receipt.get("vector_store_id") != store_id or receipt.get("binding") != expected_binding:
        raise ValueError("Reuse receipt does not match the requested snapshot and selection.")
    vs = client.vector_stores.retrieve(store_id)
    if getattr(vs, "status", None) != "completed" or getattr(vs, "metadata", None) != expected_binding:
        raise ValueError("Remote vector store is not complete or its identity differs.")
    expected = {d["filename"]: d for d in documents}
    entries = receipt.get("files", [])
    if len(entries) != len(expected) or {d["filename"] for d in entries} != set(expected):
        raise ValueError("Reuse receipt file coverage differs from this selection.")
    actual = list(client.vector_stores.files.list(vector_store_id=store_id))  # SDK iterator paginates.
    if len(actual) != len(entries) or {x.id for x in actual} != {x["file_id"] for x in entries}:
        raise ValueError("Remote vector-store membership differs from receipt.")
    if any(x.status != "completed" for x in actual):
        raise ValueError("Reused vector store contains incomplete files.")
    for item in entries:
        if item["sha256"] != expected[item["filename"]]["sha256"]:
            raise ValueError("Reuse receipt source hash mismatch.")
        body = client.files.content(item["file_id"]).read()
        if sha256_bytes(body) != item["sha256"]:
            raise ValueError("Remote file bytes differ from this snapshot's normalized input.")
    return vs  # Intentionally never added to OwnedResources.
