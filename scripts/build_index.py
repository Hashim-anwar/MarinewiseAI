from pathlib import Path

from rag.drive_download import download_manuals
from rag.ingestion import find_documents, read_document


def show_documents(folder: Path) -> None:
    """Display the downloaded documents and basic text information."""
    documents = find_documents(folder)

    print(f"\nDocuments found: {len(documents)}")

    for file_path in documents:
        pages = read_document(file_path)

        print(
            f"{file_path} | "
            f"sections/pages: {len(pages)}"
        )


def main() -> None:
    """Download the MANUALS folder and inspect its documents."""
    print("Starting MANUALS download...")

    folder = Path(download_manuals())

    print(f"\nManual folder: {folder}")

    show_documents(folder)

    print("\nStep 6 document inspection complete.")


if __name__ == "__main__":
    main()
