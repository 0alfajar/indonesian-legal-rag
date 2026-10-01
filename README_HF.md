---
title: Legal Atlas
emoji: ⚖️
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
license: mit
---

# Legal Atlas

A retrieval-augmented generation (RAG) system for Indonesian legal documents with hybrid search and verifiable citations.

## Features

- Semantic and lexical hybrid search over Indonesian regulations
- Article-level citation tracking with PDF page references
- Optional LLM answer generation with inline citations
- Support for 3 Indonesian regulations (PP 35/2021, PP 5/2021, PP 51/2023)

## Usage

The web interface provides:
- Natural language queries in Indonesian
- Document scope filtering
- Search-only or answer generation modes
- Expandable source citations

## Technical Stack

- Python 3.11
- sentence-transformers (multilingual-e5-base)
- BM25 lexical search
- Gemini API (optional, for answer generation)

## Local Development

See the main repository for full setup instructions: [GitHub Repository Link]

## Environment Variables

Set `GEMINI_API_KEY` in HF Spaces settings for answer generation. Without it, the system runs in search-only mode.
