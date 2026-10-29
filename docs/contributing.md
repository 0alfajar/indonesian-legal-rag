# Contributing

## Setup

```bash
git clone https://github.com/0alfajar/indonesian-legal-rag.git
cd indonesian-legal-rag
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[demo,dev]"
cp .env.example .env                                # optional: GEMINI_API_KEY
```

`scripts/setup.sh` / `scripts/setup.bat` do the same in one step.

## Checks

```bash
ruff check .
pytest -q
```

The suite is offline: parser and chunking run on small fixtures, the index loader on temporary
files, and Gemini through mocked `urlopen`. CI runs the same two commands on every push and PR.

## Where things live

| Change | Module | Also update |
|---|---|---|
| PDF structure parsing | `src/legal_rag/pipeline/parser.py` | Regression test with a fixture in `tests/`; re-run `legal-rag ingest` |
| Chunk boundaries / heading context | `src/legal_rag/pipeline/chunking.py` | Re-index and re-evaluate (vectors change) |
| Retrieval scoring | `src/legal_rag/retrieval.py` | `legal-rag evaluate`; report the metric delta in the PR |
| Prompt, schema, citation rules | `src/legal_rag/generation.py` | `validate_answer` tests |
| Gradio demo | `app.py` | Run `python app.py` and try the examples |
| HTML demo | `src/legal_rag/server.py`, `src/legal_rag/web/` | Run `legal-rag serve` |
| Corpus selection | `config/corpus.json` | Evaluation questions for the new document |

## Rules that keep results trustworthy

- **Never edit generated data by hand.** `data/processed/` and `data/indexes/` come from
  `legal-rag ingest` and `legal-rag index`; the index loader rejects mismatched checksums.
- **Parser fixes for a single PDF go in `config/corrections.json`**, not in special-case code.
- **Retrieval changes need numbers.** Include before/after hit@k and MRR@5 from
  `reports/evaluation.json`. Do not tune weights on the dev set and then report them as held-out.
- **Generated answers must stay source-bound.** Do not relax `validate_answer` to make a model
  pass; switch models or fix the prompt instead.
- Do not log user questions or API keys.

## Style

- Ruff, 110-character lines.
- Module docstrings explain *why* the module exists; comments explain non-obvious decisions.
- Frontend: vanilla JS/CSS, no build step.
- Commit messages: conventional prefix (`feat`, `fix`, `docs`, `refactor`, `chore`) and an
  imperative summary, e.g. `fix(retrieval): keep BM25-only hits above zero score`.
