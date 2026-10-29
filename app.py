"""Hugging Face Space entry point: Gradio SDK on free ZeroGPU hardware.

Docker Spaces need a paid plan; free accounts can host ZeroGPU Gradio Spaces.
Query encoding for one question takes ~100 ms on CPU, so retrieval stays on CPU
and never spends visitors' daily GPU quota. Run locally with ``python app.py``.
"""

# ZeroGPU requires `spaces` to be imported before torch.
try:
    import spaces
except ImportError:  # Local runs do not need the ZeroGPU runtime.
    spaces = None

import html
import os
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("LEGAL_RAG_DEVICE", "cpu")

import gradio as gr  # noqa: E402

from legal_rag.config import DATA  # noqa: E402
from legal_rag.generation import GenerationError, generate_answer  # noqa: E402
from legal_rag.retrieval import Retriever  # noqa: E402

if spaces is not None:
    @spaces.GPU(duration=1)
    def zerogpu_registration():
        """ZeroGPU refuses to start a Space without one decorated function."""

ALL_DOCUMENTS = "All documents"
SEARCH, ANSWER = "Search sources", "Answer with Gemini"
EXAMPLES = [
    ["Kapan pekerja dengan hubungan kerja berdasarkan PKWT berhak memperoleh uang kompensasi?"],
    ["Variabel apa saja yang dipertimbangkan dalam formula penyesuaian Upah minimum?"],
    ["Apa bentuk Perizinan Berusaha bagi kegiatan usaha dengan tingkat Risiko tinggi?"],
    ["Berapa batas maksimum keseluruhan jangka waktu PKWT termasuk perpanjangannya?"],
]

retriever = Retriever.load()
DOCUMENTS = sorted({chunk["doc_id"] for chunk in retriever.chunks})
PDFS = {doc: DATA / "raw" / (doc + ".pdf") for doc in DOCUMENTS if (DATA / "raw" / (doc + ".pdf")).exists()}
GENERATION_READY = bool(os.environ.get("GEMINI_API_KEY"))


def location(source: dict) -> str:
    ayat = f" ayat ({source['ayat']})" if source.get("ayat") else ""
    return f"{source['doc_id']} · Pasal {source['pasal']}{ayat}"


def render_sources(sources: list[dict], scores: dict[str, float]) -> str:
    if not sources:
        return '<p class="la-empty">No passages matched this scope.</p>'
    cards = []
    for source in sources:
        page = source.get("page_start") or 1
        page_label = f"PDF page {page}"
        if source["doc_id"] in PDFS:
            page_label = (f'<a href="/gradio_api/file={quote(PDFS[source["doc_id"]].as_posix())}#page={page}" '
                          f'target="_blank" rel="noopener">{page_label} ↗</a>')
        score = scores.get(source["chunk_id"])
        badge = f'<span class="la-score">score {score:.3f}</span>' if score is not None else ""
        cards.append(
            f'<details class="la-card" id="la-{source["source_id"]}"{" open" if len(cards) < 2 else ""}>'
            f'<summary><span class="la-id">{source["source_id"]}</span>'
            f'<span class="la-loc">{html.escape(location(source))}</span>{badge}</summary>'
            f'<div class="la-meta">{page_label}</div>'
            f'<p>{html.escape(source["text"])}</p></details>'
        )
    return "".join(cards)


def render_answer(answer: dict) -> str:
    if answer["status"] == "insufficient_evidence":
        body = "**The retrieved passages do not answer this question.**"
    else:
        body = "\n".join(
            f"- {statement['text']} " + " ".join(f"`{sid}`" for sid in statement["source_ids"]
                                                 if f"[{sid}]" not in statement["text"])
            for statement in answer["statements"]
        )
    limitations = answer.get("limitations", "").strip()
    footer = f"\n\n> {limitations}" if limitations else ""
    return f"{body}{footer}\n\n<sub>Model: {answer.get('model', 'Gemini')}</sub>"


def search(question: str, document: str):
    question = (question or "").strip()
    if not question:
        raise gr.Error("Enter a question first.")
    if len(question) > 2000:
        raise gr.Error("Keep the question under 2,000 characters.")
    doc_id = None if document == ALL_DOCUMENTS else document
    results = retriever.search(question, doc_id=doc_id)
    sources = retriever.evidence(results)
    scores = {row["chunk"]["chunk_id"]: row["score"] for row in results}
    status = f"Retrieved {len(results)} articles · {len(sources)} passages"
    return render_sources(sources, scores), sources, status, gr.update(value="", visible=False)


def answer(question: str, mode: str, sources: list[dict]):
    if mode != ANSWER:
        return gr.update(value="", visible=False)
    try:
        return gr.update(value=render_answer(generate_answer(question.strip(), sources)), visible=True)
    except GenerationError as exc:
        return gr.update(value=f"**Answer unavailable:** {exc}", visible=True)


CSS = """
.la-card { border: 1px solid var(--border-color-primary); border-radius: 10px;
           padding: 10px 14px; margin-bottom: 10px; background: var(--block-background-fill); }
.la-card summary { cursor: pointer; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.la-id { font-family: var(--font-mono); font-weight: 600; color: var(--color-accent); }
.la-loc { font-weight: 600; }
.la-score { margin-left: auto; font-size: 12px; opacity: .7; font-family: var(--font-mono); }
.la-meta { font-size: 12px; opacity: .75; margin: 6px 0; }
.la-card p { white-space: pre-wrap; line-height: 1.55; margin: 0; }
.la-empty { opacity: .7; }
footer { display: none !important; }
"""

with gr.Blocks(title="Legal Atlas") as demo:
    gr.Markdown(
        "# ⚖️ Legal Atlas\n"
        "Hybrid retrieval (multilingual-e5 + BM25) over Indonesian regulations with "
        "article-level citations. Corpus: PP 35/2021 · PP 5/2021 · PP 51/2023.  \n"
        "<sub>Portfolio demo over a small, non-consolidated corpus — not legal advice.</sub>"
    )
    with gr.Row():
        with gr.Column(scale=3):
            question = gr.Textbox(label="Question", lines=2, max_length=2000,
                                  placeholder="Tanyakan sesuatu tentang PKWT, upah minimum, atau perizinan berusaha…")
        with gr.Column(scale=1, min_width=220):
            document = gr.Dropdown([ALL_DOCUMENTS, *DOCUMENTS], value=ALL_DOCUMENTS, label="Scope")
            mode = gr.Radio([SEARCH, ANSWER], value=ANSWER if GENERATION_READY else SEARCH, label="Mode",
                            interactive=GENERATION_READY,
                            info=None if GENERATION_READY else "Answers need the GEMINI_API_KEY secret")
    submit = gr.Button("Ask", variant="primary")
    gr.Examples(EXAMPLES, inputs=question)
    status = gr.Markdown()
    answer_box = gr.Markdown(visible=False, label="Answer")
    sources_html = gr.HTML()
    sources_state = gr.State([])

    # Encoding shares one model, so it is serialized; Gemini calls may overlap.
    gr.on([submit.click, question.submit], search, [question, document],
          [sources_html, sources_state, status, answer_box], api_name="search",
          concurrency_limit=1, concurrency_id="encoder").success(
        answer, [question, mode, sources_state], answer_box, api_name="answer", concurrency_limit=4)

if __name__ == "__main__":
    demo.queue(max_size=32).launch(css=CSS, theme=gr.themes.Soft(), allowed_paths=[str(DATA / "raw")])
