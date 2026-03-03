from btwin.core.vector import VectorStore


def test_add_and_search(tmp_path):
    store = VectorStore(persist_dir=tmp_path / "index")
    store.add(
        doc_id="doc-1",
        content="I studied Unreal Material Editor today. Node-based shading is similar to Frostbite VP.",
        metadata={"date": "2026-03-02", "slug": "unreal-study"},
    )
    store.add(
        doc_id="doc-2",
        content="Python is great for building web APIs with FastAPI.",
        metadata={"date": "2026-03-02", "slug": "python-api"},
    )
    results = store.search("Unreal shader material", n_results=1)
    assert len(results) == 1
    assert results[0]["id"] == "doc-1"
    assert "Unreal" in results[0]["content"]


def test_search_empty_store(tmp_path):
    store = VectorStore(persist_dir=tmp_path / "index")
    results = store.search("anything", n_results=5)
    assert results == []


def test_upsert(tmp_path):
    store = VectorStore(persist_dir=tmp_path / "index")
    store.add(doc_id="doc-1", content="Original content", metadata={"date": "2026-03-02", "slug": "test"})
    store.add(doc_id="doc-1", content="Updated content", metadata={"date": "2026-03-02", "slug": "test"})
    results = store.search("Updated content", n_results=1)
    assert len(results) == 1
    assert "Updated" in results[0]["content"]


def test_count(tmp_path):
    store = VectorStore(persist_dir=tmp_path / "index")
    assert store.count() == 0
    store.add(doc_id="doc-1", content="First entry", metadata={"date": "2026-03-02", "slug": "first"})
    assert store.count() == 1
