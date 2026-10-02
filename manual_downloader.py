"""
MarineWise AI
STEP 20 - Selective Manual Downloader

Downloads ONLY the manuals selected by STEP 19.

This step does NOT download the complete MANUALS folder.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import urlparse

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
    """
    Make a safe local filename.
    """
    name = str(name or "").strip()

    if not name:
        name = "unknown_manual.pdf"

    name = re.sub(r'[<>:"/\\|?*]', "_", name)

    return name


def get_filename(record: dict) -> str:
    """
    Resolve filename from the catalog record using multiple aliases.
    """
    aliases = [
        "filename",
        "file_name",
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


def get_drive_url(record: dict) -> str | None:
    """
    Look for an existing Google Drive file URL in the catalog.

    STEP 20 deliberately does not create a new authentication system.
    """

    aliases = [
        "url",
        "file_url",
        "drive_url",
        "google_drive_url",
        "web_url",
        "link",
    ]

    for key in aliases:
        value = record.get(key)

        if value and "drive.google.com" in str(value):
            return str(value).strip()

    return None


def get_drive_id(record: dict) -> str | None:
    """
    Look for an existing Google Drive file ID in the catalog.
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

            # Avoid accidentally treating unrelated IDs as Drive IDs.
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
        selected_records = selected.get("selected_manuals", [])

        if not selected_records:
            selected_records = selected.get("results", [])

        if not selected_records:
            selected_records = selected.get("items", [])
    else:
        selected_records = selected

    if not selected_records:
        raise AssertionError(
            "selected_manuals.json does not contain selected manuals."
        )

    print(f"Selected manuals from STEP 19: {len(selected_records)}")

    # ------------------------------------------------------------
    # Limit STEP 20 download set
    # ------------------------------------------------------------

    max_downloads = min(len(selected_records), 10)

    selected_records = selected_records[:max_downloads]

    print(f"Manuals considered for download: {len(selected_records)}")

    # ------------------------------------------------------------
    # Prepare directory
    # ------------------------------------------------------------

    if DOWNLOAD_DIR.exists():
        shutil.rmtree(DOWNLOAD_DIR)

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------
    # Display selected manuals
    # ------------------------------------------------------------

    print("\nSELECTED MANUALS")
    print("-" * 70)

    for index, record in enumerate(selected_records, start=1):
        filename = get_filename(record)

        print(f"{index}. {filename}")

    # ------------------------------------------------------------
    # Check whether catalog contains download information
    # ------------------------------------------------------------

    print("\nDOWNLOAD SOURCE CHECK")
    print("-" * 70)

    source_count = 0

    for record in selected_records:
        drive_url = get_drive_url(record)
        drive_id = get_drive_id(record)

        if drive_url or drive_id:
            source_count += 1

    print(
        f"Selected records containing Drive URL/ID: "
        f"{source_count}/{len(selected_records)}"
    )

    # ------------------------------------------------------------
    # STEP 20 safety gate
    # ------------------------------------------------------------

    if source_count == 0:
        print()
        print("=" * 70)
        print("STEP 20 SAFETY CHECK")
        print("=" * 70)
        print()
        print("No Google Drive file URL or file ID exists in the")
        print("current catalog records.")
        print()
        print("NO FILES WERE DOWNLOADED.")
        print()
        print("This is intentional. We will NOT download all 283 files.")
        print("The next correction will add the existing Drive file")
        print("identifiers to the catalog and reuse the existing")
        print("successful Google Drive listing mechanism.")
        print()
        print("STEP 20: WAITING FOR DRIVE FILE IDENTIFIERS")
        print("=" * 70)

        return

    # ------------------------------------------------------------
    # Download only selected files
    # ------------------------------------------------------------

    downloaded = 0

    print("\nDOWNLOADING SELECTED MANUALS")
    print("-" * 70)

    for index, record in enumerate(selected_records, start=1):

        filename = safe_filename(get_filename(record))

        drive_url = get_drive_url(record)
        drive_id = get_drive_id(record)

        destination = DOWNLOAD_DIR / filename

        if drive_url:
            source = drive_url
        elif drive_id:
            source = drive_id
        else:
            print(f"{index}. SKIPPED - no Drive source: {filename}")
            continue

        print(f"\n{index}. Downloading:")
        print(f"   {filename}")

        try:
            result = gdown.download(
                id=source if not drive_url else None,
                url=drive_url,
                output=str(destination),
                quiet=False,
                fuzzy=True,
            )

            if result and destination.exists():
                downloaded += 1
                print("   GREEN - downloaded")
            else:
                print("   FAILED - file not created")

        except Exception as exc:
            print(f"   FAILED - {exc}")

    # ------------------------------------------------------------
    # Verification
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

    if len(files) > 10:
        raise AssertionError(
            "STEP 20 downloaded more than the maximum selected set."
        )

    print("\nDownloaded files:")
    for path in files:
        print(f"  - {path.name}")

    print()
    print("Only selected manuals were downloaded.")
    print()
    print("STEP 20: SUCCESS")
    print("GREEN")


if __name__ == "__main__":
    main()
