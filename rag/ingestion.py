from pathlib import Path

from docx import Document
from pypdf import PdfReader


SUPPORTED_FILES = {".pdf", ".docx", ".txt"}


def read_pdf(file_path: Path) -> list[dict]:
    """Read a PDF and return text separately for each page."""
    reader = PdfReader(str(file_path))
    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""

        if text.strip():
            pages.append(
                {
                    "page_number": page_number,
                    "text": text.strip(),
                }
            )

    return pages


def read_docx(file_path: Path) -> list[dict]:
    """Read a DOCX file as a single text section."""
    document = Document(str(file_path))

    text = "\n".join(
        paragraph.text
        for paragraph in document.paragraphs
        if paragraph.text.strip()
    )

    if not text.strip():
        return []

    return [
        {
            "page_number": 1,
            "text": text.strip(),
        }
    ]


def read_txt(file_path: Path) -> list[dict]:
    """Read a TXT file as a single text section."""
    text = file_path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    if not text.strip():
        return []

    return [
        {
            "page_number": 1,
            "text": text.strip(),
        }
    ]


def read_document(file_path: Path) -> list[dict]:
    """Read a supported document and return page-aware text."""
    extension = file_path.suffix.lower()

    if extension == ".pdf":
        return read_pdf(file_path)

    if extension == ".docx":
        return read_docx(file_path)

    if extension == ".txt":
        return read_txt(file_path)

    return []


def find_documents(folder: Path) -> list[Path]:
    """Find supported documents inside a folder recursively."""
    return [
        path
        for path in folder.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_FILES
    ]
