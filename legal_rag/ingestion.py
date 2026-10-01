"""Explicit corpus selection and non-destructive ingestion into versioned outputs."""

from pathlib import Path
from .config import ROOT, DATA, EXTRACTED, PROCESSED
from .chunking import create_chunks
from .parser import parse_document
from .storage import read_json, write_json, fingerprint


def corpus() -> list[dict]:
    return read_json(ROOT / "config" / "corpus.json")["documents"]


def extract(force: bool = False, ocr: bool = False) -> None:
    """Extract enabled PDFs; existing Docling artifacts are reused by default."""
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(
        pipeline_options=PdfPipelineOptions(do_ocr=ocr, do_table_structure=True)
    )})
    for entry in corpus():
        if not entry["enabled"]:
            continue
        source = DATA / "raw" / entry["file"]
        target = EXTRACTED / (source.stem + ".json")
        if target.exists() and not force:
            print(f"Reuse extraction: {source.name}", flush=True)
            continue
        print(f"Extracting: {source.name}", flush=True)
        result = converter.convert(source)
        if str(result.status.value) != "success":
            raise RuntimeError(f"Extraction incomplete for {source.name}: {result.status}")
        write_json(target, result.document.export_to_dict())
        markdown = DATA / "extracted" / "markdown" / (source.stem + ".md")
        markdown.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text(result.document.export_to_markdown(), encoding="utf-8")


def ingest() -> dict:
    all_chunks, summaries = [], []
    for entry in corpus():
        if not entry["enabled"]:
            continue
        path = EXTRACTED / (Path(entry["file"]).stem + ".json")
        if not path.exists():
            raise FileNotFoundError(f"Missing {path.name}; run: python -m legal_rag extract")
        document = parse_document(path)
        validation = document["validation"]
        if not document["sections"] or validation["duplicate_pasal"] or validation["empty_pasal"]:
            raise ValueError(f"Invalid structure in {path.name}: {validation}")
        chunks = create_chunks(document)
        write_json(PROCESSED / "structured" / path.name, document)
        all_chunks.extend(chunks)
        summaries.append({
            "document": document["doc_id"], "articles": len(document["sections"]),
            "chunks": len(chunks), "validation": validation,
            "corrections": document["applied_corrections"],
            "explanation_items_excluded": len(document["explanation"]),
            "tables_requiring_review": len(read_json(path).get("tables", [])),
        })
    if not all_chunks:
        raise ValueError("No enabled documents produced chunks")
    payload = {"schema_version": 2, "fingerprint": fingerprint(all_chunks), "chunks": all_chunks}
    write_json(PROCESSED / "chunks.json", payload)
    report = {"documents": summaries, "total_chunks": len(all_chunks),
              "excluded": [entry for entry in corpus() if not entry["enabled"]]}
    write_json(ROOT / "reports" / "ingestion.json", report)
    return report
