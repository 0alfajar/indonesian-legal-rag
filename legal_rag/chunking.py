"""Create bounded retrieval passages without losing unassigned article text."""

import re
from .config import MAX_CHARS


def split_text(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    """Prefer sentence boundaries; hard-split unusually long sentences safely."""
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    remaining = re.sub(r"\s+", " ", text).strip()
    pieces = []
    while len(remaining) > max_chars:
        window = remaining[:max_chars + 1]
        boundaries = list(re.finditer(r"[.;!?]\s+", window))
        end = boundaries[-1].start() + 1 if boundaries else window.rfind(" ")
        if end < max_chars // 3:
            end = max_chars
        pieces.append(remaining[:end].strip())
        remaining = remaining[end:].strip()
    if remaining:
        pieces.append(remaining)
    return pieces


def create_chunks(document: dict) -> list[dict]:
    chunks = []
    doc_id = document["doc_id"]
    slug = re.sub(r"[^a-z0-9]+", "_", doc_id.lower()).strip("_")
    for section in document["sections"]:
        units = []
        if section["ayat"]:
            if section.get("unassigned_text"):
                units.append((None, section["unassigned_text"], section))
            units.extend((ayat["number"], ayat["text"], ayat) for ayat in section["ayat"])
        else:
            units.append((None, section["text"], section))
        for ayat, text, location in units:
            pieces = split_text(text)
            for part, piece in enumerate(pieces, 1):
                headings = [f"Dokumen: {doc_id}"]
                for key in ("bab", "bagian", "paragraf"):
                    if section.get(key):
                        headings.append(": ".join(filter(None, (
                            section[key], section.get(key + "_title")
                        ))))
                headings.append(f"Pasal {section['pasal']}")
                if ayat is not None:
                    headings.append(f"Ayat ({ayat})")
                identifier = f"{slug}_pasal_{section['pasal']}"
                if ayat is not None:
                    identifier += f"_ayat_{ayat}"
                if len(pieces) > 1:
                    identifier += f"_part_{part}"
                chunks.append({
                    "chunk_id": identifier,
                    "doc_id": doc_id,
                    "pasal": section["pasal"],
                    "ayat": ayat,
                    "part": part if len(pieces) > 1 else None,
                    "page_start": location.get("page_start"),
                    "page_end": location.get("page_end"),
                    "text": piece,
                    "embedding_text": "\n".join(headings) + "\n\n" + piece,
                })
    identifiers = [chunk["chunk_id"] for chunk in chunks]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError(f"Duplicate chunk identifiers in {doc_id}; inspect parser output")
    return chunks
