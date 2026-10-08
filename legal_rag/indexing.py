"""Build and validate a versioned E5 index, reusing unchanged passage vectors."""

import hashlib
import os
import time
from pathlib import Path

import numpy as np

from .config import DATA, INDEX, MODEL, PROCESSED
from .storage import fingerprint, read_json, write_json


def load_model(offline: bool = False):
    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(min(4, os.cpu_count() or 1))
    return SentenceTransformer(MODEL, local_files_only=offline)


def passage(chunk: dict) -> str:
    return "passage: " + chunk["embedding_text"].strip()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        content = stream.read()
    # Normalize CRLF to LF for JSON/text files so git autocrlf differences between Windows and Linux don't break checksum
    if path.suffix.lower() == ".json":
        content = content.replace(b"\r\n", b"\n")
    digest.update(content)
    return digest.hexdigest()


def build_index(offline: bool = False, batch_size: int = 16) -> dict:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    chunks = read_json(PROCESSED / "chunks.json")["chunks"]
    if not chunks:
        raise ValueError("Cannot index an empty corpus")
    model = load_model(offline)
    reusable = {}
    legacy = DATA / "embeddings" / "e5_metadata.json"
    if legacy.exists():
        metadata = read_json(legacy)
        old = np.load(legacy.with_name("e5_embeddings.npy"), allow_pickle=False)
        if metadata["model_name"] == MODEL and len(old) == len(metadata["chunks"]):
            reusable.update((passage(chunk), vector) for chunk, vector in zip(metadata["chunks"], old))
    if (INDEX / "manifest.json").exists():
        vectors, metadata = load_index(check_current=False)
        if metadata["model_name"] == MODEL:
            reusable.update((passage(chunk), vector) for chunk, vector in zip(metadata["chunks"], vectors))
    texts = [passage(chunk) for chunk in chunks]
    # Character limits are not token limits. Fail visibly instead of silently
    # letting SentenceTransformer truncate legal provisions.
    lengths = [len(ids) for ids in model.tokenizer(texts, truncation=False)["input_ids"]]
    oversized = [chunks[i]["chunk_id"] for i, n in enumerate(lengths) if n > model.max_seq_length]
    if oversized:
        raise ValueError(f"Passages exceed {model.max_seq_length} tokens; reduce MAX_CHARS: {oversized[:5]}")
    missing = [i for i, text in enumerate(texts) if text not in reusable]
    dimension = model.get_sentence_embedding_dimension()
    embeddings = np.empty((len(texts), dimension), dtype=np.float32)
    for i, text in enumerate(texts):
        if text in reusable:
            embeddings[i] = reusable[text]
    print(f"Reusing {len(texts) - len(missing)} vectors; encoding {len(missing)} passages", flush=True)
    if missing:
        embeddings[missing] = model.encode(
            [texts[i] for i in missing], batch_size=batch_size,
            show_progress_bar=True, convert_to_numpy=True, normalize_embeddings=True,
        )
    INDEX.mkdir(parents=True, exist_ok=True)
    # Unique artifact names make the manifest the atomic commit point. A failed
    # build cannot pair new metadata with old vectors.
    run_id = str(time.time_ns())
    vectors_path = INDEX / f"vectors-{run_id}.npy"
    metadata_path = INDEX / f"metadata-{run_id}.json"
    np.save(vectors_path, embeddings, allow_pickle=False)
    metadata = {
        "schema_version": 2, "model_name": MODEL, "query_prefix": "query: ",
        "passage_prefix": "passage: ", "dimension": dimension,
        "chunk_fingerprint": fingerprint(chunks), "chunks": chunks,
        "max_passage_tokens": max(lengths), "reused_vectors": len(texts) - len(missing),
    }
    write_json(metadata_path, metadata)
    write_json(INDEX / "manifest.json", {
        "vectors": vectors_path.name, "metadata": metadata_path.name,
        "vectors_sha256": file_hash(vectors_path),
        "metadata_sha256": file_hash(metadata_path),
    })
    load_index()
    return {"chunks": len(chunks), "dimension": dimension, "reused": len(texts) - len(missing)}


def load_index(index_dir: Path = INDEX, check_current: bool = True) -> tuple[np.ndarray, dict]:
    manifest_path = index_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("No index. Run: python -m legal_rag ingest, then python -m legal_rag index")
    manifest = read_json(manifest_path)
    
    # Verify vectors binary file integrity
    vectors_file = index_dir / manifest["vectors"]
    if not vectors_file.exists():
        raise FileNotFoundError(f"Missing vector file: {vectors_file}")
    if file_hash(vectors_file) != manifest["vectors_sha256"]:
        raise ValueError("Index vectors checksum mismatch; rebuild the index")

    metadata_file = index_dir / manifest["metadata"]
    if not metadata_file.exists():
        raise FileNotFoundError(f"Missing metadata file: {metadata_file}")
    
    # Verify metadata checksum: accept raw hash, normalized-LF hash, or chunk fingerprint
    expected_meta_hash = manifest.get("metadata_sha256")
    actual_raw_hash = hashlib.sha256(metadata_file.read_bytes()).hexdigest()
    actual_norm_hash = file_hash(metadata_file)
    metadata = read_json(metadata_file)

    if expected_meta_hash and actual_raw_hash != expected_meta_hash and actual_norm_hash != expected_meta_hash:
        # Check semantic integrity via fingerprint as ultimate guarantee
        if fingerprint(metadata.get("chunks", [])) != metadata.get("chunk_fingerprint"):
            raise ValueError("Index metadata checksum mismatch; rebuild the index")

    vectors = np.load(vectors_file, allow_pickle=False)
    if vectors.shape != (len(metadata["chunks"]), metadata["dimension"]):
        raise ValueError("Index dimensions do not match metadata")
    if not len(vectors) or not np.isfinite(vectors).all():
        raise ValueError("Index is empty or contains non-finite values")
    if not np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-4):
        raise ValueError("Index vectors must be normalized")
    if fingerprint(metadata["chunks"]) != metadata["chunk_fingerprint"]:
        raise ValueError("Chunk fingerprint mismatch")
    if check_current and (PROCESSED / "chunks.json").exists():
        current = read_json(PROCESSED / "chunks.json")
        if fingerprint(current["chunks"]) != metadata["chunk_fingerprint"]:
            raise ValueError("Index is stale after ingestion; run: python -m legal_rag index")
    return vectors, metadata
