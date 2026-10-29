---
title: Legal Atlas
emoji: ⚖️
colorFrom: indigo
colorTo: gray
sdk: gradio
sdk_version: 6.29.1
python_version: "3.12"
app_file: app.py
pinned: false
license: mit
short_description: Hybrid-search RAG over Indonesian regulations with citations
tags:
  - rag
  - retrieval
  - legal
  - indonesian
  - sentence-transformers
models:
  - intfloat/multilingual-e5-base
preload_from_hub:
  - intfloat/multilingual-e5-base
---

# Legal Atlas — Indonesian Legal RAG

Ask questions about Indonesian government regulations and get **article-level, verifiable citations**.

- **Hybrid retrieval**: multilingual-e5-base dense vectors + BM25, weighted fusion (hit@5 = 0.925 on a 40-question dev set)
- **Source-bound answers**: Gemini returns structured JSON; every statement must cite a retrieved passage, and unknown citations are rejected
- **Corpus**: PP 35/2021 (PKWT, outsourcing, PHK), PP 5/2021 (risk-based licensing), PP 51/2023 (wages)

**Search** works without any API key. **Answer with Gemini** needs the `GEMINI_API_KEY` Space secret.

> Portfolio demo over a small, non-consolidated corpus. Not legal advice.

Source code, evaluation, and architecture: <https://github.com/0alfajar/indonesian-legal-rag>
