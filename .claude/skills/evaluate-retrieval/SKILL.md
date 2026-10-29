---
name: evaluate-retrieval
description: Measure and compare Legal Atlas retrieval quality (hit@k, MRR) before and after a change to chunking, embeddings, BM25 tokenisation, fusion weights, or the corpus; diagnose failing questions. Use when the user asks whether retrieval got better or worse, wants to tune search, or changes retrieval code.
---

# Evaluate a retrieval change

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

- Always show before → after for hit@1, hit@3, hit@5, MRR@5 with the question count (currently 40).
  With 40 questions one question moves hit@k by 0.025 — call out changes that small as noise.
- The dev set is not held out. If you tuned `SEMANTIC_WEIGHT` or similar on it, say so and
  record the sweep (as in `reports/weight_tuning.json`) instead of reporting only the best value.
- Do not edit expected answers to make a change look better.
- Commit `reports/evaluation.json` together with the code change that produced it.
