"""
MarineWise AI
STEP 18 - Smart Manual Selection

Purpose:
    Read manual_catalog.json and rank the most relevant OEM documents
    for a marine troubleshooting query.

This step DOES NOT download manuals.
It only performs intelligent catalog-level document selection.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


CATALOG_FILE = Path("manual_catalog.json")


# ---------------------------------------------------------
# TEXT NORMALIZATION
# ---------------------------------------------------------

def normalize_text(text: str) -> str:
    """Normalize text for reliable keyword matching."""

    if not text:
        return ""

    text = str(text).lower()

    # Normalize common separators
    text = text.replace("_", " ")
    text = text.replace("-", " ")
    text = text.replace("/", " ")
    text = text.replace("\\", " ")

    # Remove punctuation
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # Collapse spaces
    text = re.sub(r"\s+", " ", text).strip()

    return text


# ---------------------------------------------------------
# LOAD CATALOG
# ---------------------------------------------------------

def load_catalog() -> list[dict[str, Any]]:
    """Load the catalog created in STEP 17."""

    if not CATALOG_FILE.exists():
        raise FileNotFoundError(
            f"{CATALOG_FILE} was not found. "
            "Run STEP 17 first."
        )

    with open(CATALOG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data

    # Support catalogs wrapped inside a dictionary
    if isinstance(data, dict):

        for key in (
            "records",
            "catalog",
            "manuals",
            "items",
            "documents",
        ):
            if isinstance(data.get(key), list):
                return data[key]

    raise ValueError(
        "manual_catalog.json does not contain a recognized "
        "catalog list."
    )


# ---------------------------------------------------------
# CREATE SEARCHABLE TEXT
# ---------------------------------------------------------

def record_search_text(record: dict[str, Any]) -> str:
    """
    Combine all useful metadata fields into searchable text.
    """

    fields = [
        record.get("vessel"),
        record.get("ship"),
        record.get("vessel_name"),
        record.get("equipment"),
        record.get("system"),
        record.get("manufacturer"),
        record.get("maker"),
        record.get("engine"),
        record.get("engine_model"),
        record.get("model"),
        record.get("category"),
        record.get("document_type"),
        record.get("type"),
        record.get("filename"),
        record.get("file_name"),
        record.get("name"),
        record.get("path"),
        record.get("folder_path"),
    ]

    return normalize_text(
        " ".join(str(x) for x in fields if x)
    )


# ---------------------------------------------------------
# QUERY TOKENIZATION
# ---------------------------------------------------------

def query_tokens(query: str) -> list[str]:
    """Convert user query into useful searchable tokens."""

    normalized = normalize_text(query)

    tokens = normalized.split()

    # Ignore very common words
    stop_words = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "this",
        "that",
        "engine",
        "main",
        "system",
        "problem",
        "issue",
        "fault",
        "manual",
        "document",
        "please",
        "show",
        "find",
        "need",
        "me",
        "of",
        "a",
        "an",
        "is",
        "to",
        "in",
        "on",
        "at",
    }

    return [
        token
        for token in tokens
        if token not in stop_words and len(token) >= 2
    ]


# ---------------------------------------------------------
# IMPORTANT MARINE TERMS
# ---------------------------------------------------------

TERM_GROUPS = {

    "maintenance": {
        "maintenance",
        "pms",
        "service",
        "inspection",
        "overhaul",
        "repair",
        "servicing",
    },

    "technical": {
        "technical",
        "specification",
        "spec",
        "technicaldocument",
        "documentation",
    },

    "parts": {
        "parts",
        "spare",
        "spares",
        "part",
        "catalog",
        "catalogue",
    },

    "operation": {
        "operation",
        "operating",
        "instructions",
        "instruction",
        "manual",
    },

    "alarm": {
        "alarm",
        "warning",
        "fault",
        "malfunction",
        "temperature",
        "pressure",
        "high",
        "low",
        "sensor",
    },

    "engine": {
        "engine",
        "diesel",
        "motor",
        "propulsion",
        "generator",
        "genset",
    },

    "hydraulic": {
        "hydraulic",
        "pump",
        "valve",
        "pressure",
        "cylinder",
    },

    "gearbox": {
        "gearbox",
        "gear",
        "transmission",
        "zf",
    },

    "waterjet": {
        "waterjet",
        "water",
        "jet",
        "mjp",
    },

    "steering": {
        "steering",
        "rudder",
        "helm",
    },
}


# ---------------------------------------------------------
# SCORE DOCUMENT
# ---------------------------------------------------------

def score_record(
    record: dict[str, Any],
    query: str,
) -> tuple[float, list[str]]:

    searchable = record_search_text(record)
    tokens = query_tokens(query)

    score = 0.0
    reasons: list[str] = []

    if not searchable:
        return 0.0, reasons

    # -----------------------------------------------------
    # Exact phrase match
    # -----------------------------------------------------

    normalized_query = normalize_text(query)

    if normalized_query and normalized_query in searchable:
        score += 25
        reasons.append("exact query match")

    # -----------------------------------------------------
    # Individual token matching
    # -----------------------------------------------------

    for token in tokens:

        if token in searchable:
            score += 4

            if token not in reasons:
                reasons.append(f"keyword:{token}")

    # -----------------------------------------------------
    # Manufacturer / engine model priority
    # -----------------------------------------------------

    manufacturer = normalize_text(
        str(
            record.get("manufacturer")
            or record.get("maker")
            or ""
        )
    )

    model = normalize_text(
        str(
            record.get("engine_model")
            or record.get("model")
            or record.get("engine")
            or ""
        )
    )

    filename = normalize_text(
        str(
            record.get("filename")
            or record.get("file_name")
            or record.get("name")
            or ""
        )
    )

    # Strong match when model appears in filename
    if model and len(model) >= 4 and model in filename:
        score += 15
        reasons.append("engine/model in filename")

    # Manufacturer match
    if manufacturer and manufacturer in normalized_query:
        if manufacturer in searchable:
            score += 10
            reasons.append("manufacturer match")

    # -----------------------------------------------------
    # Document-type intelligence
    # -----------------------------------------------------

    combined = searchable

    query_lower = normalized_query

    if any(
        word in query_lower
        for word in (
            "maintenance",
            "pms",
            "service",
            "overhaul",
            "repair",
        )
    ):
        if any(
            word in combined
            for word in (
                "maintenance",
                "pms",
                "service",
                "overhaul",
                "repair",
            )
        ):
            score += 8
            reasons.append("maintenance document")

    if any(
        word in query_lower
        for word in (
            "alarm",
            "fault",
            "malfunction",
            "temperature",
            "pressure",
        )
    ):
        if any(
            word in combined
            for word in (
                "alarm",
                "fault",
                "malfunction",
                "troubleshooting",
                "operation",
                "technical",
            )
        ):
            score += 7
            reasons.append("fault/troubleshooting relevance")

    if "parts" in query_lower or "spare" in query_lower:
        if "parts" in combined or "spare" in combined:
            score += 8
            reasons.append("parts document")

    # -----------------------------------------------------
    # Term-group intelligence
    # -----------------------------------------------------

    for group_name, group_terms in TERM_GROUPS.items():

        query_has_group = any(
            term in query_tokens(query)
            for term in group_terms
        )

        document_has_group = any(
            term in searchable.split()
            for term in group_terms
        )

        if query_has_group and document_has_group:
            score += 3
            reasons.append(f"{group_name} relevance")

    return score, reasons


# ---------------------------------------------------------
# SMART SELECTOR
# ---------------------------------------------------------

def select_manuals(
    query: str,
    top_k: int = 10,
) -> list[dict[str, Any]]:

    catalog = load_catalog()

    results = []

    for record in catalog:

        score, reasons = score_record(
            record,
            query,
        )

        if score <= 0:
            continue

        results.append(
            {
                "score": round(score, 2),
                "reasons": reasons,
                "record": record,
            }
        )

    results.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return results[:top_k]


# ---------------------------------------------------------
# DISPLAY
# ---------------------------------------------------------

def display_results(
    query: str,
    results: list[dict[str, Any]],
) -> None:

    print()
    print("=" * 70)
    print("MARINEWISE AI - STEP 18 SMART MANUAL SELECTION")
    print("=" * 70)

    print(f"Query: {query}")
    print()

    print(f"Matching manuals: {len(results)}")
    print()

    if not results:
        print("NO RELEVANT MANUALS FOUND")
        print()
        print(
            "MarineWise AI should NOT download documents "
            "without a relevant catalog match."
        )
        return

    for index, item in enumerate(results, start=1):

        record = item["record"]

        filename = (
            record.get("filename")
            or record.get("file_name")
            or record.get("name")
            or "Unknown file"
        )

        vessel = (
            record.get("vessel")
            or record.get("ship")
            or record.get("vessel_name")
            or "Unknown"
        )

        manufacturer = (
            record.get("manufacturer")
            or record.get("maker")
            or "Unknown"
        )

        document_type = (
            record.get("document_type")
            or record.get("type")
            or record.get("category")
            or "Unknown"
        )

        print("-" * 70)

        print(
            f"{index}. SCORE: {item['score']}"
        )

        print(
            f"   Vessel: {vessel}"
        )

        print(
            f"   Manufacturer: {manufacturer}"
        )

        print(
            f"   Document Type: {document_type}"
        )

        print(
            f"   File: {filename}"
        )

        print(
            f"   Why: {', '.join(item['reasons'][:8])}"
        )

    print()
    print("=" * 70)
    print("STEP 18 SELECTION TEST: SUCCESS")
    print("=" * 70)


# ---------------------------------------------------------
# TEST QUERIES
# ---------------------------------------------------------

if __name__ == "__main__":

    # STEP 18 validation query
    test_query = (
        "QL 40 MAN 16V175D-MM main diesel engine "
        "high exhaust temperature alarm"
    )

    results = select_manuals(
        query=test_query,
        top_k=10,
    )

    display_results(
        query=test_query,
        results=results,
    )
