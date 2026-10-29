---
name: add-regulation
description: Add a new Indonesian regulation (PP, UU, Perpres, Permen PDF) to the Legal Atlas corpus end to end — extraction, structure validation, chunking, indexing, evaluation questions, and redeploy. Use when the user wants to add, enable, or re-ingest a legal document.
---

# Add a regulation to the corpus

The pipeline refuses to continue on structural errors on purpose. Fix the cause; never bypass
validation or hand-edit `data/processed/` or `data/indexes/`.

## 1. Register the document

- Put the PDF in `data/raw/` with the canonical name, e.g. `PP Nomor 35 Tahun 2021.pdf`. The file
  stem becomes the `doc_id` shown in citations, so keep the official form.
- Add `{"file": "...", "enabled": true}` to `config/corpus.json`. Very long documents (hundreds of
  pages, e.g. omnibus laws) should stay `enabled: false` with a `reason` until reviewed.

## 2. Extract and ingest

```bash
pip install -e ".[ingestion]"
legal-rag extract            # add --ocr only for scanned PDFs
legal-rag ingest
```

Read the new entry in `reports/ingestion.json`:

- `validation.duplicate_pasal` / `empty_pasal` must be empty — ingest raises otherwise.
- Compare `articles` with the last Pasal number in the PDF. A large gap means the parser missed
  headings; inspect `data/extracted/markdown/<doc>.md` around the missing Pasal.
- `tables_requiring_review > 0`: check whether tables carry legal content (e.g. formulas).

For one-off extraction defects (a merged heading, a misread number), add an entry to
`config/corrections.json` and re-run `legal-rag ingest`. Only change `parser.py` for patterns that
generalise, and add a fixture test in `tests/test_pipeline.py` for it.

Spot-check `data/processed/v2/structured/<doc>.json`: a few Pasal with ayat, one with
sub-points (huruf a, b, c), and the transition between batang tubuh and Penjelasan.

## 3. Index

```bash
legal-rag index
```

Unchanged passages reuse their vectors. If it fails with *Passages exceed N tokens*, lower
`MAX_CHARS` in `src/legal_rag/config.py` rather than allowing silent truncation.

## 4. Evaluate

Add 8–15 questions for the new document to `data/evaluation/dev.json` (`id`, `question`,
`expected_doc`, `expected_pasal`, `category`). Write them from the PDF, phrased the way a user
would ask — not copied from the article text. Then:

```bash
legal-rag evaluate
```

Report hit@5 and MRR@5 for `hybrid_articles` before and after. Existing documents' scores should
not drop noticeably; if they do, the new document is probably crowding results — investigate
before shipping.

## 5. Ship

- Update the corpus list in `README.md`, `deploy/huggingface/README.md`, and the description in
  `app.py`.
- `ruff check . && pytest -q`
- Commit config, processed data, index, evaluation set, and reports together.
- Redeploy with the `deploy-hf-space` skill (PDFs only reach the Space from a local deploy).
