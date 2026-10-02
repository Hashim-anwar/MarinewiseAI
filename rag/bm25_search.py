from rank_bm25 import BM25Okapi


def tokenize(text: str) -> list[str]:
    """Convert text into simple lowercase search tokens."""
    return text.lower().split()


def build_bm25(chunks: list[dict]) -> BM25Okapi:
    """Build a BM25 search index from text chunks."""
    tokenized_chunks = [
        tokenize(chunk["text"])
        for chunk in chunks
    ]

    return BM25Okapi(tokenized_chunks)


def search_bm25(
    index: BM25Okapi,
    chunks: list[dict],
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """Return the most relevant chunks using BM25."""
    scores = index.get_scores(tokenize(query))

    ranked = sorted(
        enumerate(scores),
        key=lambda item: item[1],
        reverse=True,
    )

    results = []

    for index_number, score in ranked[:top_k]:
        result = chunks[index_number].copy()
        result["bm25_score"] = float(score)
        results.append(result)

    return results
