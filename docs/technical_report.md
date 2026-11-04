# Legal Atlas: Hybrid Retrieval for Indonesian Regulations — Technical Report

*Version 0.3 · 2026-11-04 · all numbers regenerate with `legal-rag evaluate [--split test]` and
`legal-rag experiments`; raw outputs in `reports/`.*

## Abstract

We study article-level retrieval for question answering over three Indonesian government
regulations (658 articles, 1,814 ayat-level passages). We compare BM25, a multilingual dense
retriever (`intfloat/multilingual-e5-base`), reciprocal-rank fusion, and weighted min-max fusion,
on a 40-question development set and a 40-question held-out test set whose articles were drawn at
random and whose analysis plan was recorded before the first test run. On the test set the served
hybrid (0.7 dense / 0.3 BM25) reaches **MRR@5 0.822 [95 % CI 0.714–0.917]** and **hit@5 0.925**.
Hybrid beats dense-only retrieval significantly (+0.155 MRR@5, Holm-adjusted p = 0.006) but is
**not** distinguishable from BM25 alone (+0.045, p = 0.33). Fusion-weight selection is unstable
across documents yet inconsequential within 0.4–0.7, and a heading-context ablation that looked
helpful on dev did not replicate on test. All residual errors confuse the gold article with a
neighbouring article of the same regulation, which motivates a cross-encoder reranker as the next
step.

## 1. Problem and research questions

Legal answers must be traceable to a specific Pasal (article) and ayat (paragraph). The system
therefore treats retrieval of the right article as the primary measurable property and constrains
generation to cite only retrieved passages (§7).

- **RQ1** Does fusing lexical and dense signals beat either signal alone for Indonesian statutory text?
- **RQ2** How much of the reported quality is an artefact of tuning on the evaluation questions?
- **RQ3** Which design choices (heading context, query prefix, fusion weight) actually matter?
- **RQ4** What kinds of errors remain?

## 2. Corpus and preprocessing

| Regulation | Topic | Articles | Passages |
|---|---|---:|---:|
| PP 5/2021 | Risk-based business licensing | 567 | 1,570 |
| PP 35/2021 | Fixed-term contracts, working time, termination | 66 | 164 |
| PP 51/2023 | Minimum wage (amends PP 36/2021) | 25 | 80 |

PDFs are converted with Docling; a rule-based parser rebuilds BAB → Bagian → Paragraf → Pasal →
ayat, repairs ayat markers Docling places at the end of list items, separates the *Penjelasan*
(explanatory memorandum) and amendment instructions, and refuses to continue on duplicate or empty
articles (`reports/ingestion.json`). Each ayat becomes a passage (split at sentence boundaries above
1,600 characters); the text that is embedded and BM25-indexed is prefixed with its heading path
(document, BAB, Pasal, ayat). UU 6/2023 (1,127 pages) is excluded pending an extraction review.

Known data-quality issues, visible in the sampled test articles: OCR confusions in PP 35/2021 and
PP 51/2023 (`kabupatenlkota` for *kabupaten/kota*, `lOOo/o` for *100 %*, `tu3uh` for *tujuh*), and
amendment instructions of PP 51/2023 that still leak into the preceding article's text. Both
degrade lexical matching and are not corrected in this version.

## 3. Retrieval methods

All methods score every passage, then keep the best passage per article (article deduplication),
returning the top 5 articles.

- **BM25** — Okapi BM25 (`rank-bm25`, default k1/b), lower-cased `\w+` tokens, no stemming.
- **Dense** — E5-base cosine similarity with the model's `query:` / `passage:` prefixes.
- **RRF** — reciprocal-rank fusion, k = 60.
- **Hybrid (served)** — `w · minmax(dense) + (1 − w) · minmax(bm25)`, w = 0.7.

## 4. Evaluation protocol

**Task.** Given a question, retrieve the single gold article. hit@k = gold in top k; MRR@5 =
reciprocal rank, 0 beyond rank 5. MRR@5 is the primary metric.

**Data** (details in [`data/evaluation/README.md`](../data/evaluation/README.md)).
*Dev* — 40 questions written during development, concentrated on opening articles (e.g. PP 5/2021
Pasal 2–22), used for debugging and for choosing w. *Test* — 40 articles sampled with a fixed seed
from all eligible articles (excluding dev targets, Pasal 1, and stubs < 150 chars), one question
written per article from its text alone without running retrieval, file hash and analysis plan
recorded before the first evaluation; a unit test fails if the file changes.

**Statistics.** 95 % percentile bootstrap intervals (10k resamples). Systems are compared on the
same questions with a paired sign-flip permutation test on per-question RR@5 (10k permutations),
Holm–Bonferroni across the three comparisons against the served system. With n = 40 one question
is 0.025 of hit@k; intervals are ±0.10–0.15, so only large differences are detectable.

**Pre-registered hypotheses.** H1 hybrid > BM25; H2 hybrid > dense; H3 test MRR@5 < dev MRR@5.

## 5. Results

### 5.1 Main comparison (RQ1)

| Method | Dev MRR@5 | Dev hit@5 | **Test MRR@5** | **Test hit@1** | **Test hit@5** |
|---|---:|---:|---:|---:|---:|
| BM25 | 0.594 [0.47, 0.72] | 0.825 | 0.777 [0.67, 0.88] | 0.675 | 0.950 |
| Dense (E5) | 0.671 [0.54, 0.80] | 0.800 | 0.667 [0.55, 0.78] | 0.525 | 0.875 |
| RRF | 0.700 [0.58, 0.81] | 0.875 | 0.771 [0.66, 0.88] | 0.675 | 0.925 |
| **Hybrid 0.7** | **0.733** [0.62, 0.84] | **0.925** | **0.822** [0.71, 0.92] | **0.750** | 0.925 |

Paired tests, hybrid minus baseline, ΔMRR@5 [95 % CI], Holm-adjusted p (wins/losses):

| vs | Dev | Test |
|---|---|---|
| Dense | +0.062 [−0.03, +0.16], p = 0.42 (9/4) | **+0.155 [+0.07, +0.25], p = 0.006 (12/3)** |
| BM25 | +0.139 [+0.01, +0.28], p = 0.16 (16/7) | +0.045 [−0.04, +0.13], p = 0.33 (8/5) |
| RRF | +0.033 [−0.02, +0.08], p = 0.42 (7/2) | +0.051 [+0.01, +0.10], p = 0.07 (7/2) |

**H2 is supported**: adding BM25 to the dense retriever helps on held-out questions. **H1 is not**:
on neither split is hybrid significantly better than BM25 alone, and the two baselines swap places
between splits (dense ahead on dev, BM25 ahead on test). The defensible claim is that hybrid is
never worse than the better single signal and removes the need to know in advance which one that
is — not that it dominates BM25.

### 5.2 Is the dev set optimistic? (RQ2)

**H3 is not supported.** Test MRR@5 (0.822) is *higher* than dev (0.733), though the intervals
overlap heavily. Two candidate explanations were checked post hoc and neither holds: mean
question–article token overlap is the same on both sets (0.737 vs 0.755, E4) and so is mean query
IDF (2.99 vs 3.14). The gap is concentrated in PP 51/2023 (0.583 → 0.783, n = 10 each), where the
dev questions target near-duplicate wage-setting articles; given the sample sizes we read it as
noise plus question-difficulty differences, not as evidence that the system generalises better than
measured.

The *weight* was tuned on dev, and that does carry optimism. Leave-one-document-out
cross-validation (choose w on two regulations, score the third) gives:

| | MRR@5 |
|---|---:|
| Best w on all of dev (w = 0.5), in-sample | 0.761 |
| Cross-validated estimate of the same procedure | 0.698 [0.58, 0.81] |
| **Optimism of in-sample tuning** | **0.063** |

The folds select w = 0.5, 0.4 and 0.7 — the optimum is not stable across regulations.

### 5.3 Fusion weight (RQ3)

MRR@5 by w (0 = BM25 ranking, 1 = dense ranking), article-deduplicated:

| w | 0.0 | 0.2 | 0.3 | 0.4 | 0.5 | 0.6 | **0.7** | 0.8 | 1.0 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Dev | 0.594 | 0.635 | 0.677 | 0.727 | 0.761 | 0.720 | 0.733 | 0.730 | 0.671 |
| Test | 0.777 | 0.790 | 0.793 | 0.835 | 0.830 | 0.835 | 0.822 | 0.773 | 0.667 |

Both curves have a broad plateau over 0.4–0.7 with both extremes clearly worse. The dev-selected
w = 0.5 scores 0.830 on test versus 0.822 for the served 0.7, a one-question difference well
inside the noise. The served weight is therefore left unchanged; switching to the test-best value
would be tuning on test.

### 5.4 Ablations (RQ3)

ΔMRR@5 relative to the served system [95 % CI]; Holm-adjusted p within each split.

| Variant | Dev | Test |
|---|---|---|
| No heading path in BM25 text | −0.007 [−0.07, +0.06] | −0.001 [−0.06, +0.06] |
| No heading path in dense passages (re-encoded) | +0.057 [+0.00, +0.12], p = 0.32 | −0.034 [−0.11, +0.04] |
| No heading path anywhere | +0.009 [−0.09, +0.10] | −0.019 [−0.11, +0.07] |
| No E5 `query:` prefix | +0.011 [−0.04, +0.06] | −0.013 [−0.06, +0.03] |

None of the effects is significant and none keeps its sign across splits. The dense-heading
ablation is the instructive case: on dev alone it looks like a +0.057 improvement with a CI that
just excludes zero, the kind of result that is easy to adopt; on held-out questions it reverses.
Heading context is kept because it costs nothing at query time and makes short ayat
self-describing for the generator, not because retrieval evidence favours it.

### 5.5 Error analysis (RQ4)

Served configuration, questions with gold rank > 3 or not retrieved: 7 / 40 on dev, 4 / 40 on test.

| Pattern | Examples | Count |
|---|---|---:|
| **Sibling article** — top-1 is a neighbouring provision in the same chapter | risk tiers Pasal 12 vs 13 (PP 5); water-licence revocation 429 vs the next sanction step 434 (PP 5); pemekaran rules 34C vs 34B (PP 51); PKWT basis Pasal 4 vs duration Pasal 8 (PP 35) | 4 |
| **Cross-referenced article** — top-1 cites or is cited by the gold article | sanction authority 502 vs a sanction it lists (465); UMP formula 26A vs 28; UMP effective date 29 vs 28A | 3 |
| **Generic wage vocabulary** in the amendment regulation — an overview or council article wins | UMK timing 31 vs overview 25; UMK factors 32 vs wage council 71 (rank 15) | 2 |
| **Same provision type, other sector** — a structurally identical article elsewhere in PP 5 | outsourcing warnings 516 vs another sector's warnings 385 | 1 |
| **Long, enumerative gold article** — 12 passages, none matches the question as a whole | sectors covered by PP 5 (Pasal 6), not in top 20 | 1 |

No error crosses documents. In 10 of 11 cases the gold article is within the top 20, so a
cross-encoder reranker over the top 20 has headroom; recall@20 is not the bottleneck.

### 5.6 Efficiency

Single query including encoding, CPU, 1,814 passages: p50 81 ms, p95 119 ms (`reports/experiments.json`).
Brute-force scoring is adequate at this corpus size; an ANN index becomes relevant only with the
full UU 6/2023 and beyond.

## 6. Threats to validity

- **Sample size.** n = 40 per split; CIs of ±0.1 make all but the largest differences
  undetectable. The ablation nulls are "no evidence of an effect", not "no effect".
- **Single gold article.** Some questions are partly answerable by other articles (e.g. parallel
  sector provisions); such answers count as misses, so scores are a lower bound.
- **Question authorship.** Dev questions were written by the developer; test questions were drafted
  by an LLM assistant from the article text and have not been reviewed by a legal expert. Both are
  written with the article in view, unlike real user queries, which use colloquial terms and may
  span articles. Neither set contains unanswerable questions.
- **Test reuse.** The test set has now been used once for the pre-registered analysis and once in
  `experiments` (sweep and ablations, reported but not used for selection). Further development
  decisions made while looking at it would erode its held-out status; a fresh set is needed for the
  next round.
- **Corpus.** Three regulations, not consolidated with their amendments; OCR noise unrepaired.

## 7. Generation (not evaluated quantitatively)

Retrieved passages plus sibling ayat of the same article (≤ 24k chars) are sent to Gemini with a
JSON schema. `validate_answer` rejects any statement without citations, with unknown source IDs, or
with inline `[S#]` markers absent from its `source_ids`, and forbids claims in an
`insufficient_evidence` response. This guarantees *citation well-formedness*, not *faithfulness*:
a statement can cite a real source that does not support it. No faithfulness or abstention metric
is reported in this version.

## 8. Next steps (in order of expected value)

1. **Expert-reviewed, larger test set** (≥ 150 questions, multi-article gold, unanswerable items)
   so that differences of ~0.05 become detectable.
2. **Cross-encoder reranking** of the top 20 (e.g. a multilingual MiniLM / BGE reranker) — targets
   the sibling-article errors in §5.5.
3. **Answer-level evaluation**: citation precision/recall against gold articles, abstention on
   unanswerable questions, and a human-rated faithfulness sample.
4. **OCR normalisation** for common confusions (`l`↔`/`, `O`↔`0`) before BM25 indexing, measured
   with the protocol above.
5. **Consolidation of amendments** (PP 51/2023 into PP 36/2021) so retrieval returns the law as
   amended.

## Reproducing

```bash
pip install -e ".[dev]"
legal-rag evaluate                 # dev  → reports/evaluation.json
legal-rag evaluate --split test    # test → reports/evaluation_test.json
legal-rag experiments              # E1–E6 → reports/experiments.json (~4 min CPU)
python scripts/sample_test_articles.py   # regenerates the identical test-article sample
```

Every report records the SHA-256 of the question set and of the chunk corpus; results are
deterministic on CPU (dev numbers reproduce the pre-existing `reports/evaluation.json` exactly).
