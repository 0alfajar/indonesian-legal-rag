"""Project paths and reproducible defaults, independent of the working directory."""

import os
from pathlib import Path

# Source checkouts resolve the repository from src/legal_rag/config.py. Container
# and non-editable installs set LEGAL_RAG_ROOT to the directory holding data/.
ROOT = Path(os.environ.get("LEGAL_RAG_ROOT") or Path(__file__).resolve().parents[2])
DATA = ROOT / "data"
EXTRACTED = DATA / "extracted" / "json"
PROCESSED = DATA / "processed" / "v2"
INDEX = DATA / "indexes" / "e5-v2"
QUESTIONS = DATA / "evaluation" / "dev.json"
MODEL = "intfloat/multilingual-e5-base"
MAX_CHARS = 1600
SEMANTIC_WEIGHT = 0.7
