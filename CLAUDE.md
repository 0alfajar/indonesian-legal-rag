# Legal Atlas — notes for Claude Code

Indonesian legal RAG: Docling extraction → Pasal/ayat parser → chunking → E5 + BM25 hybrid
retrieval → schema-constrained Gemini answers with validated citations.

## Commands

```bash
pip install -e ".[demo,dev]"     # local dev (add [ingestion] for PDF extraction, [deploy] for HF)
ruff check . && pytest -q        # offline; must pass before any commit
python app.py                    # Gradio demo (what the HF Space runs)
legal-rag serve                  # stdlib HTML demo (what the Dockerfile runs)
legal-rag search "<q>" | ask "<q>" | evaluate | ingest | index
```

## Layout

- `src/legal_rag/pipeline/` — offline build (parser, chunking, ingestion, indexing)
- `src/legal_rag/{retrieval,generation,evaluation}.py` — shared by every surface
- `app.py` — HF Space entry; `deploy/huggingface/README.md` — Space card; `scripts/deploy_hf.py`
- `data/indexes/e5-v2/` — manifest + checksummed artefacts; regenerate, never edit

## Constraints

- **HF hosting must stay free**: Gradio SDK on ZeroGPU. Docker/CPU Spaces need a paid plan.
  Retrieval runs on CPU (`LEGAL_RAG_DEVICE=cpu`); keep the no-op `@spaces.GPU` in `app.py`.
- Index loading verifies checksums and the chunk fingerprint; after `ingest`, always `index`.
- Generation must stay source-bound: don't loosen `validate_answer` to accommodate a model.
- Retrieval changes need before/after metrics (see the `evaluate-retrieval` skill).
- Never log questions or keys; secrets go to `.env` locally and Space secrets remotely.

## Skills

- `deploy-hf-space` — deploy/debug the Space
- `add-regulation` — add a PDF to the corpus end to end
- `evaluate-retrieval` — measure and explain retrieval changes
- `.agents/skills/` — third-party frontend design skills, for UI work on `src/legal_rag/web/`
