# Self-hosted image for the standard-library web demo (src/legal_rag/web).
# Not used by the Hugging Face Space: Docker Spaces need a paid plan, so the free
# demo runs app.py on the Gradio SDK instead (see docs/deployment.md).
FROM python:3.11-slim

RUN useradd --create-home --uid 1000 user
USER user

ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/home/user/.cache/huggingface \
    LEGAL_RAG_ROOT=/home/user/app \
    HOST=0.0.0.0 \
    PORT=7860

WORKDIR /home/user/app

# CPU-only PyTorch keeps the image ~2 GB smaller than the default CUDA wheels.
RUN pip install --user --index-url https://download.pytorch.org/whl/cpu torch
RUN pip install --user "sentence-transformers==6.1.0"

# Bake the embedding model into the image so cold starts never download it.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-base')"

COPY --chown=user pyproject.toml README.md ./
COPY --chown=user src ./src
RUN pip install --user .

# Serving needs only the prebuilt index, the chunk manifest, and optional source PDFs.
COPY --chown=user config ./config
COPY --chown=user data ./data

EXPOSE 7860
ENV HF_HUB_OFFLINE=1
CMD ["legal-rag", "serve", "--offline"]
