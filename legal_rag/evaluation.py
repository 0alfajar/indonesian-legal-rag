"""Reproducible article-level retrieval evaluation; no Gemini calls."""

from datetime import datetime, timezone
from time import perf_counter

from .config import MODEL, QUESTIONS, ROOT, SEMANTIC_WEIGHT
from .retrieval import Retriever
from .storage import fingerprint, read_json, write_json


def metrics(ranks: list[int | None]) -> dict:
    if not ranks:
        raise ValueError("Evaluation needs at least one question")
    return {
        **{f"hit@{k}": sum(r is not None and r <= k for r in ranks) / len(ranks) for k in (1, 3, 5)},
        "mrr@5": sum(1 / r for r in ranks if r is not None and r <= 5) / len(ranks),
    }


def evaluate(offline: bool = False, questions_path=QUESTIONS) -> dict:
    questions = read_json(questions_path)
    retriever = Retriever.load(offline)
    targets = {(c["doc_id"], str(c["pasal"])) for c in retriever.chunks}
    missing = [q["id"] for q in questions if (q["expected_doc"], str(q["expected_pasal"])) not in targets]
    if missing:
        raise ValueError(f"Evaluation targets missing from the corpus: {missing}")
    start = perf_counter()
    vectors = retriever.encode_queries([q["question"] for q in questions])
    query_seconds = perf_counter() - start
    runs = {}
    for method, unique in (("dense", False), ("hybrid", False), ("dense", True),
                           ("bm25", True), ("hybrid", True), ("rrf", True)):
        name = method + ("_articles" if unique else "_chunks")
        rows = []
        for question, vector in zip(questions, vectors):
            results = retriever.search(question["question"], method=method,
                                       unique_articles=unique, query_vector=vector)
            rank = next((r["rank"] for r in results
                         if r["chunk"]["doc_id"] == question["expected_doc"]
                         and str(r["chunk"]["pasal"]) == str(question["expected_pasal"])), None)
            rows.append({**question, "rank": rank,
                         "retrieved": [{"doc_id": r["chunk"]["doc_id"],
                                        "pasal": r["chunk"]["pasal"],
                                        "chunk_id": r["chunk"]["chunk_id"]} for r in results]})
        runs[name] = {"metrics": metrics([r["rank"] for r in rows]), "results": rows}
        print(name, runs[name]["metrics"], flush=True)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(questions_path.relative_to(ROOT)) if questions_path.is_relative_to(ROOT) else questions_path.name,
        "dataset_sha256": fingerprint(questions), "corpus_sha256": fingerprint(retriever.chunks),
        "model": MODEL, "query_prefix": "query: ", "semantic_weight": SEMANTIC_WEIGHT,
        "questions": len(questions), "query_encoding_seconds": query_seconds,
        "evaluation_level": "document + article; original questions are a development set, not held-out evidence",
        "runs": runs,
    }
    write_json(ROOT / "reports" / "evaluation.json", report)
    return report
