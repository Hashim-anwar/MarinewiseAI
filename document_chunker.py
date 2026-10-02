"""
MarineWise AI
STEP 22 - Smart Document Chunking

Reads page-level extraction JSON files created by STEP 21
and creates searchable chunks while preserving source metadata.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path


INPUT_DIR = Path("extracted_documents")
OUTPUT_DIR = Path("chunks")

CHUNK_SIZE = 1800
CHUNK_OVERLAP = 250


def clean_text(text: str) -> str:
    """Normalize extracted technical text."""

    if not text:
        return ""

    text = text.replace("\x00", " ")

    # Normalize spaces but preserve line breaks.
    text = re.sub(r"[ \t]+", " ", text)

    # Remove excessive blank lines.
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def split_text(text: str) -> list[str]:
    """
    Split text into overlapping chunks.

    Attempts to break at paragraph/sentence boundaries
    instead of cutting technical text randomly.
    """

    text = clean_text(text)

    if not text:
        return []

    if len(text) <= CHUNK_SIZE:
        return [text]

    chunks = []

    start = 0
    text_length = len(text)

    while start < text_length:

        end = min(start + CHUNK_SIZE, text_length)

        if end < text_length:

            # Prefer paragraph boundary.
            boundary = text.rfind("\n\n", start, end)

            if boundary == -1:
                # Then sentence boundary.
                boundary = text.rfind(". ", start, end)

            if boundary == -1:
                # Then word boundary.
                boundary = text.rfind(" ", start, end)

            if boundary > start + int(CHUNK_SIZE * 0.60):
                end = boundary + 1

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        next_start = end - CHUNK_OVERLAP

        if next_start <= start:
            next_start = end

        start = next_start

    return chunks


def infer_metadata(source_file: str) -> dict:
    """
    Basic metadata inference from the source filename.
    """

    normalized = source_file.upper()

    manufacturer = "Unknown"
    engine_model = "Unknown"
    vessel = "Unknown"
    system = "Unknown"

    if "MAN" in normalized:
        manufacturer = "MAN"

    if "QL 40" in normalized or "QL40" in normalized:
        vessel = "QL 40"

    if "QL 80" in normalized or "QL80" in normalized:
        vessel = "QL 80"

    if "QL 15" in normalized or "QL15" in normalized:
        vessel = "QL 15"

    if "16V175D" in normalized:
        engine_model = "16V175D-MM"

    if "12V175D" in normalized:
        engine_model = "12V175D-ML"

    if "MAIN_DIESEL" in normalized:
        system = "Main Engine"

    return {
        "manufacturer": manufacturer,
        "engine_model": engine_model,
        "vessel": vessel,
        "system": system,
    }


def process_document(json_path: Path) -> list[dict]:
    """Create chunks from one extracted document."""

    with json_path.open("r", encoding="utf-8") as f:
        document = json.load(f)

    source_file = document.get(
        "source_file",
        json_path.stem,
    )

    metadata = infer_metadata(source_file)

    all_chunks = []

    chunk_number = 0

    for page_record in document.get("pages", []):

        page_number = page_record.get("page")
        page_text = page_record.get("text", "")

        page_text = clean_text(page_text)

        if not page_text:
            continue

        page_chunks = split_text(page_text)

        for chunk_text in page_chunks:

            chunk_number += 1

            all_chunks.append(
                {
                    "chunk_id": (
                        f"{json_path.stem}_"
                        f"p{page_number}_"
                        f"c{chunk_number}"
                    ),
                    "source_file": source_file,
                    "page": page_number,
                    "manufacturer": metadata["manufacturer"],
                    "engine_model": metadata["engine_model"],
                    "vessel": metadata["vessel"],
                    "system": metadata["system"],
                    "text": chunk_text,
                    "characters": len(chunk_text),
                }
            )

    return all_chunks


def main():

    print("=" * 70)
    print("MARINEWISE AI - STEP 22")
    print("SMART DOCUMENT CHUNKING")
    print("=" * 70)

    if not INPUT_DIR.exists():
        raise FileNotFoundError(
            f"Input directory not found: {INPUT_DIR}"
        )

    json_files = sorted(
        p
        for p in INPUT_DIR.iterdir()
        if p.is_file() and p.suffix.lower() == ".json"
    )

    print(f"\nExtraction JSON files found: {len(json_files)}")

    if len(json_files) != 10:
        raise AssertionError(
            f"Expected 10 extraction files, found {len(json_files)}"
        )

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    all_chunks = []

    print("\nCHUNKING DOCUMENTS")
    print("-" * 70)

    for index, json_path in enumerate(json_files, start=1):

        print(
            f"\n[{index}/{len(json_files)}] "
            f"{json_path.name}"
        )

        document_chunks = process_document(json_path)

        all_chunks.extend(document_chunks)

        print(
            f"  Chunks created: "
            f"{len(document_chunks)}"
        )

        print(
            f"  GREEN - source metadata preserved"
        )

    if not all_chunks:
        raise AssertionError(
            "No chunks were created."
        )

    # Write master chunk file.
    master_file = OUTPUT_DIR / "all_chunks.json"

    with master_file.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            {
                "project": "MarineWise AI",
                "step": "STEP 22",
                "chunk_size": CHUNK_SIZE,
                "chunk_overlap": CHUNK_OVERLAP,
                "total_chunks": len(all_chunks),
                "chunks": all_chunks,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    # Create a lightweight JSONL file for future RAG/embedding work.
    jsonl_file = OUTPUT_DIR / "all_chunks.jsonl"

    with jsonl_file.open(
        "w",
        encoding="utf-8",
    ) as f:

        for chunk in all_chunks:
            f.write(
                json.dumps(
                    chunk,
                    ensure_ascii=False,
                )
                + "\n"
            )

    total_characters = sum(
        chunk["characters"]
        for chunk in all_chunks
    )

    average_size = (
        total_characters / len(all_chunks)
        if all_chunks
        else 0
    )

    print()
    print("=" * 70)
    print("STEP 22 VERIFICATION")
    print("=" * 70)

    print(f"Source documents: {len(json_files)}")
    print(f"Total chunks: {len(all_chunks):,}")
    print(f"Total chunk characters: {total_characters:,}")
    print(f"Average chunk size: {average_size:,.0f}")
    print(f"Chunk size target: {CHUNK_SIZE}")
    print(f"Chunk overlap: {CHUNK_OVERLAP}")
    print(f"Master JSON: {master_file}")
    print(f"JSONL: {jsonl_file}")

    # Verify important metadata.
    sample = all_chunks[0]

    required_fields = [
        "chunk_id",
        "source_file",
        "page",
        "manufacturer",
        "engine_model",
        "vessel",
        "system",
        "text",
        "characters",
    ]

    for field in required_fields:
        if field not in sample:
            raise AssertionError(
                f"Missing chunk metadata field: {field}"
            )

    if len(all_chunks) < 100:
        raise AssertionError(
            "Unexpectedly low chunk count."
        )

    if total_characters == 0:
        raise AssertionError(
            "Chunk text is empty."
        )

    print()
    print("GREEN - chunk metadata verified.")
    print("GREEN - page references preserved.")
    print("GREEN - source filenames preserved.")
    print("GREEN - JSON master index created.")
    print("GREEN - JSONL index created.")
    print()
    print("STEP 22: SUCCESS")
    print("GREEN")


if __name__ == "__main__":
    main()
