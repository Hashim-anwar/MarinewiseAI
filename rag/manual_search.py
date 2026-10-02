from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


CATALOG_FILE = Path("manual_catalog.json")


def normalize(text: str) -> str:
    """Normalize text for reliable searching."""
    text = str(text or "").upper()
    text = text.replace("_", " ")
    text = text.replace("-", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def load_catalog(path: str | Path = CATALOG_FILE) -> list[dict[str, Any]]:
    """Load the MarineWise manual catalog."""
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Catalog not found: {path}"
        )

    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    return data.get("items", [])


def search_manuals(
    query: str,
    catalog: list[dict[str, Any]],
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """
    Search the catalog using weighted metadata matching.

    Higher scores are given to:
    manufacturer
    engine model
    vessel
    system
    document type
    filename/path
    """

    query_normalized = normalize(query)

    # Convert the query into searchable terms.
    query_terms = set(
        term
        for term in query_normalized.split()
        if len(term) >= 2
    )

    results = []

    for item in catalog:

        fields = {
            "manufacturer": normalize(
                item.get("manufacturer", "")
            ),
            "engine_model": normalize(
                item.get("engine_model", "")
            ),
            "vessel": normalize(
                item.get("vessel", "")
            ),
            "system": normalize(
                item.get("system", "")
            ),
            "document_type": normalize(
                item.get("document_type", "")
            ),
            "manual_category": normalize(
                item.get("manual_category", "")
            ),
            "file_name": normalize(
                item.get("file_name", "")
            ),
            "drive_path": normalize(
                item.get("drive_path", "")
            ),
        }

        score = 0
        matched_fields = []

        # Strong exact field matching
        if (
            fields["manufacturer"]
            and fields["manufacturer"] in query_normalized
        ):
            score += 30
            matched_fields.append("manufacturer")

        if (
            fields["engine_model"]
            and fields["engine_model"] != "UNKNOWN"
            and fields["engine_model"] in query_normalized
        ):
            score += 40
            matched_fields.append("engine_model")

        if (
            fields["vessel"]
            and fields["vessel"] != "UNKNOWN"
            and fields["vessel"] in query_normalized
        ):
            score += 25
            matched_fields.append("vessel")

        if (
            fields["system"]
            and fields["system"] in query_normalized
        ):
            score += 20
            matched_fields.append("system")

        if (
            fields["document_type"]
            and fields["document_type"] in query_normalized
        ):
            score += 10
            matched_fields.append("document_type")

        # General keyword matching
        searchable_text = " ".join(fields.values())

        for term in query_terms:

            if term in searchable_text:
                score += 2

        # Filename is particularly useful for OEM manuals
        filename_hits = 0

        for term in query_terms:
            if term in fields["file_name"]:
                filename_hits += 1

        score += min(filename_hits * 3, 15)

        if score > 0:

            result = dict(item)

            result["search_score"] = score
            result["matched_fields"] = matched_fields

            results.append(result)

    results.sort(
        key=lambda item: item["search_score"],
        reverse=True,
    )

    return results[:top_k]


def print_results(
    query: str,
    results: list[dict[str, Any]],
) -> None:

    print("\n" + "=" * 70)
    print("MARINEWISE AI - MANUAL INTELLIGENCE SEARCH")
    print("=" * 70)

    print(f"\nQuery:")
    print(query)

    print(f"\nResults found: {len(results)}")
    print("-" * 70)

    for number, item in enumerate(results, start=1):

        print(
            f"{number}. "
            f"[Score {item['search_score']}] "
            f"{item.get('file_name', 'Unknown')}"
        )

        print(
            f"   Vessel: "
            f"{item.get('vessel', 'Unknown')}"
        )

        print(
            f"   Manufacturer: "
            f"{item.get('manufacturer', 'Unknown')}"
        )

        print(
            f"   System: "
            f"{item.get('system', 'Unknown')}"
        )

        print(
            f"   Engine: "
            f"{item.get('engine_model', 'Unknown')}"
        )

        print(
            f"   Type: "
            f"{item.get('document_type', 'Unknown')}"
        )

        print(
            f"   Path: "
            f"{item.get('drive_path', 'Unknown')}"
        )

        print(
            f"   Matched: "
            f"{', '.join(item.get('matched_fields', [])) or 'keyword match'}"
        )

        print()


def main() -> None:

    print("=" * 70)
    print("MARINEWISE AI - STEP 18")
    print("MANUAL INTELLIGENCE SEARCH LAYER")
    print("=" * 70)

    catalog = load_catalog()

    print(
        f"\nCatalog loaded successfully: "
        f"{len(catalog)} records"
    )

    # Test query
    query = (
        "QL 40 MAN 16V175D-MM "
        "Main Engine maintenance"
    )

    results = search_manuals(
        query=query,
        catalog=catalog,
        top_k=10,
    )

    print_results(
        query=query,
        results=results,
    )

    if not results:
        raise RuntimeError(
            "STEP 18 FAILED: No manuals matched the test query."
        )

    print("=" * 70)
    print("STEP 18: SUCCESS")
    print("=" * 70)


if __name__ == "__main__":
    main()
