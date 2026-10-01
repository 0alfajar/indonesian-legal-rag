"""Loopback-only portfolio demo, sharing the tested retrieval and Gemini services.

This standard-library server is for local demonstrations, not public deployment.
"""

import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import unquote, urlsplit

from .config import DATA, ROOT
from .generation import GenerationError, generate_answer
from .retrieval import Retriever

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
except ImportError:
    pass

WEB = Path(__file__).parent / "web"
LOGGER = logging.getLogger(__name__)


def serve(port: int = 8000, offline: bool = False) -> None:
    retriever = Retriever.load(offline)
    documents = sorted({chunk["doc_id"] for chunk in retriever.chunks})
    inference_lock = Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # Do not log user questions or credentials.

        def send_bytes(self, status, body, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'; object-src 'none'")
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, status, payload):
            self.send_bytes(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def valid_host(self):
            return self.headers.get("Host") in {f"127.0.0.1:{port}", f"localhost:{port}"}

        def do_GET(self):
            if not self.valid_host():
                return self.send_json(403, {"error": "Use the local demo address"})
            path = urlsplit(self.path).path
            if path == "/api/health":
                return self.send_json(200, {
                    "status": "ready", "documents": documents, "chunks": len(retriever.chunks),
                    "generation_configured": bool(os.environ.get("GEMINI_API_KEY")),
                })
            static = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                      "/style.css": ("style.css", "text/css; charset=utf-8")}
            if path in static:
                filename, content_type = static[path]
                return self.send_bytes(200, (WEB / filename).read_bytes(), content_type)
            if path.startswith("/sources/"):
                doc_id = unquote(path[len("/sources/"):])
                if doc_id in documents:
                    pdf = DATA / "raw" / (doc_id + ".pdf")
                    if pdf.exists():
                        return self.send_bytes(200, pdf.read_bytes(), "application/pdf")
            self.send_json(404, {"error": "Not found"})

        def do_POST(self):
            if not self.valid_host():
                return self.send_json(403, {"error": "Use the local demo address"})
            origin = self.headers.get("Origin")
            if origin and origin not in {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}:
                return self.send_json(403, {"error": "Cross-origin requests are not allowed"})
            if self.path != "/api/query":
                return self.send_json(404, {"error": "Not found"})
            if self.headers.get_content_type() != "application/json":
                return self.send_json(415, {"error": "Expected application/json"})
            if not inference_lock.acquire(blocking=False):
                return self.send_json(429, {"error": "Another query is running; please try again shortly"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 12000:
                    raise ValueError("Request is empty or too large")
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError("Expected a JSON object")
                question = payload.get("question", "")
                if not isinstance(question, str) or not 1 <= len(question.strip()) <= 2000:
                    raise ValueError("Enter a question between 1 and 2000 characters")
                document = payload.get("document") or None
                if document is not None and document not in documents:
                    raise ValueError("Unknown document")
                mode = payload.get("mode", "search")
                if mode not in {"search", "answer"}:
                    raise ValueError("Choose search or answer")
                results = retriever.search(question, doc_id=document)
                sources = retriever.evidence(results)
                response = {"results": results, "sources": sources, "answer": None}
                if mode == "answer":
                    try:
                        response["answer"] = generate_answer(question, sources)
                    except GenerationError as exc:
                        response["generation_error"] = str(exc)
                self.send_json(200, response)
            except (ValueError, TypeError):
                self.send_json(400, {"error": "Invalid request: enter a question and select a valid document and mode"})
            except Exception:
                LOGGER.error("Unexpected query failure", exc_info=False)
                self.send_json(500, {"error": "The query could not be completed; check the local index"})
            finally:
                inference_lock.release()

    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        print(f"Legal RAG demo: http://127.0.0.1:{port} (Ctrl+C to stop)", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
