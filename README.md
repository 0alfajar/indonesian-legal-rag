# Legal Atlas

A retrieval-augmented generation (RAG) system for Indonesian legal documents with hybrid search, verifiable citations, and optional LLM-powered answers.

## Overview

Legal Atlas indexes Indonesian regulations (Peraturan Pemerintah) and enables natural language search with precise article-level citations. The system combines dense vector retrieval with BM25 lexical matching for robust search across legal text.

**Core capabilities:**
- Semantic and lexical hybrid search over legal provisions
- Article and section-level citation tracking
- Direct PDF page linking for source verification
- Optional LLM answer generation with inline citations
- Reproducible evaluation framework

## Architecture

```
legal_rag/
├── ingestion.py      # PDF extraction and document parsing
├── chunking.py       # Article-based text segmentation
├── indexing.py       # E5 embedding generation and storage
├── retrieval.py      # Hybrid search (dense + BM25 + RRF)
├── generation.py     # Gemini answer synthesis with citations
├── evaluation.py     # Retrieval quality benchmarks
├── server.py         # Local web demo server
└── web/              # Frontend interface
```

**Search pipeline:**
1. Query embedding (multilingual-e5-base)
2. Dense retrieval (cosine similarity)
3. BM25 lexical matching
4. Reciprocal Rank Fusion
5. Optional LLM generation with source attribution

## Installation

**Requirements:** Python 3.11+

```bash
# Clone repository
git clone <repository-url>
cd legal-rag

# Install dependencies
pip install -e .

# For PDF extraction (optional)
pip install -e ".[ingestion]"

# For development
pip install -e ".[dev]"
```

**Dependencies:**
- `numpy` - Array operations
- `rank-bm25` - Lexical search
- `sentence-transformers` - Dense retrieval
- `python-dotenv` - Environment config

## Quick Start

### 1. Run the Web Interface

```bash
python -m legal_rag serve
```

Open **http://127.0.0.1:8000** in your browser.

The interface provides:
- Natural language queries in Indonesian
- Document scope filtering
- Search-only or answer generation modes
- Expandable source citations with PDF links

### 2. Command Line Search

**Search provisions:**
```bash
python -m legal_rag search "ketentuan upah minimum" --top-k 5
```

**Get LLM answer with citations:**
```bash
python -m legal_rag ask "Bagaimana formula perhitungan upah minimum?"
```

**Filter by document:**
```bash
python -m legal_rag search "perizinan berusaha" --document "PP Nomor 5 Tahun 2021"
```

**Filter by article:**
```bash
python -m legal_rag search "kompensasi PKWT" --pasal 15
```

## Data Pipeline

### Ingestion

```bash
# Extract PDFs to structured JSON
python -m legal_rag extract

# Parse and chunk documents
python -m legal_rag ingest

# Build vector index
python -m legal_rag index
```

**Chunking strategy:**
- Article-level segmentation (Pasal + Ayat)
- Maximum 1,600 characters per chunk
- Metadata preservation (document ID, page numbers, hierarchy)

**Corpus:** 3 Indonesian government regulations (PP 35/2021, PP 5/2021, PP 51/2023)

### Evaluation

```bash
python -m legal_rag evaluate --questions data/evaluation/dev.json
```

Measures retrieval quality across methods:
- Dense (E5 embeddings only)
- BM25 (lexical only)
- Hybrid (weighted combination)
- RRF (Reciprocal Rank Fusion)

Metrics: Recall@k, MRR, precision

## Configuration

### Environment Variables

Create `.env` file:

```bash
# Optional: for answer generation
GEMINI_API_KEY=your_api_key_here
```

Without `GEMINI_API_KEY`, the system runs in search-only mode.

### Corpus Management

Edit `config/corpus.json` to enable/disable documents:

```json
{
  "documents": [
    {"file": "PP Nomor 35 Tahun 2021.pdf", "enabled": true},
    {"file": "PP Nomor 5 Tahun 2021.pdf", "enabled": true}
  ]
}
```

### Retrieval Parameters

Adjust in `legal_rag/config.py`:

```python
MODEL = "intfloat/multilingual-e5-base"  # Embedding model
MAX_CHARS = 1600                          # Chunk size
SEMANTIC_WEIGHT = 0.7                     # Dense vs BM25 ratio
```

## API Reference

### Server Endpoints

**GET /api/health**
```json
{
  "status": "ready",
  "documents": ["PP Nomor 35 Tahun 2021", ...],
  "chunks": 1814,
  "generation_configured": true
}
```

**POST /api/query**
```json
{
  "question": "Bagaimana ketentuan upah minimum?",
  "document": "PP Nomor 51 Tahun 2023",  // optional
  "mode": "answer"  // or "search"
}
```

Response includes:
- `results`: Ranked search results with scores
- `sources`: Formatted citations with metadata
- `answer`: LLM-generated response (if mode=answer)

### Python API

```python
from legal_rag.retrieval import Retriever

retriever = Retriever.load()
results = retriever.search(
    question="kompensasi PKWT",
    top_k=5,
    method="hybrid"
)

for result in results:
    chunk = result["chunk"]
    print(f"{chunk['doc_id']} - Pasal {chunk['pasal']}")
    print(f"Score: {result['score']:.3f}")
```

## Project Structure

```
.
├── config/                   # Corpus configuration
├── data/
│   ├── raw/                  # Source PDFs
│   ├── extracted/            # Parsed JSON/Markdown
│   ├── processed/            # Chunked documents
│   ├── indexes/              # Vector embeddings
│   └── evaluation/           # Test questions
├── legal_rag/
│   ├── web/                  # Frontend (HTML/CSS/JS)
│   ├── ingestion.py          # PDF processing
│   ├── chunking.py           # Text segmentation
│   ├── indexing.py           # Embedding generation
│   ├── retrieval.py          # Search implementation
│   ├── generation.py         # LLM integration
│   ├── evaluation.py         # Quality metrics
│   └── server.py             # HTTP server
├── tests/                    # Test suite
├── pyproject.toml            # Dependencies
└── README.md
```

## Technical Details

### Embedding Model

**intfloat/multilingual-e5-base**
- 278M parameters
- 768-dimensional embeddings
- Trained on 1B+ multilingual pairs
- Strong Indonesian language support

### Search Methods

**Dense retrieval:**
- Cosine similarity on E5 embeddings
- Optimized for semantic matching

**BM25:**
- Traditional keyword search
- Tokenization preserves Indonesian morphology

**Hybrid fusion:**
- Weighted combination (70% dense / 30% BM25)
- Reciprocal Rank Fusion option

### Citation System

Each answer statement includes:
- Inline source markers `[S1]`, `[S2]`
- Document ID and article number
- PDF page reference
- Original provision text

Citations are verifiable through:
1. Source card expansion (web UI)
2. Direct PDF links with page anchors
3. JSON output (CLI)

## Development

### Running Tests

```bash
python -m pytest tests/
```

### Code Quality

```bash
# Lint check
ruff check .

# Format
ruff format .
```

### Adding Documents

1. Place PDF in `data/raw/`
2. Enable in `config/corpus.json`
3. Run ingestion pipeline:
   ```bash
   python -m legal_rag extract
   python -m legal_rag ingest
   python -m legal_rag index
   ```

## Limitations

- **Corpus scope:** Development demo with 3 regulations, not comprehensive
- **Language:** Indonesian only (multilingual model, but corpus is Indonesian)
- **Document types:** Peraturan Pemerintah format; other legal texts may need parser adjustments
- **LLM dependency:** Answer generation requires external API (Gemini)
- **Extraction quality:** OCR accuracy varies by PDF source quality

## Performance

**Search latency:**
- Dense retrieval: ~50ms
- Hybrid search: ~100ms
- With LLM generation: 2-5s

**Resource requirements:**
- RAM: ~2GB (embedding model loaded)
- Disk: ~500MB (embeddings + processed data)
- CPU: Inference uses CPU by default (GPU optional)

## License

See LICENSE file for details.

## Acknowledgments

Built with:
- [sentence-transformers](https://github.com/UKPLab/sentence-transformers) for embedding generation
- [rank-bm25](https://github.com/dorianbrown/rank_bm25) for lexical search
- [Docling](https://github.com/DS4SD/docling) for PDF extraction
- [Gemini API](https://ai.google.dev/) for answer generation

---

**Note:** This is a portfolio demonstration project. For production legal research systems, consider: expanded corpus coverage, citation accuracy validation with legal experts, audit logging, and compliance with data protection regulations.
