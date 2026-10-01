"""Project paths and reproducible defaults, independent of the working directory."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
EXTRACTED = DATA / "extracted" / "json"
PROCESSED = DATA / "processed" / "v2"
INDEX = DATA / "indexes" / "e5-v2"
QUESTIONS = DATA / "evaluation" / "dev.json"
MODEL = "intfloat/multilingual-e5-base"
MAX_CHARS = 1600
SEMANTIC_WEIGHT = 0.7

