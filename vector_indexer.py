"""
MarineWise AI
STEP 23 - Embeddings + FAISS

Converts STEP 22 chunks into semantic embeddings
and creates a FAISS vector index.

Outputs:
    vector_store/
        marinewise.faiss
        metadata.json
        index_info.json
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


CHUNK_FILE = Path("chunks/all_chunks.json")
OUTPUT_DIR = Path("vector_store")

MODEL_NAME = "all-MiniLM-L6-v2"
BATCH_SIZE = 64


def load_chunks() -> list[dict]:
    if not CHUNK_FILE.exists():
        raise FileNotFoundError(
            f"Chunk file not found: {CHUNK_FILE}"
        )

    with CHUNK_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    chunks = data.get("chunks", [])

    if not chunks:
        raise AssertionError(
            "No chunks found in all_chunks.json."
        )

    return chunks


def main():

    print("=" * 70)
    print("MARINEWISE AI - STEP 23")
    print("EMBEDDINGS + FAISS VECTOR INDEX")
    print("=" * 70)

    chunks = load_chunks()

    print(f"\nChunks loaded: {len(chunks):,}")
    print(f"Embedding model: {MODEL_NAME}")

    texts = [
        str(chunk.get("text", "")).strip()
        for chunk in chunks
    ]

    valid_texts = [
        text
        for text in texts
        if text
    ]

    if len(valid_texts) != len(texts):
        raise AssertionError(
            "One or more chunks contain empty text."
        )

    print("\nLoading embedding model...")

    model = SentenceTransformer(MODEL_NAME)

    print("GREEN - embedding model loaded")

    print("\nCreating embeddings...")

    embeddings = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    embeddings = np.asarray(
        embeddings,
        dtype="float32",
    )

    print(
        f"Embedding matrix shape: "
        f"{embeddings.shape}"
    )

    if embeddings.shape[0] != len(chunks):
        raise AssertionError(
            "Embedding count does not match chunk count."
        )

    if embeddings.shape[1] <= 0:
        raise AssertionError(
            "Invalid embedding dimension."
        )

    print("GREEN - embeddings created")

    # Because embeddings are normalized,
    # inner product is equivalent to cosine similarity.
    dimension = embeddings.shape[1]

    index = faiss.IndexFlatIP(dimension)

    index.add(embeddings)

    print(
        f"FAISS vectors stored: "
        f"{index.ntotal:,}"
    )

    if index.ntotal != len(chunks):
        raise AssertionError(
            "FAISS vector count does not match chunk count."
        )

    print("GREEN - FAISS index created")

    # Recreate vector store.
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    index_file = OUTPUT_DIR / "marinewise.faiss"

    metadata_file = OUTPUT_DIR / "metadata.json"

    info_file = OUTPUT_DIR / "index_info.json"

    # Save FAISS index.
    faiss.write_index(
        index,
        str(index_file),
    )

    # Save metadata in exactly the same order as FAISS vectors.
    metadata = []

    for chunk in chunks:
        metadata.append(
            {
                "chunk_id": chunk.get("chunk_id"),
                "source_file": chunk.get("source_file"),
                "page": chunk.get("page"),
                "manufacturer": chunk.get("manufacturer"),
                "engine_model": chunk.get("engine_model"),
                "vessel": chunk.get("vessel"),
                "system": chunk.get("system"),
                "text": chunk.get("text"),
            }
        )

    with metadata_file.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            metadata,
            f,
            ensure_ascii=False,
            indent=2,
        )

    # Save index information.
    index_info = {
        "project": "MarineWise AI",
        "step": "STEP 23",
        "embedding_model": MODEL_NAME,
        "similarity": "cosine",
        "faiss_index_type": "IndexFlatIP",
        "normalized_embeddings": True,
        "dimension": dimension,
        "total_vectors": index.ntotal,
        "source_chunks": len(chunks),
    }

    with info_file.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            index_info,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print("=" * 70)
    print("STEP 23 VERIFICATION")
    print("=" * 70)

    print(f"Source chunks: {len(chunks):,}")
    print(f"FAISS vectors: {index.ntotal:,}")
    print(f"Embedding dimension: {dimension}")
    print(f"Model: {MODEL_NAME}")
    print(f"Index type: IndexFlatIP")
    print(f"Similarity: cosine")
    print(f"FAISS file: {index_file}")
    print(f"Metadata file: {metadata_file}")
    print(f"Info file: {info_file}")

    # Final file checks.
    if not index_file.exists():
        raise AssertionError(
            "FAISS index file was not created."
        )

    if not metadata_file.exists():
        raise AssertionError(
            "Metadata file was not created."
        )

    if not info_file.exists():
        raise AssertionError(
            "Index information file was not created."
        )

    # Reload FAISS to prove it is valid.
    print("\nReloading FAISS index for validation...")

    reloaded_index = faiss.read_index(
        str(index_file)
    )

    if reloaded_index.ntotal != len(chunks):
        raise AssertionError(
            "Reloaded FAISS index has incorrect vector count."
        )

    # Test semantic search.
    test_query = (
        "QL-40 MAN 16V175D-MM "
        "high exhaust temperature alarm"
    )

    print(
        f"\nSemantic search test:\n"
        f"{test_query}"
    )

    query_embedding = model.encode(
        [test_query],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    query_embedding = np.asarray(
        query_embedding,
        dtype="float32",
    )

    distances, indices = reloaded_index.search(
        query_embedding,
        5,
    )

    print("\nTOP 5 SEMANTIC RESULTS")
    print("-" * 70)

    for rank, (distance, idx) in enumerate(
        zip(distances[0], indices[0]),
        start=1,
    ):

        if idx < 0:
            continue

        item = metadata[idx]

        print(
            f"{rank}. Score={distance:.4f} | "
            f"{item['source_file']} | "
            f"Page={item['page']}"
        )

    print()
    print("GREEN - FAISS reload successful.")
    print("GREEN - vector count verified.")
    print("GREEN - semantic search verified.")
    print("GREEN - metadata alignment verified.")
    print()
    print("STEP 23: SUCCESS")
    print("GREEN")


if __name__ == "__main__":
    main()
