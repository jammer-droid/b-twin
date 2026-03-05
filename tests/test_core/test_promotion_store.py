from pathlib import Path

import pytest

from btwin.core.promotion_store import (
    PromotionActorRequiredError,
    PromotionItemNotFoundError,
    PromotionStore,
    PromotionTransitionError,
)


def test_enqueue_promotion_sets_proposed_status(tmp_path: Path) -> None:
    store = PromotionStore(tmp_path / "promotion_queue.yaml")

    item = store.enqueue(source_record_id="rec_01ABC", proposed_by="codex-code")

    assert item.status == "proposed"
    assert item.source_record_id == "rec_01ABC"
    assert item.proposed_by == "codex-code"


def test_approve_transitions_to_approved(tmp_path: Path) -> None:
    store = PromotionStore(tmp_path / "promotion_queue.yaml")
    item = store.enqueue(source_record_id="rec_01ABC", proposed_by="codex-code")

    approved = store.set_status(item.item_id, "approved", actor="main")

    assert approved.status == "approved"
    assert approved.approved_by == "main"
    assert approved.approved_at is not None


def test_set_status_requires_actor_for_approved(tmp_path: Path) -> None:
    store = PromotionStore(tmp_path / "promotion_queue.yaml")
    item = store.enqueue(source_record_id="rec_01ABC", proposed_by="codex-code")

    with pytest.raises(PromotionActorRequiredError):
        store.set_status(item.item_id, "approved")


def test_set_status_rejects_invalid_transition(tmp_path: Path) -> None:
    store = PromotionStore(tmp_path / "promotion_queue.yaml")
    item = store.enqueue(source_record_id="rec_01ABC", proposed_by="codex-code")

    with pytest.raises(PromotionTransitionError):
        store.set_status(item.item_id, "promoted", actor="main")


def test_set_status_rejects_missing_item(tmp_path: Path) -> None:
    store = PromotionStore(tmp_path / "promotion_queue.yaml")

    with pytest.raises(PromotionItemNotFoundError):
        store.set_status("prm_missing", "approved", actor="main")


def test_store_persists_and_reloads_items(tmp_path: Path) -> None:
    queue_file = tmp_path / "promotion_queue.yaml"
    store = PromotionStore(queue_file)
    item = store.enqueue(source_record_id="rec_01ABC", proposed_by="codex-code")
    store.set_status(item.item_id, "approved", actor="main")

    reloaded = PromotionStore(queue_file)
    items = reloaded.list_items()

    assert len(items) == 1
    assert items[0].status == "approved"
    assert items[0].source_record_id == "rec_01ABC"


def test_transition_chain_sets_timestamps_and_status_filter(tmp_path: Path) -> None:
    store = PromotionStore(tmp_path / "promotion_queue.yaml")
    item = store.enqueue(source_record_id="rec_01ABC", proposed_by="codex-code")

    approved = store.set_status(item.item_id, "approved", actor="main")
    queued = store.set_status(item.item_id, "queued", actor="main")
    promoted = store.set_status(item.item_id, "promoted", actor="main")

    assert approved.approved_at is not None
    assert queued.queued_at is not None
    assert promoted.promoted_at is not None

    promoted_items = store.list_items(status="promoted")
    assert len(promoted_items) == 1
    assert promoted_items[0].item_id == item.item_id


def test_list_items_returns_safe_copies(tmp_path: Path) -> None:
    store = PromotionStore(tmp_path / "promotion_queue.yaml")
    store.enqueue(source_record_id="rec_01ABC", proposed_by="codex-code")

    first = store.list_items()[0]
    second = store.list_items()[0]

    assert first is not second
