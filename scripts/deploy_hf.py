"""Publish the demo to a Hugging Face Space (Gradio SDK, ZeroGPU) as a single commit.

Uploads through the Hub API instead of ``git push`` so binary artifacts (vectors,
PDFs) go to Xet/LFS storage automatically and the GitHub history, which holds
old non-LFS binaries, never has to be pushed to the Hub.

Create the Space once in the web UI first (SDK: Gradio, hardware: ZeroGPU), because
free accounts can only host Gradio Spaces on ZeroGPU; see docs/deployment.md.

Usage:
    pip install -e ".[deploy]"
    export HF_TOKEN=hf_...            # token with write access
    python scripts/deploy_hf.py --space <user>/legal-atlas [--dry-run]

GEMINI_API_KEY, if set locally, is stored as a Space secret (never uploaded as a file).
"""

import argparse
import json
import os
import sys
from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPACE_CARD = ROOT / "deploy" / "huggingface" / "README.md"
INCLUDE = [
    "app.py", "requirements.txt", "LICENSE",
    "src/legal_rag/**/*", "config/*.json", "data/processed/v2/chunks.json",
]
EXCLUDE = ["*/__pycache__/*", "*.pyc"]
# Remote paths the deploy owns; anything else (e.g. PDFs uploaded earlier) is left alone.
MANAGED = ["src/**", "config/**", "data/indexes/**", "data/processed/**"]


def matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch(path, pattern) for pattern in patterns)


def index_files() -> list[str]:
    """Only the vectors and metadata the current manifest points to."""
    index = ROOT / "data" / "indexes" / "e5-v2"
    manifest = json.loads((index / "manifest.json").read_text(encoding="utf-8"))
    return [str((index / name).relative_to(ROOT).as_posix())
            for name in ("manifest.json", manifest["vectors"], manifest["metadata"])]


def enabled_pdfs() -> list[str]:
    corpus = json.loads((ROOT / "config" / "corpus.json").read_text(encoding="utf-8"))
    paths = [ROOT / "data" / "raw" / doc["file"] for doc in corpus["documents"] if doc["enabled"]]
    return [path.relative_to(ROOT).as_posix() for path in paths if path.exists()]


def collect() -> dict[str, Path]:
    files = {}
    for pattern in INCLUDE:
        for path in ROOT.glob(pattern):
            relative = path.relative_to(ROOT).as_posix()
            if path.is_file() and not matches(relative, EXCLUDE):
                files[relative] = path
    for relative in index_files() + enabled_pdfs():
        files[relative] = ROOT / relative
    # The Space card (with HF YAML metadata) replaces the GitHub README.
    files["README.md"] = SPACE_CARD
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--space", help="Space repo id, e.g. user/legal-atlas (or set HF_SPACE_ID)")
    parser.add_argument("--dry-run", action="store_true", help="List files without uploading")
    args = parser.parse_args()
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env", override=False)
    except ImportError:
        pass
    args.space = args.space or os.environ.get("HF_SPACE_ID")
    if not args.space:
        parser.error("--space or HF_SPACE_ID is required")

    files = collect()
    size = sum(path.stat().st_size for path in files.values())
    for relative in sorted(files):
        print(f"  {relative}")
    print(f"{len(files)} files, {size / 1e6:.1f} MB -> spaces/{args.space}")
    if args.dry_run:
        return 0

    from huggingface_hub import CommitOperationAdd, CommitOperationDelete, HfApi

    api = HfApi(token=os.environ.get("HF_TOKEN"))
    if not api.repo_exists(args.space, repo_type="space"):
        print(f"Space {args.space} not found. Create it at https://huggingface.co/new-space "
              "with SDK 'Gradio' and hardware 'ZeroGPU', then rerun.", file=sys.stderr)
        return 1
    remote = api.list_repo_files(args.space, repo_type="space")
    stale = [path for path in remote if matches(path, MANAGED) and path not in files]
    operations = [CommitOperationAdd(path_in_repo=rel, path_or_fileobj=str(path)) for rel, path in files.items()]
    operations += [CommitOperationDelete(path_in_repo=path) for path in stale]
    commit = api.create_commit(args.space, repo_type="space", operations=operations,
                               commit_message=os.environ.get("DEPLOY_MESSAGE", "Deploy Legal Atlas"))
    if os.environ.get("GEMINI_API_KEY"):
        api.add_space_secret(args.space, "GEMINI_API_KEY", os.environ["GEMINI_API_KEY"])
        print("Stored GEMINI_API_KEY as a Space secret")
    print(f"Deployed {commit.oid[:8]}: https://huggingface.co/spaces/{args.space}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
