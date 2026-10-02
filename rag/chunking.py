def split_text(
    text: str,
    chunk_size: int = 800,
    overlap: int = 100,
) -> list[str]:
    """Split text into overlapping character chunks."""
    text = text.strip()

    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = end - overlap

    return chunks


def create_page_chunks(
    page_text: str,
    page_number: int,
    chunk_size: int = 800,
    overlap: int = 100,
) -> list[dict]:
    """Create chunks while keeping the original page number."""
    chunks = split_text(
        page_text,
        chunk_size=chunk_size,
        overlap=overlap,
    )

    results = []

    for index, chunk in enumerate(chunks, start=1):
        results.append(
            {
                "page_number": page_number,
                "chunk_number": index,
                "text": chunk,
            }
        )

    return results
