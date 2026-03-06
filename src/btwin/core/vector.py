"""Vector store for semantic search using ChromaDB."""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import chromadb


class VectorStore:
    def __init__(self, persist_dir: Path) -> None:
        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._collection = self._client.get_or_create_collection(
            name="btwin_entries",
        )
        self._search_cache: dict[tuple[Any, ...], list[dict[str, Any]]] = {}

    def add(self, doc_id: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        """Add or update a document in the vector store."""
        self._collection.upsert(
            ids=[doc_id],
            documents=[content],
            metadatas=[metadata] if metadata else None,
        )
        self._search_cache.clear()

    def search(
        self,
        query: str,
        n_results: int = 3,
        metadata_filters: dict[str, str] | None = None,
        *,
        hybrid: bool = True,
        lexical_weight: float = 0.4,
        recency_half_life_days: float = 30.0,
        mmr_lambda: float = 0.75,
        candidate_multiplier: int = 4,
    ) -> list[dict]:
        """Search for similar documents with optional metadata filtering.

        Args:
            query: Search query.
            n_results: Number of final results.
            metadata_filters: Chroma where-filter.
            hybrid: If true, blend vector and lexical relevance.
            lexical_weight: Blend weight for lexical score (0.0-1.0).
            recency_half_life_days: Exponential half-life for temporal boosting.
            mmr_lambda: Relevance/diversity tradeoff for MMR (0.0-1.0).
            candidate_multiplier: Candidate pool size multiplier before reranking.
        """
        if self._collection.count() == 0:
            return []

        n_results = max(1, min(n_results, self._collection.count()))
        lexical_weight = min(1.0, max(0.0, lexical_weight))
        mmr_lambda = min(1.0, max(0.0, mmr_lambda))
        candidate_multiplier = max(1, candidate_multiplier)

        cache_key = (
            query,
            n_results,
            tuple(sorted((metadata_filters or {}).items())),
            hybrid,
            round(lexical_weight, 4),
            round(recency_half_life_days, 4),
            round(mmr_lambda, 4),
            candidate_multiplier,
        )
        cached = self._search_cache.get(cache_key)
        if cached is not None:
            return [dict(item) for item in cached]

        vector_candidates = self._vector_candidates(
            query=query,
            n_results=n_results * candidate_multiplier,
            metadata_filters=metadata_filters,
        )
        if not vector_candidates:
            return []

        lexical_scores = self._lexical_scores(query, metadata_filters)

        scored: list[dict[str, Any]] = []
        for item in vector_candidates:
            vector_score = self._distance_to_similarity(item.get("distance"))
            lexical_score = lexical_scores.get(item["id"], 0.0)
            relevance = vector_score
            if hybrid:
                relevance = (1.0 - lexical_weight) * vector_score + lexical_weight * lexical_score

            recency = self._recency_score(item.get("metadata") or {}, recency_half_life_days)
            total_score = relevance * recency

            enriched = dict(item)
            enriched.update(
                {
                    "_score": total_score,
                    "_relevance": relevance,
                    "_recency": recency,
                }
            )
            scored.append(enriched)

        ranked = sorted(scored, key=lambda x: x["_score"], reverse=True)
        selected = self._mmr_select(ranked, n_results=n_results, mmr_lambda=mmr_lambda)

        output: list[dict[str, Any]] = []
        for item in selected:
            payload = {
                "id": item["id"],
                "content": item["content"],
                "metadata": item.get("metadata") or {},
                "distance": item.get("distance"),
            }
            output.append(payload)

        self._search_cache[cache_key] = [dict(item) for item in output]
        return output

    def delete(self, doc_id: str) -> None:
        """Delete a document by id if present."""
        self._collection.delete(ids=[doc_id])
        self._search_cache.clear()

    def has(self, doc_id: str) -> bool:
        """Check whether a document id exists in the store."""
        result = self._collection.get(ids=[doc_id], include=[])
        return bool(result.get("ids"))

    def count(self) -> int:
        """Return the number of documents in the store."""
        return self._collection.count()

    def list_ids(self) -> set[str]:
        """Return all document ids currently stored in vectors."""
        result = self._collection.get(include=[])
        ids = result.get("ids") or []
        return set(ids)

    def _vector_candidates(
        self,
        query: str,
        n_results: int,
        metadata_filters: dict[str, str] | None,
    ) -> list[dict[str, Any]]:
        n_results = min(n_results, self._collection.count())
        query_args: dict[str, Any] = {
            "query_texts": [query],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if metadata_filters:
            query_args["where"] = metadata_filters

        results = self._collection.query(**query_args)
        output = []
        for i, doc_id in enumerate(results["ids"][0]):
            output.append(
                {
                    "id": doc_id,
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] if results["metadatas"] and results["metadatas"][0] else {},
                    "distance": results["distances"][0][i] if results["distances"] else None,
                }
            )
        return output

    def _lexical_scores(self, query: str, metadata_filters: dict[str, str] | None) -> dict[str, float]:
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return {}

        get_args: dict[str, Any] = {"include": ["documents", "metadatas"]}
        if metadata_filters:
            get_args["where"] = metadata_filters
        all_docs = self._collection.get(**get_args)

        ids = all_docs.get("ids") or []
        docs = all_docs.get("documents") or []

        scores: dict[str, float] = {}
        for i, doc_id in enumerate(ids):
            content = docs[i] if i < len(docs) else ""
            tokens = self._tokenize(content)
            if not tokens:
                continue
            overlap = len(query_tokens & tokens)
            score = overlap / len(query_tokens)
            if score > 0:
                scores[doc_id] = score
        return scores

    @staticmethod
    def _distance_to_similarity(distance: float | None) -> float:
        if distance is None:
            return 0.0
        return 1.0 / (1.0 + max(0.0, float(distance)))

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {token for token in re.findall(r"[a-zA-Z0-9가-힣]+", text.lower()) if len(token) > 1}

    @staticmethod
    def _recency_score(metadata: dict[str, Any], half_life_days: float) -> float:
        if half_life_days <= 0:
            return 1.0

        candidate = metadata.get("created_at") or metadata.get("date")
        if not candidate:
            path = str(metadata.get("path") or "")
            match = re.search(r"entries(?:/[^/]+)?/(\d{4}-\d{2}-\d{2})/", path)
            if match:
                candidate = match.group(1)
        if not candidate:
            return 1.0

        dt = VectorStore._parse_datetime(str(candidate))
        if dt is None:
            return 1.0

        now = datetime.now(timezone.utc)
        age_days = max(0.0, (now - dt).total_seconds() / 86400.0)
        return 0.5 ** (age_days / half_life_days)

    @staticmethod
    def _parse_datetime(raw: str) -> datetime | None:
        if not raw:
            return None

        try:
            if "T" in raw:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            else:
                dt = datetime.strptime(raw, "%Y-%m-%d")
                dt = dt.replace(tzinfo=timezone.utc)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            return None

    def _mmr_select(self, ranked: list[dict[str, Any]], n_results: int, mmr_lambda: float) -> list[dict[str, Any]]:
        if len(ranked) <= n_results:
            return ranked

        selected: list[dict[str, Any]] = []
        remaining = ranked.copy()

        while remaining and len(selected) < n_results:
            if not selected:
                selected.append(remaining.pop(0))
                continue

            best_idx = 0
            best_score = -math.inf
            for idx, candidate in enumerate(remaining):
                relevance = candidate.get("_score", 0.0)
                max_similarity = max(
                    self._content_similarity(candidate.get("content", ""), chosen.get("content", ""))
                    for chosen in selected
                )
                mmr_score = (mmr_lambda * relevance) - ((1.0 - mmr_lambda) * max_similarity)
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = idx

            selected.append(remaining.pop(best_idx))

        return selected

    @staticmethod
    def _content_similarity(a: str, b: str) -> float:
        a_tokens = VectorStore._tokenize(a)
        b_tokens = VectorStore._tokenize(b)
        if not a_tokens or not b_tokens:
            return 0.0
        union = a_tokens | b_tokens
        if not union:
            return 0.0
        return len(a_tokens & b_tokens) / len(union)
