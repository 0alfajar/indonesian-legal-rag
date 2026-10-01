"""Offline regression tests for failures found in the original project."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from legal_rag.chunking import create_chunks, split_text
from legal_rag.evaluation import metrics
from legal_rag.generation import GenerationError, generate_answer, validate_answer
from legal_rag.indexing import file_hash, load_index
from legal_rag.parser import item_text, ordered_items, parse_document
from legal_rag.retrieval import Retriever
from legal_rag.storage import fingerprint, write_json

Path(__file__).with_name(".tmp").mkdir(exist_ok=True)


def text_item(text, page=1, top=700, label="text", marker=""):
    return {"text": text, "label": label, "marker": marker,
            "prov": [{"page_no": page, "bbox": {"t": top, "coord_origin": "BOTTOMLEFT"}}]}


def parse_items(items):
    with tempfile.TemporaryDirectory(dir=Path(__file__).parent / ".tmp") as directory:
        path = Path(directory) / "fixture.json"
        write_json(path, {"texts": items})
        with contextlib.redirect_stdout(io.StringIO()):
            return parse_document(path)


class ParsingTests(unittest.TestCase):
    def test_trailing_paragraph_marker_repaired_only_for_list_items(self):
        self.assertEqual(item_text(text_item("A complete sentence. (1)", label="list_item")), "(1) A complete sentence.")
        self.assertEqual(item_text(text_item("According to ayat (1)")), "According to ayat (1)")

    def test_reading_order_and_preview_footers(self):
        items = [text_item("(3) Third.", top=500), text_item("(2) Second.", top=600),
                 text_item("(4) Preview...", top=50, label="page_footer")]
        self.assertEqual([i["text"] for i in ordered_items({"texts": items})], ["(2) Second.", "(3) Third."])

    def test_unassigned_article_text_survives_chunking(self):
        doc = parse_items([text_item("Pasal 28", top=750), text_item("Important opening provision.", top=700),
                           text_item("(2) Second provision.", top=650)])
        chunks = create_chunks(doc)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["text"], "Important opening provision.")
        self.assertIsNone(chunks[0]["ayat"])

    def test_misordered_trailing_markers_become_separate_ayat(self):
        doc = parse_items([text_item("Pasal 28", top=750),
                           text_item("First provision. (1)", top=700, label="list_item"),
                           text_item("(3) Third provision.", top=500),
                           text_item("Second provision. (2)", top=600, label="list_item")])
        self.assertEqual([a["number"] for a in doc["sections"][0]["ayat"]], [1, 2, 3])

    def test_distinct_repeated_ayat_text_is_not_discarded(self):
        doc = parse_items([text_item("Pasal 1", top=750), text_item("(1) First part.", top=700),
                           text_item("(1) Distinct continuation.", top=600)])
        chunk = create_chunks(doc)[0]
        self.assertIn("First part.", chunk["text"])
        self.assertIn("Distinct continuation.", chunk["text"])
        self.assertTrue(doc["validation"]["warnings"])

    def test_explanation_and_amendment_instructions_are_separate(self):
        doc = parse_items([text_item("Pasal 1", top=750), text_item("Original rule.", top=700),
                           text_item("Ketentuan Pasal 2 diubah sehingga berbunyi sebagai berikut:", top=650),
                           text_item("Pasal 2", top=600), text_item("Changed rule.", top=550),
                           text_item("PENJELASAN", top=500), text_item("Pasal 1", top=450)])
        self.assertEqual(len(doc["sections"]), 2)
        self.assertNotIn("diubah", doc["sections"][0]["text"])
        self.assertEqual(len(doc["amendment_instructions"]), 1)
        self.assertEqual(len(doc["explanation"]), 2)

    def test_long_sentence_has_hard_bound_and_preserves_words(self):
        text = "word " * 1000
        pieces = split_text(text, 100)
        self.assertTrue(all(len(p) <= 100 for p in pieces))
        self.assertEqual(" ".join(pieces), text.strip())
        self.assertEqual("".join(split_text("x" * 205, 100)), "x" * 205)


class FakeModel:
    def __init__(self):
        self.received = []

    def encode(self, texts, **_kwargs):
        self.received.extend(texts)
        return np.array([[1., 0.] for _ in texts])


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.model = FakeModel()
        self.chunks = [{"chunk_id": str(i), "doc_id": "doc", "pasal": p,
                        "text": f"rule {i}", "embedding_text": f"rule {i}"}
                       for i, p in enumerate(["1", "1", "2"])]
        self.retriever = Retriever(np.array([[1., 0.], [.9, .1], [.8, .2]]), self.chunks, self.model)

    def test_query_prefix_and_article_diversity(self):
        results = self.retriever.search(" rule ", method="dense")
        self.assertEqual(self.model.received, ["query: rule"])
        self.assertEqual([r["chunk"]["pasal"] for r in results], ["1", "2"])

    def test_explicit_article_filter(self):
        results = self.retriever.search("rule", method="dense", pasal="2")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["chunk"]["pasal"], "2")
        self.assertEqual(self.retriever.search("rule", doc_id="absent"), [])

    def test_invalid_queries_and_top_k(self):
        for query, count in [("", 5), ("rule", 0), ("rule", -1)]:
            with self.assertRaises(ValueError):
                self.retriever.search(query, count)

    def test_evidence_retains_hits_before_expanding_neighbors(self):
        results = self.retriever.search("rule", method="dense")
        sources = self.retriever.evidence(results)
        self.assertEqual([s["chunk_id"] for s in sources[:2]], ["0", "2"])
        self.assertEqual(len({s["source_id"] for s in sources}), len(sources))

    def test_metrics_are_truncated_at_five(self):
        result = metrics([1, 2, None, 6])
        self.assertEqual(result["hit@5"], .5)
        self.assertEqual(result["mrr@5"], .375)


class GenerationTests(unittest.TestCase):
    sources = [{"source_id": "S1", "text": "Evidence"}]

    def test_valid_citations(self):
        result = {"status": "answered", "statements": [{"text": "Supported statement", "source_ids": ["S1"]}], "limitations": ""}
        self.assertEqual(validate_answer(result, self.sources), result)

    def test_unknown_and_missing_citations_rejected(self):
        for citations in ([], ["S9"], [1], None):
            with self.assertRaises(GenerationError):
                validate_answer({"status": "answered", "statements": [{"text": "Claim", "source_ids": citations}], "limitations": ""}, self.sources)

    def test_insufficient_evidence_cannot_carry_claims(self):
        with self.assertRaises(GenerationError):
            validate_answer({"status": "insufficient_evidence", "statements": [{"text": "Claim", "source_ids": ["S1"]}], "limitations": ""}, self.sources)

    def test_empty_context_does_not_call_provider(self):
        with patch("legal_rag.generation.urlopen") as request:
            self.assertEqual(generate_answer("Question", [])["status"], "insufficient_evidence")
            request.assert_not_called()

    def test_missing_key_has_actionable_message(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": ""}):
            with self.assertRaisesRegex(GenerationError, "GEMINI_API_KEY"):
                generate_answer("Question", self.sources)

    def test_gemini_request_and_response_contract(self):
        answer = {"status": "answered", "statements": [{"text": "Claim", "source_ids": ["S1"]}], "limitations": ""}
        response = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(answer)}]}}]}
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "gemini-test"}):
            with patch("legal_rag.generation.urlopen") as request:
                request.return_value.__enter__.return_value = io.BytesIO(json.dumps(response).encode())
                result = generate_answer("Question", self.sources)
                self.assertEqual(result["status"], "answered")
                sent = request.call_args.args[0]
                self.assertNotIn("test-key", sent.full_url)
                self.assertIn("responseJsonSchema", json.loads(sent.data)["generationConfig"])

    def test_model_roll_on_503(self):
        from urllib.error import HTTPError
        answer = {"status": "answered", "statements": [{"text": "Claim", "source_ids": ["S1"]}], "limitations": ""}
        response = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(answer)}]}}]}
        err = HTTPError(url="http://fake", code=503, msg="Overloaded", hdrs={}, fp=io.BytesIO(b"{}"))
        ok = io.BytesIO(json.dumps(response).encode())

        class MockResponse:
            def __enter__(self):
                return ok
            def __exit__(self, *args):
                pass

        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "gemini-m1,gemini-m2"}):
            with patch("legal_rag.generation.urlopen", side_effect=[err, MockResponse()]) as request:
                result = generate_answer("Question", self.sources)
                self.assertEqual(result["status"], "answered")
                self.assertEqual(request.call_count, 2)


class IndexTests(unittest.TestCase):
    def test_corrupt_index_fails_before_retrieval(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent / ".tmp") as directory:
            path = Path(directory)
            vectors = path / "vectors.npy"
            metadata = path / "metadata.json"
            chunks = [{"chunk_id": "1"}]
            np.save(vectors, np.array([[1., 0.]], dtype=np.float32))
            write_json(metadata, {"dimension": 2, "chunks": chunks, "chunk_fingerprint": fingerprint(chunks)})
            write_json(path / "manifest.json", {"vectors": vectors.name, "metadata": metadata.name,
                       "vectors_sha256": file_hash(vectors), "metadata_sha256": file_hash(metadata)})
            load_index(path, check_current=False)
            vectors.write_bytes(b"broken")
            with self.assertRaisesRegex(ValueError, "checksum"):
                load_index(path, check_current=False)


if __name__ == "__main__":
    unittest.main()
