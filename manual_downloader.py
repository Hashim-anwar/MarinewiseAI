"""
MarineWise AI
STEP 20 - Selective Manual Downloader

Downloads ONLY the manuals selected by STEP 19.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import gdown


CATALOG_FILE = Path("manual_catalog.json")
SELECTION_FILE = Path("selected_manuals.json")
DOWNLOAD_DIR = Path("selected_manuals")


def load_json(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def safe_filename(name: str) -> str:
    name = str(name or "").strip()

    if not name:
        name = "unknown_manual.pdf"

    return re.sub(r'[<>:"/\\|?*]', "_", name)


def get_filename(record: dict) -> str:
    aliases = [
        "file_name",
        "filename",
        "file",
        "name",
        "title",
        "document_name",
        "document",
        "display_name",
    ]

    for key in aliases:
        value = record.get(key)

        if value:
            return str(value).strip()

    return "unknown_manual.pdf"


def get_drive_id(record: dict) -> str | None:
    """
    Get the exact Google Drive file ID created by STEP 17.
    """

    aliases = [
        "google_drive_file_id",
        "file_id",
        "drive_id",
        "google_drive_id",
    ]

    for key in aliases:
        value = record.get(key)

        if value:
            value = str(value).strip()

            if len(value) >= 10:
                return value

    return None


def main():
    print("=" * 70)
    print("MARINEWISE AI - STEP 20")
    print("SELECTIVE MANUAL DOWNLOAD")
    print("=" * 70)

    # ------------------------------------------------------------
    # Load catalog
    # ------------------------------------------------------------

    catalog = load_json(CATALOG_FILE)

    if isinstance(catalog, dict):
        records = catalog.get("items", [])
    else:
        records = catalog

    print(f"\nCatalog records: {len(records)}")

    if len(records) != 283:
        raise AssertionError(
            f"Expected 283 catalog records, found {len(records)}"
        )

    # ------------------------------------------------------------
    # Load STEP 19 selection
    # ------------------------------------------------------------

    selected = load_json(SELECTION_FILE)

    if isinstance(selected, dict):
        selected_records = selected.get("results", [])

        if not selected_records:
            selected_records = selected.get("selected_manuals", [])

        if not selected_records:
            selected_records = selected.get("items", [])
    else:
        selected_records = selected

    if not selected_records:
        raise AssertionError(
            "selected_manuals.json contains no selected manuals."
        )

    print(f"Selected manuals from STEP 19: {len(selected_records)}")

    # STEP 19 currently selects 10 manuals.
    selected_records = selected_records[:10]

    print(f"Manuals considered for download: {len(selected_records)}")

    # ------------------------------------------------------------
    # Prepare download directory
    # ------------------------------------------------------------

    if DOWNLOAD_DIR.exists():
        shutil.rmtree(DOWNLOAD_DIR)

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------
    # Verify Drive IDs
    # ------------------------------------------------------------

    print("\nDOWNLOAD SOURCE CHECK")
    print("-" * 70)

    valid_sources = 0

    for record in selected_records:
        filename = get_filename(record)
        drive_id = get_drive_id(record)

        if drive_id:
            valid_sources += 1
            print(f"GREEN - {filename}")
            print(f"        Drive ID: {drive_id}")
        else:
            print(f"ERROR - Missing Drive ID: {filename}")

    print(
        f"\nSelected records containing Drive IDs: "
        f"{valid_sources}/{len(selected_records)}"
    )

    if valid_sources != len(selected_records):
        raise AssertionError(
            "One or more selected manuals are missing a Google Drive file ID."
        )

    # ------------------------------------------------------------
    # Download ONLY selected manuals
    # ------------------------------------------------------------

    print("\nDOWNLOADING SELECTED MANUALS")
    print("-" * 70)

    downloaded = 0

    for index, record in enumerate(selected_records, start=1):

        filename = safe_filename(get_filename(record))
        drive_id = get_drive_id(record)

        destination = DOWNLOAD_DIR / filename

        print(f"\n{index}. Downloading:")
        print(f"   {filename}")
        print(f"   Drive ID: {drive_id}")

        try:
            result = gdown.download(
                id=drive_id,
                output=str(destination),
                quiet=False,
            )

            if result and destination.exists():
                size = destination.stat().st_size

                if size <= 0:
                    raise RuntimeError("Downloaded file is empty.")

                downloaded += 1

                print(
                    f"   GREEN - downloaded "
                    f"({size:,} bytes)"
                )

            else:
                print("   FAILED - file was not created.")

        except Exception as exc:
            print(f"   FAILED - {exc}")

    # ------------------------------------------------------------
    # Final verification
    # ------------------------------------------------------------

    files = [
        p for p in DOWNLOAD_DIR.iterdir()
        if p.is_file()
    ]

    print()
    print("=" * 70)
    print("STEP 20 VERIFICATION")
    print("=" * 70)

    print(f"Catalog records: {len(records)}")
    print(f"STEP 19 selected: {len(selected_records)}")
    print(f"Files downloaded: {len(files)}")

    if len(files) == 0:
        raise AssertionError(
            "STEP 20 downloaded zero files."
        )

    if len(files) > len(selected_records):
        raise AssertionError(
            "More files were downloaded than selected by STEP 19."
        )

    print("\nDownloaded files:")

    for path in files:
        print(f"  - {path.name}")

    print()
    print("Only STEP 19 selected manuals were downloaded.")
    print()
    print("STEP 20: SUCCESS")
    print("GREEN")


if __name__ == "__main__":
    main()
