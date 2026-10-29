---
name: deploy-hf-space
description: Deploy or update the Legal Atlas demo on a free Hugging Face Space (Gradio SDK + ZeroGPU), set the Gemini secret, and debug Space build or runtime failures. Use when the user asks to deploy, publish, redeploy, or fix the HF Space / online demo.
---

# Deploy the Hugging Face Space

The free demo is a **Gradio Space on ZeroGPU hardware**. Docker and CPU Gradio Spaces require a
paid HF plan — do not switch the Space to Docker to "fix" something unless the user confirms
they have PRO.

## Preconditions

1. Tests and lint pass: `ruff check . && pytest -q`.
2. The index is current: `python -c "from legal_rag.pipeline.indexing import load_index; load_index()"`
   must not raise. If it says *stale*, run `legal-rag index` first.
3. The app starts locally: `python app.py`, then run one example query in the browser or with
   `gradio_client` against `/search`.
4. The Space exists (created once in the web UI with SDK **Gradio**, hardware **ZeroGPU**). The
   deploy script refuses to create it, because creation with other hardware needs a paid plan.

## Deploy

```bash
pip install -e ".[deploy]"
python scripts/deploy_hf.py --space <user>/legal-atlas --dry-run   # review the file list
python scripts/deploy_hf.py --space <user>/legal-atlas
```

- Needs `HF_TOKEN` (write) in the environment or `.env`; `HF_SPACE_ID` can replace `--space`.
- Uploading is outward-facing: confirm with the user before the real (non-dry-run) upload.
- If `GEMINI_API_KEY` is present it is stored as a Space **secret**. Never write keys into files.
- Uses the Hub API (not `git push`): the git history has non-LFS `.npy` blobs the Hub rejects.

Automatic redeploys: `.github/workflows/deploy-hf.yml` (secret `HF_TOKEN`, variable `HF_SPACE_ID`).

## Files that define the Space

| File | Role |
|---|---|
| `deploy/huggingface/README.md` | Space card; YAML sets `sdk: gradio`, `sdk_version`, `python_version`, `app_file` |
| `app.py` | Entry point; imports `spaces` first, pins `LEGAL_RAG_DEVICE=cpu`, registers a no-op `@spaces.GPU` |
| `requirements.txt` | Space runtime only. Torch must stay on the ZeroGPU supported list; do not add `gradio` here |

When bumping Gradio, change `sdk_version` in the Space card **and** the `demo` extra in
`pyproject.toml` together, then retest locally.

## Debugging a failed Space

Read the build and container logs on the Space page first. Common causes:

| Log message | Cause → fix |
|---|---|
| `No @spaces.GPU function detected during startup` | `spaces` not importable or imported after torch |
| `No CUDA GPUs are available` | Model placed on CUDA; `LEGAL_RAG_DEVICE` not set before `Retriever.load()` |
| `Index vectors checksum mismatch` / `stale` | Index and `chunks.json` out of sync → rebuild locally, redeploy both |
| pip resolution error on torch | Torch pin outside ZeroGPU's supported versions |
| Answer mode disabled | `GEMINI_API_KEY` secret missing → add it, restart the Space |

After any fix, redeploy and verify the live Space with one search and one answer query.
