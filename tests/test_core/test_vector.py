from datetime import datetime, timedelta, timezone

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


def test_has(tmp_path):
    store = VectorStore(persist_dir=tmp_path / "index")
    assert store.has("doc-1") is False

    store.add(doc_id="doc-1", content="Entry", metadata={"date": "2026-03-02", "slug": "entry"})
    assert store.has("doc-1") is True


def test_delete(tmp_path):
    store = VectorStore(persist_dir=tmp_path / "index")
    store.add(doc_id="doc-1", content="Entry", metadata={"date": "2026-03-02", "slug": "entry"})
    store.add(doc_id="doc-2", content="Entry 2", metadata={"date": "2026-03-02", "slug": "entry-2"})

    store.delete("doc-1")

    assert store.has("doc-1") is False
    assert store.has("doc-2") is True
    assert store.count() == 1


def test_hybrid_retrieval_uses_lexical_signal(tmp_path):
    store = VectorStore(persist_dir=tmp_path / "index")
    store.add(
        doc_id="doc-lexical",
        content="zebraquartz token appears here several times zebraquartz",
        metadata={"date": "2026-03-02", "slug": "lexical"},
    )
    store.add(
        doc_id="doc-generic",
        content="general notes about software architecture and APIs",
        metadata={"date": "2026-03-02", "slug": "generic"},
    )

    results = store.search("zebraquartz", n_results=1, hybrid=True, lexical_weight=0.9)
    assert results[0]["id"] == "doc-lexical"


def test_mmr_promotes_diversity(tmp_path):
    store = VectorStore(persist_dir=tmp_path / "index")
    store.add(
        doc_id="doc-a",
        content="python fastapi endpoint auth token refresh service",
        metadata={"date": "2026-03-02", "slug": "a"},
    )
    store.add(
        doc_id="doc-b",
        content="python fastapi endpoint auth token refresh implementation details",
        metadata={"date": "2026-03-02", "slug": "b"},
    )
    store.add(
        doc_id="doc-c",
        content="unreal material editor shading graph and blueprints",
        metadata={"date": "2026-03-02", "slug": "c"},
    )

    results = store.search("python auth token", n_results=2, mmr_lambda=0.2)
    ids = {item["id"] for item in results}
    assert "doc-a" in ids or "doc-b" in ids
    assert "doc-c" in ids


def test_temporal_decay_favors_recent_documents(tmp_path):
    store = VectorStore(persist_dir=tmp_path / "index")
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=365)).date().isoformat()
    recent = now.date().isoformat()

    content = "engine update checklist for deployment"
    store.add(doc_id="doc-old", content=content, metadata={"date": old, "slug": "old"})
    store.add(doc_id="doc-new", content=content, metadata={"date": recent, "slug": "new"})

    results = store.search("engine update checklist", n_results=1, recency_half_life_days=14)
    assert results[0]["id"] == "doc-new"


def test_search_uses_embedding_cache_for_repeat_queries(tmp_path, monkeypatch):
    store = VectorStore(persist_dir=tmp_path / "index")
    store.add(doc_id="doc-1", content="cache me if you can", metadata={"date": "2026-03-02", "slug": "cache"})

    original_query = store._collection.query
    calls = {"count": 0}

    def wrapped_query(*args, **kwargs):
        calls["count"] += 1
        return original_query(*args, **kwargs)

    monkeypatch.setattr(store._collection, "query", wrapped_query)

    first = store.search("cache", n_results=1)
    second = store.search("cache", n_results=1)

    assert first == second
    assert calls["count"] == 1
