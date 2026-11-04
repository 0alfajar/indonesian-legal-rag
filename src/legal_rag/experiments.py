"""Research experiments behind docs/technical_report.md; writes reports/experiments.json.

E1  Fusion-weight sweep on dev and test (test is reported, never used for selection).
E2  Leave-one-document-out cross-validation of the weight-selection procedure on dev:
    an estimate of how a tuned weight generalises to a regulation it was not tuned on.
E3  Ablations: heading context in passages (dense / BM25 / both) and the E5 query prefix.
E4  Lexical overlap between each question and its gold article, and how it relates to
    BM25 vs dense success — a check on how "easy" each question set is for lexical search.
E5  Error analysis of the served configuration (rank > 3 or not retrieved).
E6  Query latency of the served configuration on CPU.
"""

from datetime import datetime, timezone
from time import perf_counter

import numpy as np

from .config import MODEL, QUESTIONS, ROOT, SEMANTIC_WEIGHT, TEST_QUESTIONS
from .evaluation import check_targets, metrics, rank_of, run_config
from .pipeline.indexing import passage
from .retrieval import Retriever, tokenize
from .stats import holm, paired_permutation_test, per_question, spearman, summarize
from .storage import fingerprint, read_json, write_json

GRID = tuple(round(i / 10, 1) for i in range(11))
STOPWORDS = set("""yang dan di ke dari untuk dengan dalam pada atau apa apakah siapa kapan bagaimana berapa
mana bagi oleh sebagai adalah ini itu tersebut dapat harus jika saja telah akan tidak sudah karena serta""".split())


def ranks(rows: list[dict]) -> list[int | None]:
    return [row["rank"] for row in rows]


def sweep(retriever, questions, vectors) -> dict[float, list]:
    return {w: ranks(run_config(retriever, questions, vectors, "hybrid", semantic_weight=w)) for w in GRID}


def select_weight(sweep_ranks: dict[float, list], mask: np.ndarray) -> float:
    """Highest MRR@5 on the masked questions; ties go to the weight closest to the served one."""
    scores = {w: per_question(r)["mrr@5"][mask].mean() for w, r in sweep_ranks.items()}
    best = max(scores.values())
    return min((w for w, s in scores.items() if np.isclose(s, best)), key=lambda w: abs(w - SEMANTIC_WEIGHT))


def lodo_cv(questions: list[dict], sweep_ranks: dict[float, list]) -> dict:
    docs = np.array([q["expected_doc"] for q in questions])
    pooled: list = [None] * len(questions)
    folds = []
    for held_out in sorted(set(docs)):
        train, test = docs != held_out, docs == held_out
        weight = select_weight(sweep_ranks, train)
        for i in np.flatnonzero(test):
            pooled[i] = sweep_ranks[weight][i]
        folds.append({"held_out": held_out, "questions": int(test.sum()), "selected_weight": weight,
                      "train_mrr@5": float(per_question(sweep_ranks[weight])["mrr@5"][train].mean()),
                      "held_out_mrr@5": float(per_question(sweep_ranks[weight])["mrr@5"][test].mean())})
    in_sample = select_weight(sweep_ranks, np.ones(len(questions), bool))
    in_sample_mrr = metrics(sweep_ranks[in_sample])["mrr@5"]
    cv = summarize(pooled)
    return {"folds": folds, "cross_validated": cv, "full_dev_selected_weight": in_sample,
            "in_sample_best_mrr@5": in_sample_mrr,
            "optimism_mrr@5": in_sample_mrr - cv["mrr@5"]["mean"]}


def without_headings(retriever: Retriever, reencode: bool) -> Retriever:
    chunks = [{**c, "embedding_text": c["text"]} for c in retriever.chunks]
    if not reencode:  # BM25 loses headings, dense keeps the original vectors
        return Retriever(retriever.embeddings, chunks, retriever.model)
    vectors = retriever.model.encode([passage(c) for c in chunks], batch_size=16,
                                     convert_to_numpy=True, normalize_embeddings=True)
    return Retriever(vectors, chunks, retriever.model)


def lexical_overlap(question: str, article_text: str) -> float:
    q = {t for t in tokenize(question) if len(t) > 2 and t not in STOPWORDS}
    return len(q & set(tokenize(article_text))) / len(q) if q else 0.0


def error_analysis(retriever, questions, vectors, served_rows) -> list[dict]:
    articles = {}
    for c in retriever.chunks:
        articles.setdefault((c["doc_id"], str(c["pasal"])), []).append(c["text"])
    errors = []
    for question, vector, row in zip(questions, vectors, served_rows):
        if row["rank"] is not None and row["rank"] <= 3:
            continue
        deep = retriever.search(question["question"], top_k=20, query_vector=vector)
        top = deep[0]["chunk"]
        gold_text = " ".join(articles[(question["expected_doc"], str(question["expected_pasal"]))])
        top_text = " ".join(articles[(top["doc_id"], str(top["pasal"]))])
        errors.append({
            "id": question["id"], "question": question["question"],
            "gold": f'{question["expected_doc"]} Pasal {question["expected_pasal"]}',
            "rank@5": row["rank"], "rank@20": rank_of(deep, question),
            "top1": f'{top["doc_id"]} Pasal {top["pasal"]}',
            "wrong_document": top["doc_id"] != question["expected_doc"],
            "cross_reference": (f'Pasal {top["pasal"]} ' in gold_text + " "
                                or f'Pasal {question["expected_pasal"]} ' in top_text + " "),
            "gold_chunks": len(articles[(question["expected_doc"], str(question["expected_pasal"]))]),
        })
    return errors


def tested(variants: dict[str, list], reference: str) -> dict:
    base = per_question(variants[reference])["mrr@5"]
    tests = {n: paired_permutation_test(per_question(r)["mrr@5"], base)
             for n, r in variants.items() if n != reference}
    adjusted = holm({n: t["p_value"] for n, t in tests.items()})
    return {n: {"metrics": metrics(r), **({"vs_served": {**tests[n], "p_holm": adjusted[n]}}
                                          if n in tests else {})}
            for n, r in variants.items()}


def run_all(offline: bool = False) -> dict:
    retriever = Retriever.load(offline)
    splits = {"dev": read_json(QUESTIONS), "test": read_json(TEST_QUESTIONS)}
    for questions in splits.values():
        check_targets(retriever, questions)
    vectors = {s: retriever.encode_queries([q["question"] for q in qs]) for s, qs in splits.items()}
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "model": MODEL,
              "served_semantic_weight": SEMANTIC_WEIGHT,
              "dataset_sha256": {s: fingerprint(qs) for s, qs in splits.items()},
              "corpus_sha256": fingerprint(retriever.chunks)}

    print("E1/E2 weight sweep and cross-validation", flush=True)
    sweeps = {s: sweep(retriever, splits[s], vectors[s]) for s in splits}
    report["weight_sweep"] = {s: {str(w): metrics(r) for w, r in sw.items()} for s, sw in sweeps.items()}
    cv = lodo_cv(splits["dev"], sweeps["dev"])
    selected = cv["full_dev_selected_weight"]
    cv["selected_weight_on_test"] = summarize(sweeps["test"][selected])
    cv["served_weight_on_test"] = summarize(sweeps["test"][SEMANTIC_WEIGHT])
    report["weight_selection"] = cv

    print("E3 ablations (re-encodes the corpus without headings)", flush=True)
    bm25_plain = without_headings(retriever, reencode=False)
    all_plain = without_headings(retriever, reencode=True)
    dense_plain = Retriever(all_plain.embeddings, retriever.chunks, retriever.model)
    report["ablations"] = {}
    for s, questions in splits.items():
        no_prefix = retriever.model.encode([q["question"].strip() for q in questions], batch_size=16,
                                           convert_to_numpy=True, normalize_embeddings=True)
        variants = {
            "served (hybrid 0.7, headings, query prefix)": sweeps[s][SEMANTIC_WEIGHT],
            "- headings in BM25 text": ranks(run_config(bm25_plain, questions, vectors[s], "hybrid")),
            "- headings in dense passages": ranks(run_config(dense_plain, questions, vectors[s], "hybrid")),
            "- headings everywhere": ranks(run_config(all_plain, questions, vectors[s], "hybrid")),
            "- E5 'query: ' prefix": ranks(run_config(retriever, questions, no_prefix, "hybrid")),
            "dense only, - headings": ranks(run_config(all_plain, questions, vectors[s], "dense")),
            "BM25 only, - headings": ranks(run_config(all_plain, questions, vectors[s], "bm25")),
        }
        report["ablations"][s] = tested(variants, "served (hybrid 0.7, headings, query prefix)")

    print("E4 lexical overlap", flush=True)
    articles = {}
    for c in retriever.chunks:
        articles.setdefault((c["doc_id"], str(c["pasal"])), []).append(c["text"])
    report["lexical_overlap"] = {}
    for s, questions in splits.items():
        overlap = np.array([lexical_overlap(q["question"], " ".join(articles[(q["expected_doc"], str(q["expected_pasal"]))]))
                            for q in questions])
        bm25_rr = per_question(ranks(run_config(retriever, questions, vectors[s], "bm25")))["mrr@5"]
        dense_rr = per_question(ranks(run_config(retriever, questions, vectors[s], "dense")))["mrr@5"]
        report["lexical_overlap"][s] = {
            "mean": float(overlap.mean()), "median": float(np.median(overlap)),
            "spearman_with_bm25_rr": spearman(overlap, bm25_rr),
            "spearman_with_dense_rr": spearman(overlap, dense_rr),
            "per_question": {q["id"]: round(float(o), 3) for q, o in zip(questions, overlap)},
        }

    print("E5 error analysis", flush=True)
    report["errors"] = {s: error_analysis(retriever, splits[s], vectors[s],
                                          run_config(retriever, splits[s], vectors[s], "hybrid"))
                        for s in splits}

    print("E6 latency", flush=True)
    timings = []
    for question in splits["dev"] + splits["test"]:
        start = perf_counter()
        retriever.search(question["question"])        # includes query encoding
        timings.append((perf_counter() - start) * 1000)
    report["latency_ms"] = {"queries": len(timings), "p50": float(np.percentile(timings, 50)),
                            "p95": float(np.percentile(timings, 95)), "device": str(retriever.model.device),
                            "chunks": len(retriever.chunks)}

    write_json(ROOT / "reports" / "experiments.json", report)
    print("Wrote reports/experiments.json")
    return report
