# Evaluation data

Two question sets with one gold article each. Both are retrieval benchmarks: a question is a hit
at rank *k* if the expected `(expected_doc, expected_pasal)` appears in the top *k* deduplicated
articles. Neither set measures answer correctness.

| | `dev.json` | `test.json` |
|---|---|---|
| Questions | 40 (15 PP 5/2021, 15 PP 35/2021, 10 PP 51/2023) | 40 (same split) |
| Article selection | Chosen by the developer, mostly opening articles (PP 5/2021: Pasal 2–22 + closing article) | Random sample, fixed seed, by [`scripts/sample_test_articles.py`](../../scripts/sample_test_articles.py) → [`test_articles.json`](test_articles.json) |
| Written | Alongside development | After sampling, from the article text only, before any retrieval was run on them |
| Used for | Building, debugging, tuning `SEMANTIC_WEIGHT` | Final evaluation of configurations frozen beforehand; never for tuning |
| SHA-256 (`storage.fingerprint`) | `c37efbca…c0fc57c8` | `c52627c7389c41020e874fec317e54fe0a846804c69fdbd3f01acc9051985c8e` |

## How the test set was built

1. **Sampling.** Eligible articles are every article in the three enabled regulations except
   (a) articles already targeted by `dev.json`, (b) Pasal 1 (definitions, which many questions can
   legitimately hit), and (c) articles under 150 characters (stubs such as "Dihapus."). From each
   document a fixed quota is drawn with `random.Random(20261104)`: 15 of 533 eligible articles in
   PP 5/2021, 15 of 49 in PP 35/2021, 10 of 15 in PP 51/2023.
2. **Writing.** One question per sampled article, written from that article's text alone, phrased as
   a user would ask, and specific enough that the article is the best single answer. Distinctive
   statutory phrasing was paraphrased where a natural paraphrase existed; terms of art (PKWT, PHK,
   Upah minimum) were kept.
3. **Freezing.** The file's fingerprint was recorded in this README, together with the analysis plan
   below, before `legal-rag evaluate --split test` was run for the first time.

**Provenance and caveat.** The test questions were drafted by an LLM assistant (Claude) from the
sampled article text and have not yet been reviewed by a legal domain expert. They are independent
of the retriever (no retrieval output was seen while writing them) but not of the corpus text, so
lexical overlap with the gold article is higher than for real user queries. `reports/experiments.json`
reports query–article token overlap for both sets so this bias is visible rather than assumed away.

## Pre-registered analysis plan (recorded 2026-11-04T08:51Z, before the first test run)

- **Primary metric:** MRR@5 over deduplicated articles. Secondary: hit@1, hit@3, hit@5.
- **Served configuration:** hybrid, min-max fusion, `SEMANTIC_WEIGHT = 0.7`, article dedup — unchanged
  from the version that produced the dev results.
- **Hypotheses (one-sided intent, two-sided tests):**
  - H1: hybrid has higher MRR@5 than BM25 alone.
  - H2: hybrid has higher MRR@5 than dense (E5) alone.
  - H3 (descriptive): test MRR@5 is lower than dev MRR@5, i.e. dev numbers are optimistic.
- **Tests:** paired randomization (sign-flip) test on per-question reciprocal rank, 10,000
  permutations, seed 0; Holm–Bonferroni correction across the comparisons against hybrid
  (dense, BM25, RRF); α = 0.05. 95 % percentile bootstrap intervals (10,000 resamples, seed 0) for
  every metric.
- **Secondary:** the fusion weight chosen by leave-one-document-out cross-validation on `dev.json`
  is also evaluated on test, as is the full weight grid (reported, not used for selection).
- **Reporting:** every configuration and every comparison is reported whether or not it is
  significant. The test set is not edited after the first run; label errors found later are
  recorded as errata in the technical report, not silently fixed.
