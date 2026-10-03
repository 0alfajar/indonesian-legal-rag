FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Rebuild index on container build
RUN python -m legal_rag index || echo "Index build failed, will retry on start"

# Expose port
EXPOSE 7860

# Run the server (rebuild index if needed, then serve)
CMD python -m legal_rag index && python -m legal_rag serve --port 7860
