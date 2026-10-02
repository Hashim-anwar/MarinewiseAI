from pathlib import Path
import pickle

import faiss
from sentence_transformers import SentenceTransformer


MODEL_NAME = "all-MiniLM-L6-v2"


def load_embedding_model() -> SentenceTransformer:
    """Load the sentence-transformer embedding model."""
    return SentenceTransformer(MODEL_NAME)


def build_faiss_index(chunks: list[dict], index_folder: Path) -> None:
    """Create and save a FAISS semantic search index."""
    if not chunks:
        raise ValueError("No chunks were provided.")

    model = load_embedding_model()

    texts = [chunk["text"] for chunk in chunks]

    embeddings = model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    dimension = embeddings.shape[1]

    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings.astype("float32"))

    index_folder.mkdir(parents=True, exist_ok=True)

    faiss.write_index(
        index,
        str(index_folder / "faiss.index"),
    )

    with open(index_folder / "chunks.pkl", "wb") as file:
        pickle.dump(chunks, file)


def load_faiss_index(
    index_folder: Path,
) -> tuple[faiss.Index, list[dict]]:
    """Load the FAISS index and stored chunks."""
    index = faiss.read_index(
        str(index_folder / "faiss.index")
    )

    with open(index_folder / "chunks.pkl", "rb") as file:
        chunks = pickle.load(file)

    return index, chunks


def search_faiss(
    index: faiss.Index,
    chunks: list[dict],
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """Search the FAISS index and return the best matching chunks."""
    model = load_embedding_model()

    query_embedding = model.encode(
        [query],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    scores, positions = index.search(
        query_embedding.astype("float32"),
        top_k,
    )

    results = []

    for score, position in zip(scores[0], positions[0]):
        if position < 0:
            continue

        result = chunks[position].copy()
        result["faiss_score"] = float(score)

        results.append(result)

    return results
