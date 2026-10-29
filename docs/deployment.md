# Deployment

## Hugging Face Space (free)

Hugging Face now requires a paid plan for **Docker** and CPU **Gradio** Spaces. The free option for
a personal account is a **Gradio Space on ZeroGPU hardware** (up to 2 per account; the account
needs a verified email and must be at least 30 days old). Legal Atlas fits that model:

- `app.py` is a Gradio app; the embedding model is pinned to CPU (`LEGAL_RAG_DEVICE=cpu`).
  Encoding one query takes ~100 ms on CPU, so visitors never spend their daily ZeroGPU quota.
- ZeroGPU refuses to start without at least one `@spaces.GPU` function, so `app.py` registers a
  no-op one.
- The free Space sleeps after a period without visitors and wakes on the next visit (~1 min).

### First deploy

1. Create the Space at <https://huggingface.co/new-space>:
   - Name: `legal-atlas`, License: MIT
   - SDK: **Gradio**, Hardware: **ZeroGPU**, Visibility: Public
2. Create a write token at <https://huggingface.co/settings/tokens>.
3. Upload:

   ```bash
   pip install -e ".[deploy]"
   export HF_TOKEN=hf_...
   python scripts/deploy_hf.py --space <hf-username>/legal-atlas --dry-run   # inspect the file list
   python scripts/deploy_hf.py --space <hf-username>/legal-atlas
   ```

   The script uploads `app.py`, `requirements.txt`, the package, the current index, the chunk
   manifest, and the enabled source PDFs as one commit, and replaces the Space README with
   [`deploy/huggingface/README.md`](../deploy/huggingface/README.md) (the Space card with HF
   metadata). If `GEMINI_API_KEY` is set locally (or in `.env`) it is stored as a **Space
   secret**, never as a file.
4. Watch the build logs on the Space page. The first build takes several minutes.

The Hub API is used instead of `git push` because the Hub rejects binary files that are not
stored in Xet/LFS, and this repository's history contains plain-git `.npy` files.

### Continuous deployment

[`.github/workflows/deploy-hf.yml`](../.github/workflows/deploy-hf.yml) redeploys on pushes to
`main` that touch the app, package, config, or index. In the GitHub repository settings add:

- Secret `HF_TOKEN` — the write token
- Variable `HF_SPACE_ID` — e.g. `<hf-username>/legal-atlas`

Source PDFs are not tracked in git, so CI deploys leave the PDFs from your first local deploy in
place.

### Gemini

Answers need `GEMINI_API_KEY` (Space → Settings → Variables and secrets). Google AI Studio's free
tier is enough for a demo. Optionally set `GEMINI_MODEL` (comma-separated) to override the
fallback list in `src/legal_rag/generation.py`.

### Troubleshooting

| Symptom | Fix |
|---|---|
| `No @spaces.GPU function detected during startup` | Hardware is ZeroGPU but `spaces` failed to import; check `requirements.txt` still lists `spaces`. |
| `No CUDA GPUs are available` during a query | The model was placed on CUDA; ensure `LEGAL_RAG_DEVICE=cpu` is set before `Retriever.load()`. |
| `Index vectors checksum mismatch` | The `.npy` was altered in transit; redeploy with the script rather than editing files on the Hub. |
| `Index is stale after ingestion` | `chunks.json` and the index disagree; run `legal-rag index` locally and redeploy both. |
| Answer mode greyed out | `GEMINI_API_KEY` secret is missing; add it and restart the Space. |

## Self-hosting with Docker

The [Dockerfile](../Dockerfile) serves the HTML demo (`legal-rag serve`) with the model baked into
the image:

```bash
docker build -t legal-atlas .
docker run -p 7860:7860 -e GEMINI_API_KEY=... legal-atlas
```

Server settings (environment variables):

| Variable | Default | Purpose |
|---|---|---|
| `PORT` / `HOST` | `7860` / `0.0.0.0` in the image | Bind address |
| `RATE_LIMIT_PER_MINUTE` | `20` | Queries per client IP per minute; `0` disables |
| `FRAME_ANCESTORS` | `'self' https://huggingface.co https://*.hf.space` | CSP `frame-ancestors` for embedding |
| `LEGAL_RAG_ROOT` | repository root | Directory containing `data/` and `config/` |
| `LEGAL_RAG_DEVICE` | auto | Force the embedding device (`cpu`, `cuda`) |

The container needs about 2 GB of RAM.
