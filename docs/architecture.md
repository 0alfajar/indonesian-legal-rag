# Architecture

Legal Atlas has two halves that share one package: an **offline build** that turns PDFs into a
validated, versioned index, and a **query path** used identically by the CLI, the Gradio Space,
the HTML demo, and the evaluation harness.

## Offline build (`src/legal_rag/pipeline/`)

| Step | Module | What it guarantees |
|---|---|---|
| Extract | `ingestion.extract` | Docling converts each enabled PDF in `config/corpus.json` to JSON + Markdown. Existing extractions are reused unless `--force`. |
| Parse | `parser.py` | Rebuilds reading order and the BAB → Bagian → Paragraf → Pasal → ayat hierarchy. Repairs list items whose `(n)` marker Docling placed at the end, applies reviewed fixes from `config/corrections.json`, and separates the *Penjelasan* (explanation) section. |
| Validate | `ingestion.ingest` | Refuses to continue on duplicate or empty Pasal; writes `reports/ingestion.json`. |
| Chunk | `chunking.py` | One chunk per ayat (or per Pasal without ayat), split at sentence boundaries above 1,600 chars. `embedding_text` prefixes the heading path (document, BAB, Pasal, ayat) so short ayat keep their context. |
| Index | `indexing.py` | Encodes `passage: …` with E5, refuses passages longer than the model's token limit instead of silently truncating, and reuses vectors for unchanged passages. |

### Index integrity

Each build writes `vectors-<run>.npy` and `metadata-<run>.json`, then commits them by atomically
replacing `manifest.json` (SHA-256 of both files). Loading verifies checksums, shape, finiteness,
unit norm, and that the chunk fingerprint matches `data/processed/v2/chunks.json` — a stale index
after re-ingestion fails loudly.

## Query path

1. **Retrieve** (`retrieval.py`) — dense cosine scores (`query: …` prefix) and BM25 over the same
   candidates, optionally filtered by document or Pasal. Hybrid fusion min-max normalises both and
   weights them 0.7 / 0.3; RRF (k = 60) is kept as a baseline. Results are deduplicated to one hit
   per article.
2. **Expand evidence** — every retrieved chunk is kept, then sibling ayat from the same Pasal are
   added up to a 24k-character budget. Each passage gets a stable ID `S1…Sn`.
3. **Generate** (`generation.py`) — Gemini receives the question and sources as JSON data (never as
   instructions) with a response schema. `validate_answer` rejects answers whose statements cite
   unknown IDs, lack citations, or contain inline `[S#]` markers missing from `source_ids`. An
   `insufficient_evidence` status must carry no claims. A configurable model list falls back on
   429/5xx/timeouts.

## Serving surfaces

| Surface | Entry point | Used for |
|---|---|---|
| Gradio | `app.py` | Free Hugging Face Space (ZeroGPU hardware, CPU retrieval) and local demo |
| HTML + stdlib server | `legal-rag serve` | Self-hosted / Docker; per-client rate limit, serialized encoding, CSP |
| CLI | `legal-rag search|ask` | Scripting and debugging, `--json` output |

## Evaluation

`legal-rag evaluate` encodes all questions once, runs six configurations (dense/hybrid over chunks
and articles, plus BM25 and RRF), and records hit@1/3/5 and MRR@5 with the dataset and corpus
fingerprints, so reports from different corpora cannot be confused.
