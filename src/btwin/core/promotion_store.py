"""YAML-backed promotion queue store."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import yaml

from btwin.core.promotion_models import PromotionItem, PromotionStatus

_ALLOWED_TRANSITIONS: dict[PromotionStatus, set[PromotionStatus]] = {
    "proposed": {"approved"},
    "approved": {"queued"},
    "queued": {"promoted"},
    "promoted": set(),
}


class PromotionStore:
    def __init__(self, queue_path: Path) -> None:
        self.queue_path = queue_path
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        self._items: list[PromotionItem] = self._load_items()

    def list_items(self, status: PromotionStatus | None = None) -> list[PromotionItem]:
        if status is None:
            return list(self._items)
        return [item for item in self._items if item.status == status]

    def enqueue(self, source_record_id: str, proposed_by: str) -> PromotionItem:
        now = datetime.now(timezone.utc)
        item = PromotionItem(
            item_id=f"prm_{uuid4().hex[:12]}",
            source_record_id=source_record_id,
            status="proposed",
            proposed_by=proposed_by,
            proposed_at=now,
        )
        self._items.append(item)
        self._save_items()
        return item

    def set_status(self, item_id: str, to_status: PromotionStatus, actor: str | None = None) -> PromotionItem | None:
        for idx, item in enumerate(self._items):
            if item.item_id != item_id:
                continue

            if to_status not in _ALLOWED_TRANSITIONS[item.status]:
                return None

            now = datetime.now(timezone.utc)
            updates: dict[str, object] = {"status": to_status}
            if to_status == "approved":
                updates["approved_by"] = actor
                updates["approved_at"] = now
            elif to_status == "queued":
                updates["queued_at"] = now
            elif to_status == "promoted":
                updates["promoted_at"] = now

            updated = item.model_copy(update=updates)
            self._items[idx] = updated
            self._save_items()
            return updated

        return None

    def _load_items(self) -> list[PromotionItem]:
        if not self.queue_path.exists():
            return []

        raw = yaml.safe_load(self.queue_path.read_text()) or []
        return [PromotionItem.model_validate(item) for item in raw]

    def _save_items(self) -> None:
        serialized = [item.model_dump(mode="json") for item in self._items]
        self.queue_path.write_text(yaml.dump(serialized, allow_unicode=True, sort_keys=False))
