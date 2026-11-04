---
name: evaluate-retrieval
description: Measure and compare Legal Atlas retrieval quality (hit@k, MRR) before and after a change to chunking, embeddings, BM25 tokenisation, fusion weights, or the corpus; diagnose failing questions. Use when the user asks whether retrieval got better or worse, wants to tune search, or changes retrieval code.
---

# Evaluate a retrieval change

## Two question sets — never tune on test

- `data/evaluation/dev.json` (`legal-rag evaluate`) — the development set. Tune and debug here.
- `data/evaluation/test.json` (`legal-rag evaluate --split test`) — held out, frozen and
  pre-registered in `data/evaluation/README.md`. Run it only after a change is final, report the
  result whatever it is, and never pick a setting because it scores better on test. A test in
  `tests/test_stats.py` fails if the file is edited.
- `legal-rag experiments` reruns the weight sweep, leave-one-document-out CV, ablations, overlap
  analysis, error analysis and latency → `reports/experiments.json` (~5 min on CPU, re-encodes the
  corpus once). Update `docs/technical_report.md` when its numbers change.

## Baseline first

`reports/evaluation.json` is overwritten by every run, so save the baseline before touching code:

```bash
git stash            # or check out the base commit
legal-rag evaluate && cp reports/evaluation.json "$TMPDIR/eval_before.json"
git stash pop
legal-rag evaluate
```

If the change affects chunks or embeddings, run `legal-rag ingest` and/or `legal-rag index`
before the second evaluation, otherwise the loader rejects the stale index.

## Compare

```python
import json, os
before = json.load(open(os.path.join(os.environ.get("TMPDIR", "."), "eval_before.json"), encoding="utf-8"))
after = json.load(open("reports/evaluation.json", encoding="utf-8"))
assert before["dataset_sha256"] == after["dataset_sha256"], "different question sets"
for run in after["runs"]:
    b, a = before["runs"][run]["metrics"], after["runs"][run]["metrics"]
    print(f"{run:16}", "  ".join(f"{k} {b[k]:.3f}→{a[k]:.3f}" for k in a))
```

Each report also carries 95 % bootstrap intervals (`ci95`) and Holm-corrected paired tests of
the served configuration against each baseline (`comparisons`). A change whose before/after
difference sits inside the interval is not evidence of improvement; for a paired before/after
test use `legal_rag.stats.paired_permutation_test` on `per_question(ranks)["mrr@5"]`.

`hybrid_articles` is the configuration the demo serves; the others are baselines.

## Diagnose failures

For each question where `rank` is `null` or > 3 in `hybrid_articles`, look at `retrieved` and
classify:

- **Wrong article, same topic** — often a definition article (Pasal 1) outranking the substantive
  one; consider heading context or BM25 weighting.
- **Right article, ranked low** — try `legal-rag search "<question>" --method dense` and
  `--method bm25` to see which signal fails.
- **Target split across chunks** — chunking issue; check `chunk_id`s for the target Pasal.
- **Question ambiguous or label wrong** — fix the dataset in a separate commit and say so.

## Reporting rules

- Always show before → after for hit@1, hit@3, hit@5, MRR@5 with the question count (currently 40
  per split) and the 95 % CI. One question moves hit@k by 0.025 — call changes that small noise.
- The dev set is not held out. If you tuned `SEMANTIC_WEIGHT` or similar on it, say so and
  record the sweep (`weight_sweep` in `reports/experiments.json`) instead of only the best value.
- Do not edit expected answers to make a change look better.
- Commit `reports/evaluation.json` together with the code change that produced it.
