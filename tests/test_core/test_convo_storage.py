from btwin.core.storage import Storage


def test_save_convo_record_writes_under_convo_dir(tmp_path):
    storage = Storage(tmp_path)

    entry = storage.save_convo_record(content="기억해줘", requested_by_user=True)

    convo_path = tmp_path / "entries" / "convo" / entry.date / f"{entry.slug}.md"
    assert convo_path.exists()
    assert entry.metadata.get("recordType") == "convo"
    assert entry.metadata.get("requestedByUser") is True


def test_list_convo_entries_returns_saved_records(tmp_path):
    storage = Storage(tmp_path)
    first = storage.save_convo_record(content="첫번째")
    second = storage.save_convo_record(content="두번째")

    items = storage.list_convo_entries()

    slugs = {item.slug for item in items}
    assert first.slug in slugs
    assert second.slug in slugs
