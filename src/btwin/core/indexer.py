"""Core indexer that keeps markdown entries and vector index in sync."""

from __future__ import annotations

from pathlib import Path

from btwin.core.indexer_manifest import IndexManifest
from btwin.core.indexer_models import IndexEntry, IndexStatus, RecordType
from btwin.core.storage import Storage
from btwin.core.vector import VectorStore


class CoreIndexer:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.storage = Storage(data_dir)
        self.vector_store = VectorStore(persist_dir=data_dir / "index")
        self.manifest = IndexManifest(data_dir / "index_manifest.yaml")

    def mark_pending(self, *, doc_id: str, path: str, record_type: RecordType, checksum: str) -> IndexEntry:
        existing = self.manifest.get(doc_id)
        status: IndexStatus = "pending"
        if existing is not None and existing.checksum != checksum:
            status = "stale"
        elif existing is not None and existing.status in {"failed", "deleted"}:
            status = "pending"
        elif existing is not None:
            status = existing.status

        return self.manifest.upsert(
            doc_id=doc_id,
            path=path,
            record_type=record_type,
            checksum=checksum,
            status=status,
        )

    def refresh(self, limit: int | None = None) -> dict[str, int]:
        processed = 0
        indexed = 0
        deleted = 0
        failed = 0

        queue: list[IndexEntry] = []
        queue.extend(self.manifest.list_by_status("pending"))
        queue.extend(self.manifest.list_by_status("stale"))
        queue.extend(self.manifest.list_by_status("failed"))
        queue.extend(self.manifest.list_by_status("deleted"))

        if limit is not None:
            queue = queue[:limit]

        for item in queue:
            processed += 1

            if item.status == "deleted":
                self.vector_store.delete(item.doc_id)
                deleted += 1
                continue

            source_path = self.data_dir / item.path
            if not source_path.exists():
                self.vector_store.delete(item.doc_id)
                self.manifest.mark_status(item.doc_id, "deleted", error="source file missing")
                deleted += 1
                continue

            try:
                content = source_path.read_text(encoding="utf-8")
                self.vector_store.add(
                    doc_id=item.doc_id,
                    content=content,
                    metadata={
                        "record_type": item.record_type,
                        "path": item.path,
                        "doc_version": str(item.doc_version),
                    },
                )
                self.manifest.mark_status(item.doc_id, "indexed", error=None)
                indexed += 1
            except Exception as exc:  # pragma: no cover - defensive
                self.manifest.mark_status(item.doc_id, "failed", error=str(exc))
                failed += 1

        return {
            "processed": processed,
            "indexed": indexed,
            "deleted": deleted,
            "failed": failed,
        }

    def reconcile(self) -> dict[str, int]:
        docs = self.storage.list_indexable_documents()
        current_doc_ids = {doc["doc_id"] for doc in docs}

        for doc in docs:
            self.mark_pending(
                doc_id=doc["doc_id"],
                path=doc["path"],
                record_type=doc["record_type"],
                checksum=doc["checksum"],
            )

        for status in ("pending", "indexed", "stale", "failed"):
            for item in self.manifest.list_by_status(status):
                if item.doc_id not in current_doc_ids:
                    self.manifest.mark_status(item.doc_id, "deleted", error="reconcile: source missing")

        return self.refresh()

    def repair(self, doc_id: str) -> dict[str, object]:
        item = self.manifest.get(doc_id)
        if item is None:
            return {"ok": False, "error": "not_found", "doc_id": doc_id}

        source_path = self.data_dir / item.path
        if not source_path.exists():
            self.vector_store.delete(item.doc_id)
            self.manifest.mark_status(item.doc_id, "deleted", error="repair: source missing")
            return {"ok": False, "error": "source_missing", "doc_id": doc_id, "status": "deleted"}

        updated = self.manifest.upsert(
            doc_id=item.doc_id,
            path=item.path,
            record_type=item.record_type,
            checksum=item.checksum,
            status="stale",
        )
        result = self.refresh(limit=1)
        refreshed = self.manifest.get(doc_id)
        return {
            "ok": result["indexed"] == 1,
            "doc_id": doc_id,
            "status": refreshed.status if refreshed else "unknown",
        }

    def status_summary(self) -> dict[str, int]:
        return self.manifest.summary()
