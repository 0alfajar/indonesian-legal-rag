# Changelog

All notable changes to Legal Atlas will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-10-29

### Added
- Gradio app (`app.py`) for a free Hugging Face Space on ZeroGPU hardware, with CPU retrieval,
  two-stage search → answer flow, and PDF page links.
- `scripts/deploy_hf.py`: single-commit Space upload through the Hub API, Space secret for
  `GEMINI_API_KEY`, and cleanup of stale index artefacts.
- GitHub Actions: CI (ruff + pytest) and automatic Space deployment.
- HTML server: per-client rate limit, HF-compatible `frame-ancestors`, proxy-aware origin check,
  and PDF links shown only when the PDF is deployed.
- `LEGAL_RAG_ROOT` and `LEGAL_RAG_DEVICE` environment overrides.
- Claude Code project skills and `CLAUDE.md`.
- Docs: architecture, deployment, rewritten contributing guide.

### Changed
- `src/` layout; offline build steps moved to `legal_rag.pipeline`.
- Dockerfile runs as uid 1000 with the model baked in, and is now for self-hosting only.
- Encoding lock no longer blocks concurrent Gemini calls.

### Removed
- Railway config and superseded deployment guides.
- Legacy `data/embeddings/` from version control (local cache only).

## [0.1.0] - 2024-10-01

### Added
- Initial release of Legal Atlas
- Hybrid retrieval system (dense + BM25 + RRF)
- Web interface for legal document search
- Command-line interface for search and ask operations
- PDF extraction pipeline with Docling
- Article-level chunking strategy
- E5 multilingual embedding indexing
- Gemini API integration for answer generation
- Citation tracking and verification system
- Evaluation framework for retrieval quality
- Support for 3 Indonesian regulations (PP 35/2021, PP 5/2021, PP 51/2023)
- Configurable corpus management
- Direct PDF page linking
- Mobile-responsive UI
- Health check API endpoint
- Error handling and user feedback

### Technical Details
- Python 3.11+ support
- sentence-transformers integration
- rank-bm25 lexical search
- Standard library HTTP server
- Vanilla JavaScript frontend (no frameworks)
- Dark mode UI inspired by modern chat interfaces

### Documentation
- Comprehensive README with setup instructions
- API reference documentation
- Contributing guidelines
- Code of conduct
- MIT License

## [Unreleased]

### Planned
- Additional Indonesian legal documents
- Advanced filtering (date ranges, legal hierarchy)
- Export functionality (PDF, citations)
- Search history and bookmarks
- Multi-language UI support
- Performance optimizations for large corpora
- GPU acceleration for embedding generation

---

**Note:** This project is in active development. Breaking changes may occur in minor versions until 1.0.0 release.
