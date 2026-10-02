from pathlib import Path

from rag.drive_download import download_manuals
from rag.ingestion import find_documents, read_document
from rag.chunking import create_page_chunks
from rag.vector_search import build_faiss_index


MANUALS_FOLDER = Path("data/manuals")
INDEX_FOLDER = Path("data/index")


def process_document(file_path: Path) -> list[dict]:
    """Read one document and create page-aware chunks."""
    pages = read_document(file_path)

    all_chunks = []

    for page in pages:
        chunks = create_page_chunks(
            page_text=page["text"],
            page_number=page["page_number"],
            chunk_size=800,
            overlap=100,
        )

        for chunk in chunks:
            chunk["document_name"] = file_path.name
            chunk["file_path"] = str(file_path)

        all_chunks.extend(chunks)

    return all_chunks


def process_all_documents(folder: Path) -> list[dict]:
    """Process all supported documents recursively."""
    documents = find_documents(folder)

    print(f"Documents found: {len(documents)}")

    all_chunks = []

    for number, document in enumerate(documents, start=1):
        print(
            f"[{number}/{len(documents)}] "
            f"Processing: {document.name}"
        )

        chunks = process_document(document)
        all_chunks.extend(chunks)

        print(f"    Chunks created: {len(chunks)}")

    return all_chunks


def main() -> None:
    """Download manuals and build the FAISS knowledge base."""
    print("=" * 60)
    print("MARINEWISE AI - OEM KNOWLEDGE BASE BUILDER")
    print("=" * 60)

    print("\nStep 1: Downloading MANUALS folder...")
    folder = Path(download_manuals())

    print("\nStep 2: Processing OEM documents...")
    chunks = process_all_documents(folder)

    print(f"\nTotal chunks created: {len(chunks)}")

    if not chunks:
        print("No readable documents were found.")
        return

    print("\nStep 3: Building FAISS index...")

    build_faiss_index(
        chunks=chunks,
        index_folder=INDEX_FOLDER,
    )

    print("\n" + "=" * 60)
    print("FAISS INDEX CREATED SUCCESSFULLY")
    print("=" * 60)

    print(f"Documents folder: {folder}")
    print(f"Index folder: {INDEX_FOLDER}")
    print(f"Total chunks: {len(chunks)}")


if __name__ == "__main__":
    main()
