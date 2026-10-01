# Deployment Guide

This guide covers deploying Legal Atlas to various environments.

## Local Development

See [README.md](README.md) for quick start instructions.

```bash
python -m legal_rag serve --port 8000
```

Access at: http://127.0.0.1:8000

## Production Considerations

### Security

**⚠️ Important:** The built-in HTTP server is for local demonstration only. For production:

1. **Use a production WSGI server** (not included):
   - Gunicorn (Linux/macOS)
   - Waitress (cross-platform)
   - uWSGI

2. **Add reverse proxy** (nginx, Apache, Caddy):
   - SSL/TLS termination
   - Rate limiting
   - Request logging
   - Static file caching

3. **Environment variables:**
   - Store `GEMINI_API_KEY` securely (not in code)
   - Use secrets management (AWS Secrets Manager, Azure Key Vault, etc.)

4. **Access control:**
   - Add authentication layer
   - Implement user sessions
   - Audit query logs

### Example: Nginx + Gunicorn

**Not currently supported** - the server uses `http.server.BaseHTTPRequestHandler`.

To deploy with WSGI:
1. Refactor `legal_rag/server.py` to expose WSGI application
2. Install Gunicorn: `pip install gunicorn`
3. Run: `gunicorn legal_rag.wsgi:app --workers 4 --bind 0.0.0.0:8000`

**nginx configuration:**
```nginx
server {
    listen 80;
    server_name legal-atlas.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /static/ {
        alias /path/to/legal_rag/web/;
    }
}
```

## Docker Deployment (Future)

A Dockerfile is not yet included. To containerize:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -e .

EXPOSE 8000
CMD ["python", "-m", "legal_rag", "serve", "--port", "8000"]
```

**Note:** Embedding model downloads ~1GB on first run. Consider:
- Pre-baking model into image
- Using volume mounts for cache
- Multi-stage builds to reduce image size

## Cloud Platforms

### AWS

**Option 1: EC2**
1. Launch Ubuntu instance (t3.medium or larger)
2. Install Python 3.11+
3. Clone repository
4. Run setup script
5. Configure security group (port 8000)

**Option 2: ECS (containerized)**
- Create Docker image
- Push to ECR
- Deploy as ECS service
- Use Application Load Balancer

**Storage:**
- S3 for PDF documents
- EFS for embeddings index (if shared across instances)

### Google Cloud

**Option 1: Compute Engine**
Similar to AWS EC2 approach.

**Option 2: Cloud Run (containerized)**
- Build container with Cloud Build
- Deploy to Cloud Run
- Auto-scaling included
- Use Secret Manager for API keys

### Azure

**Option 1: Virtual Machine**
Similar to AWS EC2 approach.

**Option 2: App Service (containerized)**
- Deploy Docker container
- Configure environment variables
- Use Azure Key Vault for secrets

## Performance Tuning

### Memory

**Minimum:** 2GB RAM
- Embedding model: ~1.5GB
- Application: ~500MB
- OS overhead: ~500MB

**Recommended:** 4GB+ RAM for production

### CPU

The system is CPU-bound during:
- Query embedding generation (~50ms)
- Vector similarity search (~50ms)
- LLM API calls (network-bound)

**Recommendation:** 2+ CPU cores for concurrent queries

### Scaling

**Horizontal scaling:**
- Run multiple instances behind load balancer
- Share embedding index via network storage (NFS, EFS)
- Cache query embeddings (Redis, Memcached)

**Vertical scaling:**
- More RAM = larger corpus support
- More CPU = better concurrent query performance
- GPU = faster embedding generation (requires code changes)

### Caching Strategy

Consider caching:
1. **Query embeddings** (24hr TTL):
   - Reduces model inference load
   - Key: hash(query_text)

2. **Search results** (1hr TTL):
   - For popular queries
   - Invalidate on corpus updates

3. **LLM responses** (optional):
   - Expensive to generate
   - Consider legal/compliance implications

## Monitoring

### Health Checks

```bash
curl http://localhost:8000/api/health
```

Monitor for:
- Status: "ready"
- Chunk count matches expected corpus size
- generation_configured: true (if using LLM)

### Logs

Application logs go to stdout/stderr. Capture with:
- systemd journal (Linux)
- CloudWatch Logs (AWS)
- Stackdriver (GCP)
- Azure Monitor (Azure)

### Metrics to Track

- Query latency (p50, p95, p99)
- Error rate (4xx, 5xx responses)
- LLM API failures
- Memory usage
- CPU usage
- Concurrent requests

### Alerting

Set alerts for:
- Health check failures
- High error rate (>5%)
- High latency (>10s)
- Memory usage >80%
- LLM API quota exceeded

## Backup and Recovery

### Data to Backup

1. **Source documents:** `data/raw/` (PDFs)
2. **Processed data:** `data/processed/v2/` (chunks)
3. **Embeddings:** `data/indexes/e5-v2/` (can regenerate, but slow)
4. **Configuration:** `config/corpus.json`, `.env`

### Recovery Process

1. Restore source PDFs to `data/raw/`
2. If embeddings lost: `python -m legal_rag index` (slow)
3. If only chunks lost: `python -m legal_rag ingest` then index
4. Verify with health check

## Updates and Maintenance

### Updating the Application

```bash
git pull origin main
pip install -e . --upgrade
# Restart server
```

### Updating Dependencies

```bash
pip install --upgrade sentence-transformers rank-bm25
# Test thoroughly before production deploy
```

### Adding Documents

1. Add PDF to `data/raw/`
2. Enable in `config/corpus.json`
3. Extract: `python -m legal_rag extract`
4. Ingest: `python -m legal_rag ingest`
5. Index: `python -m legal_rag index`
6. Restart server

**Downtime:** Indexing requires restart (minutes to hours depending on corpus size)

## Cost Estimation

### Compute (example: AWS EC2 t3.medium)
- Instance: ~$30/month (on-demand)
- Storage: ~$1/month (10GB EBS)
- Bandwidth: Varies by usage

### LLM API (Gemini)
- Pay per token
- Typical query: 500-1000 tokens
- Cost depends on usage volume

### Total
- Small deployment: $50-100/month
- Medium (with caching, monitoring): $100-200/month
- Large (multi-region, HA): $500+/month

## Troubleshooting

### Server won't start

**Check:** Python version
```bash
python --version  # Should be 3.11+
```

**Check:** Dependencies installed
```bash
pip list | grep -E "numpy|rank-bm25|sentence"
```

**Check:** Port already in use
```bash
lsof -i :8000  # Linux/macOS
netstat -ano | findstr :8000  # Windows
```

### Search returns no results

**Check:** Index exists
```bash
ls -lh data/indexes/e5-v2/
```

**Check:** Chunks loaded
```bash
curl http://localhost:8000/api/health | jq .chunks
```

**Fix:** Rebuild index
```bash
python -m legal_rag index
```

### Out of memory

**Reduce model memory:**
- Use smaller embedding model (not yet configurable)
- Reduce batch size in indexing

**Increase available memory:**
- Upgrade instance type
- Add swap space (Linux)

### LLM generation fails

**Check:** API key set
```bash
echo $GEMINI_API_KEY
```

**Check:** Network connectivity
```bash
curl https://generativelanguage.googleapis.com
```

**Fallback:** Use search-only mode
- System works without LLM
- Citations still available

## Support

For deployment issues:
- Check [README.md](README.md) first
- Review logs for error messages
- Open issue on GitHub with environment details
- Include health check output

---

**Remember:** This is a demonstration project. Production deployments require additional security hardening, monitoring, and legal compliance review.
