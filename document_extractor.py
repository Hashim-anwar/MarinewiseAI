"""
MarineWise AI
STEP 21 - Document Extraction

Extracts text from the manuals selected by STEP 19
and downloaded by STEP 20.

Output:
    extracted_documents/
        <manual>.json

Each JSON preserves:
    - source file
    - page number
    - extracted text
    - document metadata
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from pypdf import PdfReader


INPUT_DIR = Path("selected_manuals")
OUTPUT_DIR = Path("extracted_documents")


def safe_name(filename: str) -> str:
    """
    Convert a PDF filename into a safe JSON filename.
    """
    name = Path(filename).stem
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    return name + ".json"


def clean_text(text: str) -> str:
    """
    Basic text cleanup while preserving technical content.
    """
    if not text:
        return ""

    text = text.replace("\x00", " ")

    # Normalize repeated whitespace
    text = re.sub(r"[ \t]+", " ", text)

    # Preserve paragraph/page structure
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def extract_pdf(pdf_path: Path) -> dict:
    """
    Extract page-by-page text from a PDF.
    """

    print(f"\nProcessing: {pdf_path.name}")

    reader = PdfReader(str(pdf_path))

    pages = []
    total_characters = 0
    pages_with_text = 0

    for page_number, page in enumerate(reader.pages, start=1):

        try:
            text = page.extract_text() or ""
        except Exception as exc:
            print(
                f"  WARNING - page {page_number} "
                f"could not be extracted: {exc}"
            )
            text = ""

        text = clean_text(text)

        if text:
            pages_with_text += 1
            total_characters += len(text)

        pages.append(
            {
                "page": page_number,
                "text": text,
                "characters": len(text),
            }
        )

    return {
        "source_file": pdf_path.name,
        "file_size_bytes": pdf_path.stat().st_size,
        "total_pages": len(reader.pages),
        "pages_with_text": pages_with_text,
        "total_characters": total_characters,
        "pages": pages,
    }


def main():

    print("=" * 70)
    print("MARINEWISE AI - STEP 21")
    print("DOCUMENT EXTRACTION")
    print("=" * 70)

    if not INPUT_DIR.exists():
        raise FileNotFoundError(
            f"Input directory not found: {INPUT_DIR}"
        )

    pdf_files = sorted(
        p for p in INPUT_DIR.iterdir()
        if p.is_file() and p.suffix.lower() == ".pdf"
    )

    print(f"\nPDF manuals found: {len(pdf_files)}")

    if len(pdf_files) != 10:
        raise AssertionError(
            f"Expected 10 selected manuals, found {len(pdf_files)}"
        )

    # Recreate output directory
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    extracted_count = 0
    total_pages = 0
    total_characters = 0

    print("\nEXTRACTION")
    print("-" * 70)

    for index, pdf_path in enumerate(pdf_files, start=1):

        print(f"\n[{index}/10]")

        result = extract_pdf(pdf_path)

        output_file = OUTPUT_DIR / safe_name(pdf_path.name)

        with output_file.open(
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                result,
                f,
                ensure_ascii=False,
                indent=2,
            )

        extracted_count += 1
        total_pages += result["total_pages"]
        total_characters += result["total_characters"]

        print(
            f"  Pages: {result['total_pages']}"
        )

        print(
            f"  Pages with text: "
            f"{result['pages_with_text']}"
        )

        print(
            f"  Characters: "
            f"{result['total_characters']:,}"
        )

        print(
            f"  GREEN - "
            f"{output_file.name}"
        )

    output_files = [
        p for p in OUTPUT_DIR.iterdir()
        if p.is_file() and p.suffix.lower() == ".json"
    ]

    print()
    print("=" * 70)
    print("STEP 21 VERIFICATION")
    print("=" * 70)

    print(f"Input PDF manuals: {len(pdf_files)}")
    print(f"Successfully extracted: {extracted_count}")
    print(f"JSON output files: {len(output_files)}")
    print(f"Total pages: {total_pages}")
    print(f"Total extracted characters: {total_characters:,}")

    if extracted_count != 10:
        raise AssertionError(
            "Not all 10 manuals were extracted."
        )

    if len(output_files) != 10:
        raise AssertionError(
            "Expected 10 extraction JSON files."
        )

    if total_characters == 0:
        raise AssertionError(
            "No text was extracted from the manuals."
        )

    print()
    print("Document extraction completed successfully.")
    print("Page-level source information preserved.")
    print()
    print("STEP 21: SUCCESS")
    print("GREEN")


if __name__ == "__main__":
    main()
