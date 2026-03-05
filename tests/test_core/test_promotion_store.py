from pathlib import Path

from btwin.core.promotion_store import PromotionStore


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

    assert approved is not None
    assert approved.status == "approved"
    assert approved.approved_by == "main"


def test_set_status_rejects_invalid_transition(tmp_path: Path) -> None:
    store = PromotionStore(tmp_path / "promotion_queue.yaml")
    item = store.enqueue(source_record_id="rec_01ABC", proposed_by="codex-code")

    result = store.set_status(item.item_id, "promoted", actor="main")

    assert result is None


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
