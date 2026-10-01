# Changelog

All notable changes to Legal Atlas will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
