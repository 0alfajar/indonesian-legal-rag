"""One retrieval implementation shared by CLI, demo, and evaluation."""

import re
import numpy as np
from rank_bm25 import BM25Okapi

from .config import MODEL, SEMANTIC_WEIGHT
from .indexing import load_index, load_model


def tokenize(text: str) -> list[str]:
    return re.findall(r"\b\w+\b", text.lower())


def normalize(scores: np.ndarray) -> np.ndarray:
    spread = np.ptp(scores)
    return (scores - scores.min()) / spread if spread else np.zeros_like(scores)


class Retriever:
    def __init__(self, embeddings: np.ndarray, chunks: list[dict], model):
        if not chunks or len(chunks) != len(embeddings):
            raise ValueError("A nonempty index with matching chunks is required")
        self.embeddings = embeddings
        self.chunks = chunks
        self.model = model
        self.bm25 = BM25Okapi([tokenize(chunk["embedding_text"]) for chunk in chunks])

    @classmethod
    def load(cls, offline: bool = False):
        embeddings, metadata = load_index()
        if metadata["model_name"] != MODEL:
            raise ValueError("Configured query model differs from the index model")
        return cls(embeddings, metadata["chunks"], load_model(offline))

    def encode_queries(self, queries: list[str]) -> np.ndarray:
        return self.model.encode(
            ["query: " + query.strip() for query in queries], batch_size=16,
            convert_to_numpy=True, normalize_embeddings=True,
        )

    def search(self, query: str, top_k: int = 5, method: str = "hybrid",
               unique_articles: bool = True, doc_id: str | None = None,
               pasal: str | None = None, query_vector=None,
               semantic_weight: float = SEMANTIC_WEIGHT) -> list[dict]:
        if not query.strip():
            raise ValueError("Question cannot be empty")
        if not 1 <= top_k <= 100:
            raise ValueError("top_k must be between 1 and 100")
        if method not in {"dense", "bm25", "hybrid", "rrf"}:
            raise ValueError(f"Unknown retrieval method: {method}")
        if not 0 <= semantic_weight <= 1:
            raise ValueError("semantic_weight must be between 0 and 1")
        candidates = np.array([
            i for i, chunk in enumerate(self.chunks)
            if (doc_id is None or chunk["doc_id"] == doc_id)
            and (pasal is None or str(chunk["pasal"]).upper() == str(pasal).upper())
        ], dtype=int)
        if not len(candidates):
            return []
        if method == "bm25":
            dense = np.zeros(len(candidates))
        else:
            vector = self.encode_queries([query])[0] if query_vector is None else query_vector
            dense = self.embeddings[candidates] @ vector
        sparse = np.asarray(self.bm25.get_scores(tokenize(query)))[candidates]
        if method == "dense":
            scores = dense
        elif method == "bm25":
            scores = sparse
        elif method == "hybrid":
            scores = semantic_weight * normalize(dense) + (1 - semantic_weight) * normalize(sparse)
        else:
            scores = np.zeros(len(candidates))
            for component in (dense, sparse):
                if np.ptp(component):
                    order = np.argsort(-component, kind="stable")
                    scores[order] += 1 / (60 + np.arange(1, len(order) + 1))
        results, seen = [], set()
        for local in np.argsort(-scores, kind="stable"):
            chunk = self.chunks[int(candidates[local])]
            article = (chunk["doc_id"], chunk["pasal"])
            if unique_articles and article in seen:
                continue
            if method == "bm25" and scores[local] <= 0:
                continue
            seen.add(article)
            results.append({
                "rank": len(results) + 1, "score": float(scores[local]),
                "dense_score": float(dense[local]), "bm25_score": float(sparse[local]),
                "chunk": chunk,
            })
            if len(results) == top_k:
                break
        return results

    def evidence(self, results: list[dict], max_chars: int = 24000) -> list[dict]:
        """Reserve space for every retrieved hit, then add neighboring ayat.

        Expanding within the same article prevents an isolated paragraph from
        hiding an adjacent condition. Each passage keeps its own citation ID.
        """
        selected, seen, used = [], set(), 0
        primary = [row["chunk"] for row in results]
        articles = {(chunk["doc_id"], chunk["pasal"]) for chunk in primary}
        neighbors = [c for c in self.chunks if (c["doc_id"], c["pasal"]) in articles]
        for chunk in primary + neighbors:
            if chunk["chunk_id"] in seen or used + len(chunk["text"]) > max_chars:
                continue
            seen.add(chunk["chunk_id"])
            used += len(chunk["text"])
            selected.append({"source_id": f"S{len(selected) + 1}", **chunk})
        return selected
