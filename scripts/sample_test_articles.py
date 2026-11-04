"""Draw the articles for the held-out test set with a fixed, documented procedure.

The sample is drawn *before* any test question exists, so article choice cannot be
steered toward articles the retriever already handles well. Run once; the output
is committed and the questions are written against it (see data/evaluation/README.md).

    python scripts/sample_test_articles.py            # writes data/evaluation/test_articles.json
"""

import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261104
MIN_CHARS = 150          # excludes stubs such as "Dihapus." or one-line transitional clauses
QUOTA = {"PP Nomor 5 Tahun 2021": 15, "PP Nomor 35 Tahun 2021": 15, "PP Nomor 51 Tahun 2023": 10}


def article_key(pasal: str):
    match = re.match(r"(\d+)(.*)", str(pasal))
    return (0, int(match.group(1)), match.group(2)) if match else (1, 0, str(pasal))


def main() -> int:
    chunks = json.loads((ROOT / "data/processed/v2/chunks.json").read_text(encoding="utf-8"))["chunks"]
    dev = json.loads((ROOT / "data/evaluation/dev.json").read_text(encoding="utf-8"))
    used = {(q["expected_doc"], str(q["expected_pasal"])) for q in dev}

    articles = defaultdict(list)
    for chunk in chunks:
        articles[(chunk["doc_id"], str(chunk["pasal"]))].append(chunk["text"])

    rng = random.Random(SEED)
    sample, eligible_counts = [], {}
    for doc_id, quota in QUOTA.items():
        eligible = sorted(
            (pasal for (doc, pasal), texts in articles.items()
             if doc == doc_id and (doc, pasal) not in used
             and pasal != "1"                                   # definitions: answerable from many articles
             and len(" ".join(texts)) >= MIN_CHARS),
            key=article_key)
        eligible_counts[doc_id] = len(eligible)
        if len(eligible) < quota:
            print(f"{doc_id}: only {len(eligible)} eligible articles for quota {quota}", file=sys.stderr)
            return 1
        for pasal in sorted(rng.sample(eligible, quota), key=article_key):
            sample.append({"doc_id": doc_id, "pasal": pasal,
                           "text": " ".join(articles[(doc_id, pasal)])})

    out = {
        "procedure": {
            "seed": SEED, "quota": QUOTA, "min_chars": MIN_CHARS,
            "excluded": ["articles already targeted by dev.json", "Pasal 1 (definitions)",
                         f"articles shorter than {MIN_CHARS} characters"],
            "eligible_articles": eligible_counts,
        },
        "articles": sample,
    }
    path = ROOT / "data/evaluation/test_articles.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(sample)} articles to {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
