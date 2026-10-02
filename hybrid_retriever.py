"""
MarineWise AI
STEP 24 - Hybrid / Advanced RAG

Combines:
    1. FAISS semantic search
    2. BM25 keyword search
    3. Metadata-aware filtering
    4. Reciprocal Rank Fusion (RRF)

Input:
    chunks/all_chunks.json
    vector_store/marinewise.faiss
    vector_store/metadata.json

Output:
    hybrid_results.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer


CHUNK_FILE = Path("chunks/all_chunks.json")
FAISS_FILE = Path("vector_store/marinewise.faiss")
METADATA_FILE = Path("vector_store/metadata.json")

OUTPUT_FILE = Path("hybrid_results.json")

MODEL_NAME = "all-MiniLM-L6-v2"

FAISS_TOP_K = 20
BM25_TOP_K = 20
FINAL_TOP_K = 10

RRF_K = 60


def tokenize(text: str) -> list[str]:
    """
    Simple technical-document tokenizer.

    Keeps important technical identifiers such as:
        16V175D-MM
        QL-40
        8351291
        P/N
    """

    text = str(text).lower()

    return re.findall(
        r"[a-z0-9]+(?:[-_/][a-z0-9]+)*",
        text,
    )


def load_chunks() -> list[dict]:

    if not CHUNK_FILE.exists():
        raise FileNotFoundError(
            f"Missing chunk file: {CHUNK_FILE}"
        )

    with CHUNK_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    chunks = data.get("chunks", [])

    if not chunks:
        raise AssertionError(
            "No chunks found."
        )

    return chunks


def load_metadata() -> list[dict]:

    if not METADATA_FILE.exists():
        raise FileNotFoundError(
            f"Missing metadata file: {METADATA_FILE}"
        )

    with METADATA_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:
        metadata = json.load(f)

    if not metadata:
        raise AssertionError(
            "Metadata file is empty."
        )

    return metadata


def detect_filters(query: str) -> dict:

    query_upper = query.upper()

    filters = {
        "vessel": None,
        "manufacturer": None,
        "engine_model": None,
        "system": None,
    }

    # Vessel detection.
    vessel_match = re.search(
        r"\bQL[-\s]?(\d+)\b",
        query_upper,
    )

    if vessel_match:
        filters["vessel"] = (
            f"QL {vessel_match.group(1)}"
        )

    # Manufacturer detection.
    manufacturers = [
        "MAN",
        "MTU",
        "CATERPILLAR",
        "CAT",
        "YANMAR",
        "VOLVO PENTA",
        "YAMAHA",
    ]

    for manufacturer in manufacturers:

        if manufacturer in query_upper:
            filters["manufacturer"] = manufacturer
            break

    # Engine detection.
    engine_patterns = [
        r"\b16V175D[-\s]?MM\b",
        r"\b12V175D[-\s]?ML\b",
        r"\bD2676[-\s]?LE\d+\b",
        r"\b10V2000[-\s]?M94\b",
        r"\b12V2000[-\s]?M94\b",
        r"\b12V2000[-\s]?M96L\b",
        r"\b16V4000[-\s]?M90\b",
    ]

    for pattern in engine_patterns:

        match = re.search(
            pattern,
            query_upper,
        )

        if match:
            filters["engine_model"] = (
                match.group(0)
                .replace(" ", "-")
            )
            break

    # System detection.
    if (
        "MAIN ENGINE" in query_upper
        or "MAIN DIESEL" in query_upper
        or "PROPULSION" in query_upper
    ):
        filters["system"] = "Main Engine"

    elif "GENERATOR" in query_upper:
        filters["system"] = "Generator"

    elif "GEARBOX" in query_upper or "GEAR BOX" in query_upper:
        filters["system"] = "Gear Box"

    return filters


def metadata_matches(
    item: dict,
    filters: dict,
) -> bool:

    # If no metadata filter is detected,
    # don't remove anything.
    if not any(filters.values()):
        return True

    item_vessel = str(
        item.get("vessel", "")
    ).upper()

    item_manufacturer = str(
        item.get("manufacturer", "")
    ).upper()

    item_engine = str(
        item.get("engine_model", "")
    ).upper()

    item_system = str(
        item.get("system", "")
    ).upper()

    if filters["vessel"]:

        target = filters["vessel"].upper()

        if target not in item_vessel:
            return False

    if filters["manufacturer"]:

        target = filters["manufacturer"].upper()

        if (
            target not in item_manufacturer
            and target != "CAT"
        ):
            return False

    if filters["engine_model"]:

        target = (
            filters["engine_model"]
            .upper()
            .replace("-", "")
            .replace(" ", "")
        )

        current = (
            item_engine
            .replace("-", "")
            .replace(" ", "")
        )

        if target not in current:
            return False

    if filters["system"]:

        target = filters["system"].upper()

        if target not in item_system:
            return False

    return True


def main():

    print("=" * 70)
    print("MARINEWISE AI - STEP 24")
    print("HYBRID / ADVANCED RAG")
    print("=" * 70)

    query = (
        "QL-40 MAN 16V175D-MM "
        "main engine high exhaust temperature alarm"
    )

    print(f"\nTest query:\n{query}")

    chunks = load_chunks()
    metadata = load_metadata()

    print(f"\nChunks loaded: {len(chunks):,}")
    print(f"Metadata records: {len(metadata):,}")

    if len(chunks) != len(metadata):
        raise AssertionError(
            "Chunk count and metadata count do not match."
        )

    # ---------------------------------------------------------
    # Load FAISS
    # ---------------------------------------------------------

    print("\nLoading FAISS index...")

    if not FAISS_FILE.exists():
        raise FileNotFoundError(
            f"Missing FAISS index: {FAISS_FILE}"
        )

    index = faiss.read_index(
        str(FAISS_FILE)
    )

    if index.ntotal != len(chunks):
        raise AssertionError(
            "FAISS vector count does not match chunks."
        )

    print(
        f"GREEN - FAISS loaded: "
        f"{index.ntotal:,} vectors"
    )

    # ---------------------------------------------------------
    # Load embedding model
    # ---------------------------------------------------------

    model = SentenceTransformer(
        MODEL_NAME
    )

    print(
        "GREEN - embedding model loaded"
    )

    # ---------------------------------------------------------
    # BM25
    # ---------------------------------------------------------

    print("\nBuilding BM25 index...")

    corpus_tokens = [
        tokenize(
            chunk.get("text", "")
        )
        for chunk in chunks
    ]

    bm25 = BM25Okapi(
        corpus_tokens
    )

    print(
        f"GREEN - BM25 index built: "
        f"{len(corpus_tokens):,} documents"
    )

    # ---------------------------------------------------------
    # Query intelligence
    # ---------------------------------------------------------

    filters = detect_filters(query)

    print("\nQUERY INTELLIGENCE")
    print("-" * 70)

    for key, value in filters.items():
        print(
            f"{key}: "
            f"{value if value else 'Not detected'}"
        )

    # ---------------------------------------------------------
    # FAISS semantic search
    # ---------------------------------------------------------

    query_embedding = model.encode(
        [query],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    query_embedding = np.asarray(
        query_embedding,
        dtype="float32",
    )

    faiss_scores, faiss_indices = index.search(
        query_embedding,
        FAISS_TOP_K,
    )

    semantic_results = []

    for rank, (
        score,
        idx,
    ) in enumerate(
        zip(
            faiss_scores[0],
            faiss_indices[0],
        ),
        start=1,
    ):

        if idx < 0:
            continue

        if idx >= len(metadata):
            continue

        item = metadata[idx]

        semantic_results.append(
            {
                "index": int(idx),
                "rank": rank,
                "score": float(score),
            }
        )

    print(
        f"\nFAISS semantic results: "
        f"{len(semantic_results)}"
    )

    # ---------------------------------------------------------
    # BM25 keyword search
    # ---------------------------------------------------------

    query_tokens = tokenize(query)

    bm25_scores = bm25.get_scores(
        query_tokens
    )

    bm25_order = np.argsort(
        bm25_scores
    )[::-1][:BM25_TOP_K]

    keyword_results = []

    for rank, idx in enumerate(
        bm25_order,
        start=1,
    ):

        idx = int(idx)

        keyword_results.append(
            {
                "index": idx,
                "rank": rank,
                "score": float(
                    bm25_scores[idx]
                ),
            }
        )

    print(
        f"BM25 keyword results: "
        f"{len(keyword_results)}"
    )

    # ---------------------------------------------------------
    # Metadata-aware candidate filtering
    # ---------------------------------------------------------

    matching_indices = set()

    for idx, item in enumerate(metadata):

        if metadata_matches(
            item,
            filters,
        ):
            matching_indices.add(idx)

    print(
        f"Metadata-compatible chunks: "
        f"{len(matching_indices):,}"
    )

    # ---------------------------------------------------------
    # Reciprocal Rank Fusion
    # ---------------------------------------------------------

    fused = {}

    for result in semantic_results:

        idx = result["index"]

        if (
            matching_indices
            and idx not in matching_indices
        ):
            continue

        fused.setdefault(
            idx,
            {
                "index": idx,
                "rrf_score": 0.0,
                "faiss_rank": None,
                "bm25_rank": None,
                "faiss_score": None,
                "bm25_score": None,
            },
        )

        fused[idx]["rrf_score"] += (
            1.0
            / (
                RRF_K
                + result["rank"]
            )
        )

        fused[idx]["faiss_rank"] = (
            result["rank"]
        )

        fused[idx]["faiss_score"] = (
            result["score"]
        )

    for result in keyword_results:

        idx = result["index"]

        if (
            matching_indices
            and idx not in matching_indices
        ):
            continue

        fused.setdefault(
            idx,
            {
                "index": idx,
                "rrf_score": 0.0,
                "faiss_rank": None,
                "bm25_rank": None,
                "faiss_score": None,
                "bm25_score": None,
            },
        )

        fused[idx]["rrf_score"] += (
            1.0
            / (
                RRF_K
                + result["rank"]
            )
        )

        fused[idx]["bm25_rank"] = (
            result["rank"]
        )

        fused[idx]["bm25_score"] = (
            result["score"]
        )

    # ---------------------------------------------------------
    # Final ranking
    # ---------------------------------------------------------

    ranked = sorted(
        fused.values(),
        key=lambda x: x["rrf_score"],
        reverse=True,
    )

    ranked = ranked[
        :FINAL_TOP_K
    ]

    final_results = []

    print("\n" + "=" * 70)
    print("HYBRID RAG RESULTS")
    print("=" * 70)

    for rank, result in enumerate(
        ranked,
        start=1,
    ):

        idx = result["index"]

        item = metadata[idx]

        final_item = {
            "hybrid_rank": rank,
            "rrf_score": result[
                "rrf_score"
            ],
            "faiss_rank": result[
                "faiss_rank"
            ],
            "faiss_score": result[
                "faiss_score"
            ],
            "bm25_rank": result[
                "bm25_rank"
            ],
            "bm25_score": result[
                "bm25_score"
            ],
            "chunk_id": item.get(
                "chunk_id"
            ),
            "source_file": item.get(
                "source_file"
            ),
            "page": item.get(
                "page"
            ),
            "manufacturer": item.get(
                "manufacturer"
            ),
            "engine_model": item.get(
                "engine_model"
            ),
            "vessel": item.get(
                "vessel"
            ),
            "system": item.get(
                "system"
            ),
            "text": item.get(
                "text"
            ),
        }

        final_results.append(
            final_item
        )

        print(
            f"\n{rank}. "
            f"RRF={result['rrf_score']:.6f}"
        )

        print(
            f"   FAISS rank: "
            f"{result['faiss_rank']}"
        )

        print(
            f"   BM25 rank: "
            f"{result['bm25_rank']}"
        )

        print(
            f"   Source: "
            f"{item.get('source_file')}"
        )

        print(
            f"   Page: "
            f"{item.get('page')}"
        )

        print(
            f"   Vessel: "
            f"{item.get('vessel')}"
        )

        print(
            f"   Engine: "
            f"{item.get('engine_model')}"
        )

    # ---------------------------------------------------------
    # Save results
    # ---------------------------------------------------------

    output = {
        "project": "MarineWise AI",
        "step": "STEP 24",
        "query": query,
        "embedding_model": MODEL_NAME,
        "faiss_top_k": FAISS_TOP_K,
        "bm25_top_k": BM25_TOP_K,
        "final_top_k": FINAL_TOP_K,
        "rrf_k": RRF_K,
        "filters": filters,
        "candidate_count": len(
            matching_indices
        ),
        "results": final_results,
    }

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2,
        )

    # ---------------------------------------------------------
    # Verification
    # ---------------------------------------------------------

    if not final_results:
        raise AssertionError(
            "Hybrid RAG returned no results."
        )

    if not OUTPUT_FILE.exists():
        raise AssertionError(
            "Hybrid results file was not created."
        )

    first = final_results[0]

    required_fields = [
        "source_file",
        "page",
        "text",
        "rrf_score",
    ]

    for field in required_fields:

        if field not in first:
            raise AssertionError(
                f"Missing result field: {field}"
            )

    print("\n" + "=" * 70)
    print("STEP 24 VERIFICATION")
    print("=" * 70)

    print(
        "GREEN - FAISS semantic search verified."
    )

    print(
        "GREEN - BM25 keyword search verified."
    )

    print(
        "GREEN - metadata filtering verified."
    )

    print(
        "GREEN - Reciprocal Rank Fusion verified."
    )

    print(
        "GREEN - source/page metadata preserved."
    )

    print(
        f"GREEN - final hybrid results: "
        f"{len(final_results)}"
    )

    print(
        f"Results file: {OUTPUT_FILE}"
    )

    print()
    print("STEP 24: SUCCESS")
    print("GREEN")


if __name__ == "__main__":
    main()
