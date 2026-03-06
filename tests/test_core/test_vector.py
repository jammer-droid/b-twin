from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

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


# --- Issue 1: _lexical_scores only fetches candidate IDs ---


def test_lexical_scores_fetches_only_candidate_ids(tmp_path, monkeypatch):
    """_lexical_scores should call collection.get with explicit IDs, not fetch the entire collection."""
    store = VectorStore(persist_dir=tmp_path / "index")
    store.add(doc_id="doc-1", content="alpha bravo", metadata={"date": "2026-03-02", "slug": "a"})
    store.add(doc_id="doc-2", content="charlie delta", metadata={"date": "2026-03-02", "slug": "b"})
    store.add(doc_id="doc-3", content="echo foxtrot", metadata={"date": "2026-03-02", "slug": "c"})

    original_get = store._collection.get
    get_calls: list[dict] = []

    def tracking_get(*args, **kwargs):
        get_calls.append(kwargs)
        return original_get(*args, **kwargs)

    monkeypatch.setattr(store._collection, "get", tracking_get)

    # Only pass candidate IDs for doc-1 and doc-2
    scores = store._lexical_scores("alpha", ["doc-1", "doc-2"])

    assert len(get_calls) == 1
    assert "ids" in get_calls[0]
    assert set(get_calls[0]["ids"]) == {"doc-1", "doc-2"}
    # "where" should NOT be used since we pass explicit IDs
    assert "where" not in get_calls[0]
    # Only doc-1 should have a score since it contains "alpha"
    assert "doc-1" in scores
    assert "doc-3" not in scores


def test_lexical_scores_empty_candidate_ids(tmp_path):
    """_lexical_scores should return empty dict when candidate_ids is empty."""
    store = VectorStore(persist_dir=tmp_path / "index")
    store.add(doc_id="doc-1", content="alpha bravo", metadata={"date": "2026-03-02", "slug": "a"})
    scores = store._lexical_scores("alpha", [])
    assert scores == {}


# --- Issue 2: Cache eviction ---


def test_search_cache_evicts_oldest_entries(tmp_path, monkeypatch):
    """Cache should evict oldest entries when exceeding _SEARCH_CACHE_MAX."""
    store = VectorStore(persist_dir=tmp_path / "index")
    store.add(doc_id="doc-1", content="test content for cache", metadata={"date": "2026-03-02", "slug": "cache"})

    assert isinstance(store._search_cache, OrderedDict)

    # Lower the max to make the test practical
    monkeypatch.setattr(VectorStore, "_SEARCH_CACHE_MAX", 3)

    # Fill cache with 3 entries (at the limit)
    store.search("query one", n_results=1)
    store.search("query two", n_results=1)
    store.search("query three", n_results=1)
    assert len(store._search_cache) == 3

    # Record the first key before eviction
    first_key = next(iter(store._search_cache))

    # Add a 4th entry, which should evict the oldest
    store.search("query four", n_results=1)
    assert len(store._search_cache) == 3
    assert first_key not in store._search_cache


def test_search_cache_is_ordered_dict(tmp_path):
    """Cache should be an OrderedDict instance."""
    store = VectorStore(persist_dir=tmp_path / "index")
    assert isinstance(store._search_cache, OrderedDict)


# --- Issue 3: Recency regex flexibility ---


def test_recency_score_from_created_at_metadata():
    """_recency_score should use created_at metadata field as primary source."""
    today = datetime.now(timezone.utc).date().isoformat()
    score = VectorStore._recency_score({"created_at": today}, half_life_days=30.0)
    assert score > 0.9  # Today should be close to 1.0


def test_recency_score_from_date_metadata():
    """_recency_score should use date metadata field as fallback."""
    today = datetime.now(timezone.utc).date().isoformat()
    score = VectorStore._recency_score({"date": today}, half_life_days=30.0)
    assert score > 0.9


def test_recency_score_from_entries_path():
    """_recency_score should extract date from traditional entries/ path structure."""
    today = datetime.now(timezone.utc).date().isoformat()
    score = VectorStore._recency_score(
        {"path": f"entries/journal/{today}/note.md"}, half_life_days=30.0
    )
    assert score > 0.9


def test_recency_score_from_flat_path():
    """_recency_score should extract date from path without entries/ prefix."""
    today = datetime.now(timezone.utc).date().isoformat()
    score = VectorStore._recency_score(
        {"path": f"notes/{today}-my-note.md"}, half_life_days=30.0
    )
    assert score > 0.9


def test_recency_score_from_path_no_trailing_slash():
    """_recency_score should extract date from path without trailing slash after date."""
    today = datetime.now(timezone.utc).date().isoformat()
    score = VectorStore._recency_score(
        {"path": f"/data/{today}_report.txt"}, half_life_days=30.0
    )
    assert score > 0.9


def test_recency_score_from_deeply_nested_path():
    """_recency_score should extract date from deeply nested path."""
    today = datetime.now(timezone.utc).date().isoformat()
    score = VectorStore._recency_score(
        {"path": f"/a/b/c/d/{today}/e/f.md"}, half_life_days=30.0
    )
    assert score > 0.9


def test_recency_score_no_date_returns_one():
    """_recency_score should return 1.0 when no date is available."""
    score = VectorStore._recency_score({"path": "no-date-here.md"}, half_life_days=30.0)
    assert score == 1.0


def test_recency_score_old_date_decays():
    """_recency_score should decay for old dates."""
    old_date = (datetime.now(timezone.utc) - timedelta(days=365)).date().isoformat()
    score = VectorStore._recency_score({"date": old_date}, half_life_days=30.0)
    # After 365 days with 30-day half-life: 0.5^(365/30) ~ 0.00008
    assert score < 0.01


# --- Issue 4: MMR uses _relevance not _score ---


def test_mmr_select_uses_relevance_not_score(tmp_path):
    """_mmr_select should use _relevance (pure relevance) not _score (blended).

    The candidate with the higher _score (doc-b) has the LOWER _relevance,
    so old code (sorting by _score) and new code (sorting by _relevance)
    would pick different second candidates.  Fully disjoint vocabulary
    ensures Jaccard similarity is 0 and lambda=1.0 makes the test
    unambiguous.
    """
    store = VectorStore(persist_dir=tmp_path / "index")

    ranked = [
        {"id": "doc-a", "content": "alpha beta gamma", "_score": 0.9, "_relevance": 0.5, "_recency": 1.8},
        {"id": "doc-b", "content": "delta epsilon zeta", "_score": 0.8, "_relevance": 0.3, "_recency": 2.67},
        {"id": "doc-c", "content": "theta iota kappa", "_score": 0.4, "_relevance": 0.9, "_recency": 0.44},
    ]

    selected = store._mmr_select(ranked, n_results=2, mmr_lambda=1.0)
    # OLD code would pick [doc-a, doc-b] (by _score: 0.8 > 0.4)
    # NEW code picks [doc-a, doc-c] (by _relevance: 0.9 > 0.3)
    assert [item["id"] for item in selected] == ["doc-a", "doc-c"]
