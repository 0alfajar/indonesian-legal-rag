"""Portfolio demo server, sharing the tested retrieval and Gemini services.

The standard-library server is sized for a self-hosted single-container demo
(see Dockerfile): one embedding model, serialized query encoding, and a
per-client rate limit so a public URL cannot exhaust the Gemini quota. The free
Hugging Face Space serves the same services through app.py instead.
"""

import json
import logging
import os
import time
from collections import defaultdict, deque
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
# Hugging Face renders a Space inside an iframe on huggingface.co.
DEFAULT_FRAME_ANCESTORS = "'self' https://huggingface.co https://*.hf.space"


class RateLimiter:
    """Sliding one-minute window per client; zero disables the limit."""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self.hits = defaultdict(deque)
        self.lock = Lock()

    def allow(self, client: str) -> bool:
        if self.per_minute <= 0:
            return True
        now = time.monotonic()
        with self.lock:
            window = self.hits[client]
            while window and now - window[0] > 60:
                window.popleft()
            if len(window) >= self.per_minute:
                return False
            window.append(now)
            return True


def serve(port: int = None, host: str = None, offline: bool = False) -> None:
    if port is None:
        port = int(os.environ.get("PORT", "8000"))
    if host is None:
        host = os.environ.get("HOST", "0.0.0.0")

    retriever = Retriever.load(offline)
    documents = sorted({chunk["doc_id"] for chunk in retriever.chunks})
    pdfs = [doc for doc in documents if (DATA / "raw" / (doc + ".pdf")).exists()]
    csp = ("default-src 'self'; object-src 'none'; frame-ancestors "
           + os.environ.get("FRAME_ANCESTORS", DEFAULT_FRAME_ANCESTORS))
    limiter = RateLimiter(int(os.environ.get("RATE_LIMIT_PER_MINUTE", "20")))
    # The embedding model is not shared safely across threads; Gemini calls are.
    encoder_lock = Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # Do not log user questions or credentials.

        def send_bytes(self, status, body, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", csp)
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, status, payload):
            self.send_bytes(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def client(self):
            forwarded = self.headers.get("X-Forwarded-For", "")
            return forwarded.split(",")[0].strip() or self.client_address[0]

        def same_origin(self):
            origin = self.headers.get("Origin")
            if not origin:
                return True
            origin_host = urlsplit(origin).netloc.lower()
            # Reverse proxies (Hugging Face, Railway) may rewrite Host but keep X-Forwarded-Host.
            hosts = {self.headers.get(name, "").lower() for name in ("Host", "X-Forwarded-Host")}
            loopback = {f"127.0.0.1:{port}", f"localhost:{port}", "127.0.0.1", "localhost"}
            return origin_host in hosts | loopback

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/api/health":
                return self.send_json(200, {
                    "status": "ready", "documents": documents, "chunks": len(retriever.chunks),
                    "pdfs": pdfs, "generation_configured": bool(os.environ.get("GEMINI_API_KEY")),
                })
            static = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                      "/style.css": ("style.css", "text/css; charset=utf-8")}
            if path in static:
                filename, content_type = static[path]
                return self.send_bytes(200, (WEB / filename).read_bytes(), content_type)
            if path.startswith("/sources/"):
                doc_id = unquote(path[len("/sources/"):])
                if doc_id in pdfs:
                    return self.send_bytes(200, (DATA / "raw" / (doc_id + ".pdf")).read_bytes(), "application/pdf")
            self.send_json(404, {"error": "Not found"})

        def do_POST(self):
            if not self.same_origin():
                return self.send_json(403, {"error": "Cross-origin requests are not allowed"})
            if self.path != "/api/query":
                return self.send_json(404, {"error": "Not found"})
            if self.headers.get_content_type() != "application/json":
                return self.send_json(415, {"error": "Expected application/json"})
            if not limiter.allow(self.client()):
                return self.send_json(429, {"error": "Too many queries; please wait a minute and try again"})
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
            except (ValueError, TypeError):
                return self.send_json(400, {"error": "Invalid request: enter a question and select a valid document and mode"})
            if not encoder_lock.acquire(timeout=30):
                return self.send_json(503, {"error": "The demo is busy; please try again shortly"})
            try:
                results = retriever.search(question, doc_id=document)
            except Exception:
                LOGGER.error("Unexpected retrieval failure", exc_info=False)
                return self.send_json(500, {"error": "The query could not be completed; check the index"})
            finally:
                encoder_lock.release()
            sources = retriever.evidence(results)
            response = {"results": results, "sources": sources, "answer": None}
            if mode == "answer":
                try:
                    response["answer"] = generate_answer(question, sources)
                except GenerationError as exc:
                    response["generation_error"] = str(exc)
            self.send_json(200, response)

    with ThreadingHTTPServer((host, port), Handler) as server:
        display_host = "localhost" if host in {"0.0.0.0", "127.0.0.1"} else host
        print(f"Legal RAG demo: http://{display_host}:{port} (listening on {host}:{port}) (Ctrl+C to stop)", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
