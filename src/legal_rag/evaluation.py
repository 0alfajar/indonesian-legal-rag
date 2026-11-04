"""Reproducible article-level retrieval evaluation with uncertainty; no Gemini calls."""

from datetime import datetime, timezone
from time import perf_counter

from .config import MODEL, QUESTIONS, ROOT, SEMANTIC_WEIGHT
from .retrieval import Retriever
from .stats import holm, paired_permutation_test, per_question, summarize
from .storage import fingerprint, read_json, write_json

# (run name, method, deduplicate to one hit per article). hybrid_articles is what the demo serves.
CONFIGS = (("dense_chunks", "dense", False), ("hybrid_chunks", "hybrid", False),
           ("dense_articles", "dense", True), ("bm25_articles", "bm25", True),
           ("hybrid_articles", "hybrid", True), ("rrf_articles", "rrf", True))
SERVED = "hybrid_articles"
BASELINES = ("dense_articles", "bm25_articles", "rrf_articles")


def metrics(ranks: list[int | None]) -> dict:
    return {name: float(values.mean()) for name, values in per_question(ranks).items()}


def rank_of(results: list[dict], question: dict) -> int | None:
    return next((r["rank"] for r in results
                 if r["chunk"]["doc_id"] == question["expected_doc"]
                 and str(r["chunk"]["pasal"]) == str(question["expected_pasal"])), None)


def check_targets(retriever: Retriever, questions: list[dict]) -> None:
    targets = {(c["doc_id"], str(c["pasal"])) for c in retriever.chunks}
    missing = [q["id"] for q in questions if (q["expected_doc"], str(q["expected_pasal"])) not in targets]
    if missing:
        raise ValueError(f"Evaluation targets missing from the corpus: {missing}")


def run_config(retriever: Retriever, questions: list[dict], vectors, method: str,
               unique: bool = True, top_k: int = 5, **options) -> list[dict]:
    rows = []
    for question, vector in zip(questions, vectors):
        results = retriever.search(question["question"], top_k=top_k, method=method,
                                   unique_articles=unique, query_vector=vector, **options)
        rows.append({**question, "rank": rank_of(results, question),
                     "retrieved": [{"doc_id": r["chunk"]["doc_id"], "pasal": r["chunk"]["pasal"],
                                    "chunk_id": r["chunk"]["chunk_id"]} for r in results]})
    return rows


def compare(runs: dict, served: str = SERVED, baselines=BASELINES, metric: str = "mrr@5") -> dict:
    """Paired tests of the served configuration against each baseline, Holm-corrected."""
    target = per_question([r["rank"] for r in runs[served]["results"]])[metric]
    tests = {name: paired_permutation_test(
        target, per_question([r["rank"] for r in runs[name]["results"]])[metric])
        for name in baselines}
    adjusted = holm({name: t["p_value"] for name, t in tests.items()})
    return {name: {**t, "p_holm": adjusted[name]} for name, t in tests.items()}


def by_document(rows: list[dict]) -> dict:
    documents = sorted({r["expected_doc"] for r in rows})
    return {doc: {"questions": sum(r["expected_doc"] == doc for r in rows),
                  **metrics([r["rank"] for r in rows if r["expected_doc"] == doc])}
            for doc in documents}


def evaluate(offline: bool = False, questions_path=QUESTIONS, output=None) -> dict:
    questions = read_json(questions_path)
    retriever = Retriever.load(offline)
    check_targets(retriever, questions)
    start = perf_counter()
    vectors = retriever.encode_queries([q["question"] for q in questions])
    query_seconds = perf_counter() - start
    runs = {}
    for name, method, unique in CONFIGS:
        rows = run_config(retriever, questions, vectors, method, unique)
        ranks = [r["rank"] for r in rows]
        runs[name] = {"metrics": metrics(ranks), "ci95": {k: v["ci95"] for k, v in summarize(ranks).items()},
                      "by_document": by_document(rows), "results": rows}
        print(name, {k: round(v, 3) for k, v in runs[name]["metrics"].items()}, flush=True)
    comparisons = compare(runs)
    for name, test in comparisons.items():
        print(f"{SERVED} vs {name}: dMRR@5 {test['mean_difference']:+.3f} "
              f"95% CI [{test['ci95'][0]:+.3f}, {test['ci95'][1]:+.3f}] p_holm={test['p_holm']:.3f}")
    split = "dev" if questions_path.stem == "dev" else questions_path.stem
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset": (questions_path.relative_to(ROOT).as_posix() if questions_path.is_relative_to(ROOT)
                    else questions_path.name),
        "split": split,
        "dataset_sha256": fingerprint(questions), "corpus_sha256": fingerprint(retriever.chunks),
        "model": MODEL, "query_prefix": "query: ", "semantic_weight": SEMANTIC_WEIGHT,
        "questions": len(questions), "query_encoding_seconds": query_seconds,
        "evaluation_level": ("document + article; dev questions were written alongside development and used "
                             "for tuning" if split == "dev" else
                             "document + article; held-out set frozen before evaluation, see "
                             "data/evaluation/README.md"),
        "statistics": {"ci": "95% percentile bootstrap, 10,000 resamples, seed 0",
                       "comparison": f"{SERVED} vs baselines on per-question RR@5; paired sign-flip "
                                     "permutation test, 10,000 permutations, seed 0; Holm-corrected"},
        "comparisons": comparisons,
        "runs": runs,
    }
    output = output or ROOT / "reports" / ("evaluation.json" if split == "dev" else f"evaluation_{split}.json")
    write_json(output, report)
    return report
