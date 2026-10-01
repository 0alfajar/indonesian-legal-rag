"""Run the portfolio pipeline with ``python -m legal_rag --help``."""

import argparse
import json
import sys
from pathlib import Path

from .config import ROOT, QUESTIONS


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env", override=False)
    except ImportError:
        pass  # OS environment variables remain supported without python-dotenv.
    parser = argparse.ArgumentParser(description="Indonesian legal RAG: ingestion, search, evaluation, Gemini answers")
    commands = parser.add_subparsers(dest="command", required=True)
    extract = commands.add_parser("extract", help="Extract enabled PDFs with Docling")
    extract.add_argument("--force", action="store_true", help="Replace existing extractions")
    extract.add_argument("--ocr", action="store_true", help="Enable OCR for scanned PDFs")
    commands.add_parser("ingest", help="Parse existing extractions and create v2 chunks")
    index = commands.add_parser("index", help="Build the E5 vector index")
    index.add_argument("--batch-size", type=int, default=16)
    evaluate = commands.add_parser("evaluate", help="Compare retrieval methods without Gemini calls")
    evaluate.add_argument("--questions", type=Path, default=QUESTIONS)
    for name in ("search", "ask"):
        command = commands.add_parser(name, help="Retrieve sources" if name == "search" else "Retrieve sources and ask Gemini")
        command.add_argument("question")
        command.add_argument("--top-k", type=int, default=5)
        command.add_argument("--document", help="Exact document ID, e.g. PP Nomor 35 Tahun 2021")
        command.add_argument("--pasal", help="Filter an article number")
        command.add_argument("--method", choices=["dense", "bm25", "hybrid", "rrf"], default="hybrid")
        command.add_argument("--json", action="store_true", help="Print machine-readable output")
    serve = commands.add_parser("serve", help="Start the local portfolio web demo")
    serve.add_argument("--port", type=int, default=8000)
    for command in (index, evaluate, serve, commands.choices["search"], commands.choices["ask"]):
        command.add_argument("--offline", action="store_true", help="Load embedding model from local cache only")
    args = parser.parse_args()
    try:
        if args.command == "extract":
            from .ingestion import extract as run
            run(args.force, args.ocr)
        elif args.command == "ingest":
            from .ingestion import ingest
            print(json.dumps(ingest(), ensure_ascii=False, indent=2))
        elif args.command == "index":
            from .indexing import build_index
            print(build_index(args.offline, args.batch_size))
        elif args.command == "evaluate":
            from .evaluation import evaluate as run
            run(args.offline, args.questions.resolve())
        elif args.command == "serve":
            from .server import serve as run
            run(args.port, args.offline)
        else:
            from .retrieval import Retriever
            retriever = Retriever.load(args.offline)
            results = retriever.search(args.question, args.top_k, args.method,
                                       doc_id=args.document, pasal=args.pasal)
            output = {"question": args.question, "results": results}
            if args.command == "ask":
                from .generation import generate_answer
                sources = retriever.evidence(results)
                output.update(answer=generate_answer(args.question, sources), sources=sources)
            if args.json:
                print(json.dumps(output, ensure_ascii=False, indent=2))
            else:
                if "answer" in output:
                    for statement in output["answer"]["statements"]:
                        print(statement["text"], " ".join(f"[{s}]" for s in statement["source_ids"]))
                    print(output["answer"]["limitations"])
                    for source in output["sources"]:
                        print(f"[{source['source_id']}] {source['doc_id']} | Pasal {source['pasal']} | ayat {source['ayat']} | PDF page {source['page_start']}")
                else:
                    for row in results:
                        chunk = row["chunk"]
                        print(f"\n{row['rank']}. {chunk['doc_id']} | Pasal {chunk['pasal']} | ayat {chunk['ayat']} | PDF page {chunk['page_start']}")
                        print(chunk["text"])
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
