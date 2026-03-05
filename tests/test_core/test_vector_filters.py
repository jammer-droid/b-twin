from btwin.config import BTwinConfig
from btwin.core.btwin import BTwin
from btwin.core.vector import VectorStore


def test_vector_search_filters_by_record_type(tmp_path):
    store = VectorStore(persist_dir=tmp_path / "index")
    store.add(
        doc_id="doc-collab",
        content="collab decision memo about handoff",
        metadata={"record_type": "collab", "slug": "collab-1", "date": "2026-03-05"},
    )
    store.add(
        doc_id="doc-convo",
        content="convo note about preferences",
        metadata={"record_type": "convo", "slug": "convo-1", "date": "2026-03-05"},
    )

    results = store.search("memo", n_results=5, metadata_filters={"record_type": "collab"})

    assert len(results) == 1
    assert results[0]["id"] == "doc-collab"


def test_btwin_search_passes_filters_to_vector_store(tmp_path):
    twin = BTwin(BTwinConfig(data_dir=tmp_path))
    twin.vector_store.add(
        doc_id="doc-entry",
        content="entry generic",
        metadata={"record_type": "entry", "slug": "entry-1", "date": "2026-03-05"},
    )
    twin.vector_store.add(
        doc_id="doc-convo",
        content="convo memory about meeting",
        metadata={"record_type": "convo", "slug": "convo-1", "date": "2026-03-05"},
    )

    results = twin.search("meeting", filters={"record_type": "convo"})

    assert len(results) == 1
    assert results[0]["id"] == "doc-convo"
