FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    HOST=0.0.0.0

WORKDIR /app

# Install minimal build tools if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch CPU first to avoid heavy CUDA wheels (saves >1.5GB image size)
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch

# Copy dependency definition and project files
COPY . .

# Install package dependencies
RUN pip install --no-cache-dir -e .

# Pre-cache the embedding model during docker build so startup takes 1s instead of minutes
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-base')"

EXPOSE 8000

# Start server directly without rebuilding the index (pre-built indexes exist in data/indexes/e5-v2)
CMD ["python", "-m", "legal_rag", "serve"]
