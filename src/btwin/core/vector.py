"""Vector store for semantic search using ChromaDB."""

from pathlib import Path

import chromadb


class VectorStore:
    def __init__(self, persist_dir: Path) -> None:
        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._collection = self._client.get_or_create_collection(
            name="btwin_entries",
        )

    def add(self, doc_id: str, content: str, metadata: dict[str, str] | None = None) -> None:
        """Add or update a document in the vector store."""
        self._collection.upsert(
            ids=[doc_id],
            documents=[content],
            metadatas=[metadata] if metadata else None,
        )

    def search(
        self,
        query: str,
        n_results: int = 3,
        metadata_filters: dict[str, str] | None = None,
    ) -> list[dict]:
        """Search for similar documents with optional metadata filtering."""
        if self._collection.count() == 0:
            return []
        n_results = min(n_results, self._collection.count())

        query_args = {
            "query_texts": [query],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if metadata_filters:
            query_args["where"] = metadata_filters

        results = self._collection.query(**query_args)
        output = []
        for i, doc_id in enumerate(results["ids"][0]):
            output.append({
                "id": doc_id,
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i] if results["metadatas"] and results["metadatas"][0] else {},
                "distance": results["distances"][0][i] if results["distances"] else None,
            })
        return output

    def delete(self, doc_id: str) -> None:
        """Delete a document from the vector store by id."""
        self._collection.delete(ids=[doc_id])

    def has(self, doc_id: str) -> bool:
        """Return whether a document exists in the vector store."""
        result = self._collection.get(ids=[doc_id], include=[])
        return bool(result["ids"])

    def count(self) -> int:
        """Return the number of documents in the store."""
        return self._collection.count()
