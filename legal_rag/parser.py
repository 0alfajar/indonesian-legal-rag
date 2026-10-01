"""Parse article and paragraph structure from single-column Docling legal PDFs.

Original source text is retained. Only explicitly reviewed heading corrections
and conservative list-marker repairs are applied; all are recorded in the output.
"""

import json
import re
from pathlib import Path
from collections import Counter

from .config import ROOT
from .storage import read_json



# =========================================================
# 1. GENERIC NOISE CLEANING
# =========================================================

def is_noise_line(line: str) -> bool:
    """Return True for obvious repeated PDF header/footer noise."""
    raw = line.strip()
    if not raw:
        return True

    compact = re.sub(r"\s+", " ", raw)
    upper = compact.upper()

    # Website footer/header
    if re.fullmatch(r"(?:WWW\.)?PERATURAN\.GO\.ID", upper):
        return True

    # Gazette footer, e.g. 2021, No.15 / 2023, No. 146
    if re.fullmatch(r"\d{4}\s*,\s*NO\.?\s*\d+", upper):
        return True

    # SK codes, e.g. SK No 031784 A / SK No. 187394A
    if re.fullmatch(r"SK\s+NO\.?\s+[A-Z0-9\s.-]+", upper):
        return True

    # Obvious page numbers and OCR-corrupted page numbers:
    # -12-, - 12 -, -t4-, -L9-, -J.J-, 11-
    if len(compact) <= 10:
        if re.fullmatch(r"-\s*[0-9ILTJ.]+\s*-", upper):
            return True
        if re.fullmatch(r"[0-9]{1,4}\s*-", upper):
            return True

    # Repeated presidential header with OCR noise.
    # Examples: PRESIDEN REPUBLIK INDONESIA,
    #           PRESIDEN REPUELIK INDONESIA
    #           FRESTDEN REPUBLII( INDONESIA
    #           PRESIDEN REPUBLIK TNDONESIA
    if len(compact) <= 80:
        president_like = (
            "PRESID" in upper
            or "FRESID" in upper
            or "FREST" in upper
        )
        indonesia_like = (
            "INDON" in upper
            or "NDON" in upper
            or "TNDON" in upper
        )
        if president_like and indonesia_like:
            return True

    return False


def clean_text(text: str) -> str:
    """Conservative line-based cleaning; does not rewrite legal wording."""
    if not text:
        return ""

    kept = []
    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        if not line:
            continue
        if is_noise_line(line):
            continue
        kept.append(line)

    return "\n".join(kept).strip()


# =========================================================
# 2. DOCLING READING ORDER
# =========================================================

def build_ref_lookup(data: dict) -> dict:
    """Build '#/texts/..' / '#/groups/..' lookup from a Docling JSON."""
    lookup = {}

    for collection_name in ("texts", "groups", "tables", "pictures", "key_value_items"):
        for item in data.get(collection_name, []) or []:
            ref = item.get("self_ref")
            if ref:
                lookup[ref] = item

    return lookup


def flatten_body(data: dict) -> list:
    """
    Get Docling text items in reading order.

    Strategy:
    1. Traverse body recursively when possible.
    2. Keep an item's own text even when it also has children.
    3. If body traversal returns nothing, fall back to data["texts"].

    This is intentionally simple and generic because different Docling
    exports can organize body/groups differently.
    """
    lookup = build_ref_lookup(data)
    ordered = []
    visited = set()

    def walk_ref(ref: str):
        if not ref or ref in visited:
            return

        item = lookup.get(ref)
        if item is None:
            return

        visited.add(ref)

        # Keep this item's own visible text.
        if item.get("text") or item.get("orig"):
            ordered.append(item)

        # Then traverse children in declared order.
        for child in item.get("children", []) or []:
            if not isinstance(child, dict):
                continue

            child_ref = child.get("$ref") or child.get("self_ref")
            if child_ref:
                walk_ref(child_ref)

    body = data.get("body") or {}

    if isinstance(body, dict):
        for child in body.get("children", []) or []:
            if not isinstance(child, dict):
                continue

            ref = child.get("$ref") or child.get("self_ref")
            if ref:
                walk_ref(ref)

    # Some Docling JSONs do not expose usable body traversal.
    # In that case, texts[] is still useful and is already ordered.
    if not ordered:
        ordered = [
            item
            for item in data.get("texts", []) or []
            if item.get("text") or item.get("orig")
        ]

    return ordered


def get_page(item: dict):
    prov = item.get("prov") or []
    if not prov:
        return None
    return prov[0].get("page_no")


def item_text(item: dict) -> str:
    """
    Reconstruct visible text from Docling item.
    Uses marker when Docling stores '(1)', 'a.', etc. separately.
    """
    marker = clean_text(str(item.get("marker") or ""))
    text = clean_text(str(item.get("text") or item.get("orig") or ""))

    if marker and text:
        # Avoid duplicating markers already present in text.
        if text.startswith(marker):
            return text
        return f"{marker} {text}".strip()

    # Some PDF text layers put the paragraph marker after the sentence.
    # Restrict repair to list items ending in punctuation and a marker.
    trailing = re.fullmatch(r"(.+[.;:])\s+\((\d+)\)", text, re.DOTALL)
    if not marker and item.get("label") == "list_item" and trailing:
        return f"({trailing.group(2)}) {trailing.group(1)}"
    return marker or text


def ordered_items(data: dict) -> list:
    """Repair within-page reading order for this single-column corpus.

    Do not use this layout assumption for multi-column PDFs without review.
    Docling page headers/footers include continuation previews, not body text.
    """
    items = [item for item in flatten_body(data)
             if item.get("label") not in {"page_header", "page_footer"}]

    def position(pair):
        index, item = pair
        prov = (item.get("prov") or [{}])[0]
        box = prov.get("bbox", {})
        top = box.get("t")
        if top is None:
            return (prov.get("page_no", 0), index, index)
        y = -top if box.get("coord_origin") == "BOTTOMLEFT" else top
        return (prov.get("page_no", 0), y, index)

    # Without complete geometry, preserve Docling's order rather than guess.
    if all(item.get("prov") and "bbox" in item["prov"][0] for item in items):
        items = [item for _, item in sorted(enumerate(items), key=position)]
    return items


# =========================================================
# 3. STRUCTURAL DETECTION
# =========================================================

def detect_bab(text: str):
    """
    Returns (heading, inline_title).

    Supports:
      BAB I
      BAB XIIIA KETENTUAN LAIN-LAIN
    """
    s = re.sub(r"\s+", " ", text.strip())
    m = re.fullmatch(r"BAB\s+([IVXLCDM]+[A-Z]?)(?:\s+(.+))?", s, re.IGNORECASE)
    if not m:
        return None
    heading = f"BAB {m.group(1).upper()}"
    title = m.group(2).strip() if m.group(2) else None
    return heading, title


def detect_bagian(text: str):
    """Returns (heading, inline_title)."""
    s = re.sub(r"\s+", " ", text.strip())
    ordinal = (
        r"Kesatu|Kedua|Ketiga|Keempat|Kelima|Keenam|Ketujuh|Kedelapan|"
        r"Kesembilan|Kesepuluh|Kesebelas|Kedua\s+Belas|Ketiga\s+Belas|"
        r"Keempat\s+Belas|Kelima\s+Belas|Keenam\s+Belas|Ketujuh\s+Belas|"
        r"Kedelapan\s+Belas|Kesembilan\s+Belas|Kedua\s+Puluh"
    )
    m = re.fullmatch(rf"Bagian\s+({ordinal})(?:\s+(.+))?", s, re.IGNORECASE)
    if not m:
        return None
    heading = f"Bagian {m.group(1)}"
    title = m.group(2).strip() if m.group(2) else None
    return heading, title


def detect_paragraf(text: str):
    """Returns (heading, inline_title)."""
    s = re.sub(r"\s+", " ", text.strip())
    m = re.fullmatch(r"Paragraf\s+(\d+)(?:\s+(.+))?", s, re.IGNORECASE)
    if not m:
        return None
    heading = f"Paragraf {m.group(1)}"
    title = m.group(2).strip() if m.group(2) else None
    return heading, title


def normalize_pasal_token(token: str) -> str:
    token = token.strip().rstrip(".:;,")

    # Roman Pasal I / II in amendment regulations.
    if re.fullmatch(r"[IVXLCDM]+", token, re.IGNORECASE):
        return token.upper()

    # '1 1' -> '11', '2 6 A' -> '26A'
    token = re.sub(r"\s+", "", token)

    # Normalize suffix capitalization.
    m = re.fullmatch(r"(\d+)([A-Za-z]?)", token)
    if not m:
        return token

    return m.group(1) + m.group(2).upper()


def detect_pasal(text: str):
    """
    Detect standalone article headings only.

    Supports:
      Pasal 10
      Pasal10
      Pasal 1 1   -> 11
      Pasal 26A
      Pasal II

    It intentionally does NOT match references such as:
      'Pasal 10 ayat (1) ...'
    """
    s = re.sub(r"\s+", " ", text.strip())

    # Heading must be short; prevents normal sentences from matching.
    if len(s) > 40:
        return None

    m = re.fullmatch(
        r"Pasal\s*((?:\d(?:\s*\d)*[A-Za-z]?|[IVXLCDM]+))\s*(?:[.:]|\.\s*\.)?",
        s,
        re.IGNORECASE,
    )
    if not m:
        return None

    return normalize_pasal_token(m.group(1))


def detect_ayat_start(text: str):
    """
    Detect ayat marker at the beginning of an item.

    Handles common extraction noise:
      (1) text
      (21 text   -> interpreted as ayat 2
      (2\\ text  -> interpreted as ayat 2
    """
    s = text.strip()

    # Proper '(12) text'
    m = re.match(r"^\((\d+)\)\s*(.*)$", s, re.DOTALL)
    if m:
        return int(m.group(1)), m.group(2).strip()

    # OCR ')' -> '1', e.g. '(21 text' means '(2) text'.
    m = re.match(r"^\(([1-9])1\s+(.*)$", s, re.DOTALL)
    if m:
        return int(m.group(1)), m.group(2).strip()

    # OCR closing parenthesis -> backslash, e.g. '(2\\ text'
    m = re.match(r"^\((\d+)\\\s*(.*)$", s, re.DOTALL)
    if m:
        return int(m.group(1)), m.group(2).strip()

    return None


def is_explanation_start(text: str) -> bool:
    upper = re.sub(r"\s+", " ", text.upper()).strip()
    return upper == "PENJELASAN" or upper.startswith("PENJELASAN ATAS")


def is_closing_start(text: str) -> bool:
    """Detect promulgation/signature material after the final legal article."""
    upper = re.sub(r"\s+", " ", text.upper()).strip()
    # Use only strong closing signals here.
    # "LEMBARAN NEGARA ..." often appears in citations inside
    # the preamble, so treating it as a closing trigger can make
    # the parser stop before Pasal 1.
    starts = (
        "AGAR SETIAP ORANG MENGETAHUINYA",
        "DIUNDANGKAN DI ",
        "DITETAPKAN DI ",
    )
    return upper.startswith(starts)


def looks_like_title(text: str) -> bool:
    """Conservative helper for BAB/Bagian/Paragraf titles."""
    s = text.strip()
    if not s or len(s) > 180:
        return False
    if detect_bab(s) or detect_bagian(s) or detect_paragraf(s) or detect_pasal(s):
        return False
    if detect_ayat_start(s):
        return False
    if is_closing_start(s) or is_explanation_start(s):
        return False
    return True


# =========================================================
# 4. PARSER
# =========================================================

def parse_document(file_path: Path) -> dict:
    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    items = ordered_items(data)
    correction_file = ROOT / "config" / "corrections.json"
    corrections = read_json(correction_file).get(file_path.stem, [])
    applied_corrections = []
    amendments = []

    # Small debug block so we can see whether the failure is in
    # Docling traversal or in Pasal detection.
    pasal_candidates = []
    for item in items:
        text = item_text(item)
        if detect_pasal(text) is not None:
            pasal_candidates.append(text)

    print(f"Docling text items : {len(items)}")
    print(f"Pasal headings seen: {len(pasal_candidates)}")
    print(f"First headings     : {pasal_candidates[:10]}")

    sections = []
    closing_metadata = []
    explanation_lines = []
    warnings = []

    current_bab = None
    current_bab_title = None
    current_bagian = None
    current_bagian_title = None
    current_paragraf = None
    current_paragraf_title = None

    pending_title = None
    current = None
    mode = "body"  # body -> closing -> explanation

    def new_section(pasal, page):
        return {
            "bab": current_bab,
            "bab_title": current_bab_title,
            "bagian": current_bagian,
            "bagian_title": current_bagian_title,
            "paragraf": current_paragraf,
            "paragraf_title": current_paragraf_title,
            "pasal": pasal,
            "page_start": page,
            "page_end": page,
            "heading_pages": [page] if page is not None else [],
            "_content": [],
            "_ayat": [],
            "_current_ayat": None,
            "_unassigned": [],
        }

    def finalize_ayat(section):
        if not section or section["_current_ayat"] is None:
            return
        ay = section["_current_ayat"]
        ay["text"] = "\n".join(ay.pop("_parts")).strip()
        section["_ayat"].append(ay)
        section["_current_ayat"] = None

    def dedupe_ayat(ayat_list):
        """
        Merge repeated ayat numbers caused by page-break previews.

        Generic rule: for the same ayat number, keep the fuller text
        and expand the page span. This avoids duplicate preview lines
        such as "(3) Masa..." followed by the complete ayat on the
        next page.
        """
        merged = []
        by_number = {}

        for ay in ayat_list:
            number = ay["number"]

            if number not in by_number:
                copy = dict(ay)
                by_number[number] = copy
                merged.append(copy)
                continue

            existing = by_number[number]
            old_text = existing.get("text", "").strip()
            new_text = ay.get("text", "").strip()

            # Discard only verified duplicate prefixes, never distinct text.
            if new_text.startswith(old_text):
                existing["text"] = new_text
            elif not old_text.startswith(new_text):
                existing["text"] = old_text + "\n" + new_text
                warnings.append(f"Merged distinct text for repeated ayat {number}; review required")

            pages = [
                p for p in (
                    existing.get("page_start"),
                    existing.get("page_end"),
                    ay.get("page_start"),
                    ay.get("page_end"),
                )
                if p is not None
            ]
            if pages:
                existing["page_start"] = min(pages)
                existing["page_end"] = max(pages)

        return merged

    def save_current():
        nonlocal current
        if current is None:
            return

        finalize_ayat(current)

        text = "\n".join(current.pop("_content")).strip()
        ayat = dedupe_ayat(current.pop("_ayat"))
        current.pop("_current_ayat", None)

        current["text"] = text
        current["ayat"] = ayat
        current["unassigned_text"] = "\n".join(current.pop("_unassigned")).strip()
        sections.append(current)
        current = None

    for item in items:
        text = item_text(item)
        if not text:
            continue

        page = get_page(item)
        for correction in corrections:
            if page == correction["page"] and text == correction["original"]:
                text = correction["replacement"]
                applied_corrections.append(correction)

        # -------------------------------------------------
        # Explanation section: keep it separate from body.
        # -------------------------------------------------
        if is_explanation_start(text):
            save_current()
            mode = "explanation"
            explanation_lines.append({"text": text, "page": page})
            continue

        if mode == "explanation":
            explanation_lines.append({"text": text, "page": page})
            continue

        # -------------------------------------------------
        # Closing metadata after final article.
        # -------------------------------------------------
        # Only enter closing mode after at least one article has been
        # parsed. This prevents legal citations in the preamble from
        # accidentally terminating the whole document.
        if is_closing_start(text) and (current is not None or sections):
            save_current()
            mode = "closing"
            closing_metadata.append({"text": text, "page": page})
            continue

        if mode == "closing":
            closing_metadata.append({"text": text, "page": page})
            continue

        # Amendment instructions belong to the amending instrument, not the
        # preceding quoted article. Preserve them separately for inspection.
        if re.match(r"^(?:\d+[.)]?\s+)?(?:Ketentuan\s+Pasal\b|Di\s+antara\s+Pasal\b)", text, re.I) and re.search(
            r"diubah|disisipkan|dihapus", text, re.I
        ):
            save_current()
            amendments.append({"text": text, "page": page})
            continue

        # -------------------------------------------------
        # Capture title following BAB/Bagian/Paragraf.
        # -------------------------------------------------
        if pending_title and looks_like_title(text):
            if pending_title == "bab":
                current_bab_title = text
            elif pending_title == "bagian":
                current_bagian_title = text
            elif pending_title == "paragraf":
                current_paragraf_title = text
            pending_title = None
            continue
        elif pending_title:
            pending_title = None

        # -------------------------------------------------
        # Structural headings
        # -------------------------------------------------
        bab_info = detect_bab(text)
        if bab_info:
            save_current()
            current_bab, inline_title = bab_info
            current_bab_title = inline_title
            current_bagian = None
            current_bagian_title = None
            current_paragraf = None
            current_paragraf_title = None
            pending_title = None if inline_title else "bab"
            continue

        bagian_info = detect_bagian(text)
        if bagian_info:
            save_current()
            current_bagian, inline_title = bagian_info
            current_bagian_title = inline_title
            current_paragraf = None
            current_paragraf_title = None
            pending_title = None if inline_title else "bagian"
            continue

        paragraf_info = detect_paragraf(text)
        if paragraf_info:
            save_current()
            current_paragraf, inline_title = paragraf_info
            current_paragraf_title = inline_title
            pending_title = None if inline_title else "paragraf"
            continue

        pasal = detect_pasal(text)
        if pasal is not None:
            # Same heading repeated around a page break: do not create duplicate.
            if current is not None and current["pasal"] == pasal:
                if page is not None and page not in current["heading_pages"]:
                    current["heading_pages"].append(page)
                continue

            save_current()
            current = new_section(pasal, page)
            continue

        # -------------------------------------------------
        # Normal body content
        # -------------------------------------------------
        if current is None:
            # Preamble / amendment instructions before first detected article.
            # Keep only as warning-free ignored text for now.
            continue

        if page is not None:
            if current["page_start"] is None:
                current["page_start"] = page
            current["page_end"] = page

        current["_content"].append(text)

        ay = detect_ayat_start(text)
        if ay:
            finalize_ayat(current)
            number, ayat_text = ay
            current["_current_ayat"] = {
                "number": number,
                "page_start": page,
                "page_end": page,
                "_parts": [ayat_text] if ayat_text else [],
            }
        elif current["_current_ayat"] is not None:
            current["_current_ayat"]["_parts"].append(text)
            if page is not None:
                current["_current_ayat"]["page_end"] = page
        else:
            current["_unassigned"].append(text)

    save_current()

    # -----------------------------------------------------
    # Simple generic post-validation
    # -----------------------------------------------------
    ids = [s["pasal"] for s in sections]
    duplicates = [k for k, v in Counter(ids).items() if v > 1]

    empty_sections = [s["pasal"] for s in sections if not s["text"].strip()]

    ayat_issues = []
    for s in sections:
        nums = [a["number"] for a in s["ayat"]]
        if not nums:
            continue
        missing = sorted(set(range(1, max(nums) + 1)) - set(nums))
        if missing:
            warnings.append(f"Pasal {s['pasal']}: missing ayat markers {missing}; review source")
        dup_ayat = [k for k, v in Counter(nums).items() if v > 1]
        if dup_ayat:
            ayat_issues.append({"pasal": s["pasal"], "duplicate_ayat": dup_ayat})

    # A malformed heading such as Pasal4T can remain detectable but suspicious.
    for s in sections:
        p = str(s["pasal"])
        if re.fullmatch(r"\d+[D-Z]", p):
            warnings.append(f"Suspicious Pasal heading: Pasal {p}")

    return {
        "doc_id": file_path.stem,
        "source": str(file_path),
        "parser_version": "2.0-single-column-reviewed",
        "total_pasal": len(sections),
        "sections": sections,
        "closing_metadata": closing_metadata,
        "explanation": explanation_lines,
        "amendment_instructions": amendments,
        "applied_corrections": applied_corrections,
        "validation": {
            "duplicate_pasal": duplicates,
            "empty_pasal": empty_sections,
            "ayat_issues": ayat_issues,
            "warnings": warnings,
        },
    }
