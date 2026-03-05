"""Batch worker for processing promotion queue items."""

from __future__ import annotations

from dataclasses import dataclass

from btwin.core.promotion_store import (
    PromotionActorRequiredError,
    PromotionItemNotFoundError,
    PromotionStore,
    PromotionTransitionError,
)
from btwin.core.storage import Storage


@dataclass
class PromotionBatchResult:
    processed: int = 0
    promoted: int = 0
    skipped: int = 0
    errors: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "processed": self.processed,
            "promoted": self.promoted,
            "skipped": self.skipped,
            "errors": self.errors,
        }


class PromotionWorker:
    def __init__(self, *, storage: Storage, promotion_store: PromotionStore) -> None:
        self.storage = storage
        self.promotion_store = promotion_store

    def run_once(self, limit: int | None = None) -> dict[str, int]:
        result = PromotionBatchResult()

        approved_items = self.promotion_store.list_items(status="approved")
        if limit is not None:
            approved_items = approved_items[:limit]

        for item in approved_items:
            result.processed += 1

            source_doc = self.storage.read_collab_record_document(item.source_record_id)
            if source_doc is None:
                result.errors += 1
                continue

            if self.storage.promoted_entry_exists(item.item_id):
                try:
                    self.promotion_store.set_status(item.item_id, "promoted", actor="main")
                    result.skipped += 1
                except (PromotionTransitionError, PromotionItemNotFoundError, PromotionActorRequiredError):
                    result.errors += 1
                continue

            try:
                self.promotion_store.set_status(item.item_id, "queued", actor="main")
            except (PromotionTransitionError, PromotionItemNotFoundError, PromotionActorRequiredError):
                result.errors += 1
                continue

            self.storage.save_promoted_entry(
                item_id=item.item_id,
                source_record_id=item.source_record_id,
                content=str(source_doc.get("content", "")),
            )

            try:
                self.promotion_store.set_status(item.item_id, "promoted", actor="main")
                result.promoted += 1
            except (PromotionTransitionError, PromotionItemNotFoundError, PromotionActorRequiredError):
                result.errors += 1

        return result.as_dict()
