"""
MarineWise AI
STEP 19 - Advanced Smart Manual Selection

Purpose:
    Select and rank the most relevant OEM manuals from
    manual_catalog.json.

The selector considers:
    - Vessel
    - Manufacturer
    - Exact engine model
    - System
    - Fault / alarm / problem
    - Document type
    - Manual category
    - Filename
    - Folder/path information
    - General keyword evidence

Important:
    - Does NOT connect to Google Drive.
    - Does NOT download manuals.
    - Uses the existing manual_catalog.json.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


# ============================================================
# CONFIGURATION
# ============================================================

CATALOG_FILE = Path("manual_catalog.json")
DEFAULT_TOP_K = 10


WEIGHTS = {
    "exact_vessel": 40,
    "exact_manufacturer": 25,
    "exact_engine_model": 50,
    "system": 25,
    "fault": 20,
    "document_type": 15,
    "manual_category": 10,
    "filename": 10,
    "path": 5,
}


MANUFACTURERS = [
    "VOLVO PENTA",
    "CATERPILLAR",
    "GÜRDESAN",
    "ARNESON",
    "YANMAR",
    "YAMAHA",
    "CATERPILLAR",
    "DOEN",
    "MJP",
    "MTU",
    "MAN",
    "CAT",
    "VOLVO",
    "ZF",
    "GURDESAN",
]


SYSTEM_ALIASES = {
    "main engine": [
        "main engine",
        "main engines",
        "main diesel engine",
        "main diesel engines",
        "propulsion",
    ],
    "generator": [
        "generator",
        "generators",
        "genset",
        "auxiliary engine",
        "auxiliary engines",
    ],
    "gearbox": [
        "gearbox",
        "gear box",
        "transmission",
        "zf",
    ],
    "bow ramp": [
        "bow ramp",
        "landing craft ramp",
    ],
    "bow thruster": [
        "bow thruster",
        "thruster",
    ],
    "anchor winch": [
        "anchor winch",
        "winch",
    ],
    "hydraulic": [
        "hydraulic",
        "hydraulic pump",
        "hydraulic system",
    ],
    "water jet": [
        "water jet",
        "waterjet",
        "mjp",
    ],
    "steering": [
        "steering",
        "steering system",
    ],
    "petrol engine": [
        "petrol engine",
        "petrol engines",
        "yamaha",
    ],
    "arneson": [
        "arneson",
        "surface drive",
    ],
}


DOCUMENT_TYPE_TERMS = {
    "technical documentation": [
        "technical documentation",
        "technical document",
        "tech doc",
    ],
    "maintenance manual": [
        "maintenance manual",
        "maintenance",
        "repair manual",
    ],
    "pms": [
        "pms",
        "planned maintenance",
        "preventive maintenance",
    ],
    "parts catalog": [
        "parts catalog",
        "parts catalogue",
        "part list",
        "spare parts",
        "spares",
    ],
    "operating manual": [
        "operating instructions",
        "operating manual",
        "operation manual",
        "operator manual",
    ],
    "service manual": [
        "service manual",
        "service manuel",
    ],
}


# ============================================================
# NORMALIZATION
# ============================================================

def normalize(text: Any) -> str:
    """Normalize text for matching."""

    if text is None:
        return ""

    value = str(text).upper()

    value = value.replace("_", " ")
    value = value.replace("-", " ")
    value = value.replace("/", " ")
    value = value.replace("\\", " ")
    value = value.replace(",", " ")
    value = value.replace(".", " ")

    value = re.sub(r"\s+", " ", value)

    return value.strip()


def compact(text: Any) -> str:
    """Remove separators for exact technical model matching."""

    return re.sub(
        r"[^A-Z0-9]",
        "",
        str(text).upper(),
    )


def tokenize(text: Any) -> set[str]:
    """Return normalized tokens."""

    value = normalize(text)

    if not value:
        return set()

    return set(
        re.findall(
            r"[A-Z0-9]+",
            value,
        )
    )


# ============================================================
# CATALOG FIELD COMPATIBILITY
# ============================================================

FIELD_ALIASES = {

    "filename": [
        "filename",
        "file_name",
        "file",
        "name",
        "title",
        "document_name",
        "document",
        "display_name",
    ],

    "name": [
        "name",
        "filename",
        "file_name",
        "file",
        "title",
        "document_name",
        "document",
        "display_name",
    ],

    "path": [
        "path",
        "file_path",
        "folder_path",
        "relative_path",
        "full_path",
    ],

    "relative_path": [
        "relative_path",
        "path",
        "file_path",
        "folder_path",
        "full_path",
    ],

    "folder": [
        "folder",
        "folder_path",
        "parent_folder",
        "path",
    ],

    "vessel": [
        "vessel",
        "ship",
        "vessel_name",
        "ship_name",
    ],

    "ship": [
        "ship",
        "vessel",
        "ship_name",
        "vessel_name",
    ],

    "manufacturer": [
        "manufacturer",
        "maker",
        "oem",
        "brand",
    ],

    "engine_model": [
        "engine_model",
        "engine",
        "model",
        "engine_type",
    ],

    "engine": [
        "engine",
        "engine_model",
        "model",
        "engine_type",
    ],

    "system": [
        "system",
        "system_name",
        "equipment",
        "equipment_system",
    ],

    "document_type": [
        "document_type",
        "doc_type",
        "document",
        "type",
    ],

    "manual_category": [
        "manual_category",
        "category",
        "manual_type",
    ],
}


def get_field(
    record: dict[str, Any],
    *names: str,
) -> str:
    """
    Return the first available catalog field.

    Supports multiple possible field names so STEP 19
    remains compatible with the catalog generated by
    STEP 17/18.
    """

    checked = set()

    for name in names:

        candidates = FIELD_ALIASES.get(
            name,
            [name],
        )

        for candidate in candidates:

            if candidate in checked:
                continue

            checked.add(candidate)

            value = record.get(candidate)

            if value is not None:

                value_string = str(value).strip()

                if value_string:
                    return value_string

    return ""


def record_text(record: dict[str, Any]) -> str:
    """Build searchable text from all useful catalog fields."""

    fields = [
        get_field(record, "vessel"),
        get_field(record, "manufacturer"),
        get_field(record, "engine_model"),
        get_field(record, "system"),
        get_field(record, "document_type"),
        get_field(record, "manual_category"),
        get_field(record, "filename"),
        get_field(record, "path"),
        get_field(record, "folder"),
    ]

    return " ".join(
        value
        for value in fields
        if value
    )


# ============================================================
# CATALOG LOADING
# ============================================================

def load_catalog(
    path: Path = CATALOG_FILE,
) -> list[dict[str, Any]]:
    """Load manual_catalog.json."""

    if not path.exists():

        raise FileNotFoundError(
            f"Catalog not found: {path}\n"
            "Run STEP 17/18 first."
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:

        data = json.load(file)

    if isinstance(data, dict):

        items = data.get(
            "items",
            [],
        )

    elif isinstance(data, list):

        items = data

    else:

        raise ValueError(
            "Unsupported manual_catalog.json structure."
        )

    if not isinstance(items, list):

        raise ValueError(
            "Catalog 'items' must be a list."
        )

    return items


# ============================================================
# QUERY INTELLIGENCE
# ============================================================

def detect_vessels(
    query: str,
) -> list[str]:
    """Detect vessel identifiers such as QL-40."""

    matches = re.findall(
        r"\bQL[\s\-_]?\d+\b",
        str(query).upper(),
    )

    result = []

    for value in matches:

        normalized_value = re.sub(
            r"[\s_]",
            "-",
            value,
        )

        normalized_value = normalized_value.replace(
            "--",
            "-",
        )

        if normalized_value not in result:

            result.append(
                normalized_value
            )

    return result


def detect_manufacturer(
    query: str,
) -> str:
    """Detect known OEM manufacturer."""

    normalized_query = normalize(query)

    for manufacturer in sorted(
        MANUFACTURERS,
        key=len,
        reverse=True,
    ):

        if normalize(manufacturer) in normalized_query:

            return manufacturer

    return ""


def detect_engine_model(
    query: str,
) -> str:
    """Detect common marine engine model patterns."""

    raw = str(query).upper()

    patterns = [

        r"\b\d{1,2}V\s*175D[\s\-]*[A-Z]{2,4}\b",

        r"\bD2676[\s\-]*LE[\s\-]*\d{3}\b",

        r"\b\d{1,2}V\s*2000[\s\-]*M\d+[A-Z]?\b",

        r"\b\d{1,2}V\s*4000[\s\-]*M\d+[A-Z]?\b",

        r"\b\d{1,2}V175D[\s\-]*[A-Z]{2,4}\b",

        r"\b\d{1,2}V2000[\s\-]*M\d+[A-Z]?\b",

        r"\b\d{1,2}V4000[\s\-]*M\d+[A-Z]?\b",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            raw,
        )

        if match:

            return normalize(
                match.group(0)
            )

    return ""


def detect_system(
    query: str,
) -> str:
    """Detect the main equipment/system."""

    normalized_query = normalize(query)

    best_system = ""
    best_length = 0

    for system, aliases in SYSTEM_ALIASES.items():

        for alias in aliases:

            alias_normalized = normalize(
                alias
            )

            if alias_normalized in normalized_query:

                if len(alias_normalized) > best_length:

                    best_system = system
                    best_length = len(
                        alias_normalized
                    )

    return best_system


def detect_document_type(
    query: str,
) -> str:
    """Detect requested document type."""

    normalized_query = normalize(query)

    best_type = ""
    best_length = 0

    for document_type, aliases in DOCUMENT_TYPE_TERMS.items():

        for alias in aliases:

            alias_normalized = normalize(
                alias
            )

            if alias_normalized in normalized_query:

                if len(alias_normalized) > best_length:

                    best_type = document_type
                    best_length = len(
                        alias_normalized
                    )

    return best_type


def extract_fault_terms(
    query: str,
) -> list[str]:
    """Extract known marine troubleshooting terms."""

    normalized_query = normalize(query)

    fault_phrases = [

        "high exhaust temperature",
        "low exhaust temperature",

        "high coolant temperature",
        "high cooling water temperature",

        "low oil pressure",
        "high oil pressure",
        "low lube oil pressure",

        "high crankcase pressure",
        "crankcase pressure",

        "high fuel temperature",
        "low fuel pressure",

        "fuel leakage",

        "oil in coolant",
        "coolant in oil",

        "abnormal noise",
        "engine vibration",

        "overspeed",

        "overheat",
        "overheating",

        "misfire",

        "no start",
        "hard starting",
        "starting problem",

        "high temperature",
        "low pressure",

        "alarm",
        "fault",
        "malfunction",
        "shutdown",
        "trip",

        "injector",
        "turbocharger",
        "exhaust",
        "lubrication",
        "cooling",
        "fuel system",
    ]

    found = []

    for phrase in fault_phrases:

        if normalize(phrase) in normalized_query:

            if phrase not in found:

                found.append(phrase)

    return found


# ============================================================
# MATCHING
# ============================================================

def vessel_match(
    record: dict[str, Any],
    vessel: str,
) -> bool:
    """Check vessel across catalog fields."""

    target = compact(vessel)

    fields = [
        get_field(record, "vessel"),
        get_field(record, "ship"),
        get_field(record, "filename"),
        get_field(record, "path"),
        get_field(record, "folder"),
    ]

    for field in fields:

        if target and target in compact(field):

            return True

    return False


def manufacturer_match(
    record: dict[str, Any],
    manufacturer: str,
) -> bool:
    """Check manufacturer across catalog fields."""

    if not manufacturer:
        return False

    target = compact(manufacturer)

    fields = [
        get_field(record, "manufacturer"),
        get_field(record, "filename"),
        get_field(record, "path"),
        get_field(record, "folder"),
    ]

    for field in fields:

        if target and target in compact(field):

            return True

    return False


def engine_model_match(
    record: dict[str, Any],
    engine_model: str,
) -> bool:
    """Check exact engine model."""

    if not engine_model:
        return False

    target = compact(engine_model)

    fields = [
        get_field(record, "engine_model"),
        get_field(record, "engine"),
        get_field(record, "filename"),
        get_field(record, "path"),
        get_field(record, "folder"),
    ]

    for field in fields:

        if target and target in compact(field):

            return True

    return False


def score_system(
    record: dict[str, Any],
    system: str,
) -> int:
    """Score system relevance."""

    if not system:
        return 0

    aliases = SYSTEM_ALIASES.get(
        system,
        [],
    )

    searchable = normalize(
        record_text(record)
    )

    for alias in aliases:

        if normalize(alias) in searchable:

            return WEIGHTS["system"]

    return 0


def score_fault(
    record: dict[str, Any],
    fault_terms: list[str],
) -> int:
    """Score fault/problem relevance."""

    if not fault_terms:
        return 0

    searchable = normalize(
        record_text(record)
    )

    score = 0

    for fault in fault_terms:

        if normalize(fault) in searchable:

            score += WEIGHTS["fault"]

    return min(
        score,
        WEIGHTS["fault"] * 3,
    )


def score_document_type(
    record: dict[str, Any],
    document_type: str,
) -> int:
    """Score requested document type."""

    if not document_type:
        return 0

    aliases = DOCUMENT_TYPE_TERMS.get(
        document_type,
        [],
    )

    document_text = normalize(
        " ".join(
            [
                get_field(
                    record,
                    "document_type",
                ),
                get_field(
                    record,
                    "manual_category",
                ),
                get_field(
                    record,
                    "filename",
                ),
            ]
        )
    )

    for alias in aliases:

        if normalize(alias) in document_text:

            return WEIGHTS["document_type"]

    return 0


def score_filename(
    record: dict[str, Any],
    query: str,
    engine_model: str,
) -> int:
    """
    Give a small additional bonus when the filename itself
    contains the requested engine model or important query terms.
    """

    filename = normalize(
        get_field(
            record,
            "filename",
        )
    )

    if not filename:
        return 0

    score = 0

    if engine_model:

        if compact(engine_model) in compact(
            filename
        ):

            score += WEIGHTS["filename"]

    query_tokens = tokenize(query)

    filename_tokens = tokenize(filename)

    useful_tokens = {
        token
        for token in query_tokens
        if token not in {
            "THE",
            "AND",
            "FOR",
            "WITH",
            "MAIN",
            "ENGINE",
            "MANUAL",
            "PROBLEM",
            "ALARM",
            "FAULT",
        }
        and len(token) >= 3
    }

    matches = useful_tokens.intersection(
        filename_tokens
    )

    score += min(
        len(matches) * 2,
        10,
    )

    return score


def score_generic_tokens(
    record: dict[str, Any],
    query: str,
) -> int:
    """Small bonus for additional matching tokens."""

    query_tokens = tokenize(query)

    record_tokens = tokenize(
        record_text(record)
    )

    if not query_tokens or not record_tokens:
        return 0

    ignored = {
        "THE",
        "AND",
        "FOR",
        "WITH",
        "MAIN",
        "ENGINE",
        "MANUAL",
        "PROBLEM",
        "ISSUE",
        "CHECK",
        "PLEASE",
        "SHOW",
        "ME",
        "ALARM",
        "FAULT",
    }

    useful_tokens = {
        token
        for token in query_tokens
        if token not in ignored
        and len(token) >= 3
    }

    matches = useful_tokens.intersection(
        record_tokens
    )

    return min(
        len(matches) * 2,
        12,
    )


# ============================================================
# TOTAL SCORE
# ============================================================

def calculate_score(
    record: dict[str, Any],
    query: str,
    vessels: list[str],
    manufacturer: str,
    engine_model: str,
    system: str,
    fault_terms: list[str],
    document_type: str,
) -> tuple[int, list[str]]:
    """Calculate total relevance score."""

    score = 0
    reasons = []

    # --------------------------------------------------------
    # Vessel
    # --------------------------------------------------------

    for vessel in vessels:

        if vessel_match(
            record,
            vessel,
        ):

            score += WEIGHTS["exact_vessel"]

            reasons.append(
                f"Exact vessel: {vessel}"
            )

            break

    # --------------------------------------------------------
    # Manufacturer
    # --------------------------------------------------------

    if manufacturer_match(
        record,
        manufacturer,
    ):

        score += WEIGHTS[
            "exact_manufacturer"
        ]

        reasons.append(
            f"Manufacturer: {manufacturer}"
        )

    # --------------------------------------------------------
    # Exact engine model
    # --------------------------------------------------------

    if engine_model_match(
        record,
        engine_model,
    ):

        score += WEIGHTS[
            "exact_engine_model"
        ]

        reasons.append(
            f"Exact engine model: {engine_model}"
        )

    # --------------------------------------------------------
    # System
    # --------------------------------------------------------

    system_score = score_system(
        record,
        system,
    )

    if system_score:

        score += system_score

        reasons.append(
            f"System: {system}"
        )

    # --------------------------------------------------------
    # Fault
    # --------------------------------------------------------

    fault_score = score_fault(
        record,
        fault_terms,
    )

    if fault_score:

        score += fault_score

        reasons.append(
            "Fault/problem terms matched"
        )

    # --------------------------------------------------------
    # Document type
    # --------------------------------------------------------

    document_score = score_document_type(
        record,
        document_type,
    )

    if document_score:

        score += document_score

        reasons.append(
            f"Document type: {document_type}"
        )

    # --------------------------------------------------------
    # Filename
    # --------------------------------------------------------

    filename_score = score_filename(
        record,
        query,
        engine_model,
    )

    if filename_score:

        score += filename_score

        reasons.append(
            f"Filename relevance: +{filename_score}"
        )

    # --------------------------------------------------------
    # Manual category
    # --------------------------------------------------------

    category = normalize(
        get_field(
            record,
            "manual_category",
        )
    )

    if category:

        if category in normalize(query):

            score += WEIGHTS[
                "manual_category"
            ]

            reasons.append(
                f"Manual category: {category}"
            )

    # --------------------------------------------------------
    # Generic keywords
    # --------------------------------------------------------

    generic_score = score_generic_tokens(
        record,
        query,
    )

    if generic_score:

        score += generic_score

        reasons.append(
            f"Additional keyword matches: +{generic_score}"
        )

    return score, reasons


# ============================================================
# RANKING
# ============================================================

def rank_manuals(
    catalog: list[dict[str, Any]],
    query: str,
    top_k: int = DEFAULT_TOP_K,
) -> list[dict[str, Any]]:
    """Rank all catalog records."""

    vessels = detect_vessels(query)

    manufacturer = detect_manufacturer(
        query
    )

    engine_model = detect_engine_model(
        query
    )

    system = detect_system(query)

    fault_terms = extract_fault_terms(
        query
    )

    document_type = detect_document_type(
        query
    )

    results = []

    for record in catalog:

        score, reasons = calculate_score(
            record=record,
            query=query,
            vessels=vessels,
            manufacturer=manufacturer,
            engine_model=engine_model,
            system=system,
            fault_terms=fault_terms,
            document_type=document_type,
        )

        result = dict(record)

        result["_score"] = score

        result["_reasons"] = reasons

        results.append(result)

    results.sort(
        key=lambda item: (
            item["_score"],
            normalize(
                get_field(
                    item,
                    "filename",
                    "name",
                )
            ),
        ),
        reverse=True,
    )

    return results[:top_k]


# ============================================================
# DISPLAY
# ============================================================

def display_name(
    record: dict[str, Any],
) -> str:
    """Return document filename."""

    name = get_field(
        record,
        "filename",
        "name",
        "title",
        "document_name",
    )

    if name:
        return name

    return "Unknown document"


def display_path(
    record: dict[str, Any],
) -> str:
    """Return document path."""

    path = get_field(
        record,
        "path",
        "relative_path",
        "folder",
    )

    if path:
        return path

    return "Path not available"


def print_query_analysis(
    query: str,
) -> None:
    """Display extracted query intelligence."""

    print()
    print("QUERY INTELLIGENCE")
    print("-" * 60)

    vessels = detect_vessels(query)

    manufacturer = detect_manufacturer(
        query
    )

    engine_model = detect_engine_model(
        query
    )

    system = detect_system(query)

    fault_terms = extract_fault_terms(
        query
    )

    document_type = detect_document_type(
        query
    )

    print(
        "Vessel(s): "
        + (
            ", ".join(vessels)
            if vessels
            else "Not detected"
        )
    )

    print(
        "Manufacturer: "
        + (
            manufacturer
            if manufacturer
            else "Not detected"
        )
    )

    print(
        "Engine model: "
        + (
            engine_model
            if engine_model
            else "Not detected"
        )
    )

    print(
        "System: "
        + (
            system
            if system
            else "Not detected"
        )
    )

    print(
        "Fault/problem: "
        + (
            ", ".join(fault_terms)
            if fault_terms
            else "Not detected"
        )
    )

    print(
        "Document type: "
        + (
            document_type
            if document_type
            else "Not detected"
        )
    )


def print_results(
    results: list[dict[str, Any]],
) -> None:
    """Display ranked manuals."""

    print()
    print("SMART MANUAL SELECTION RESULTS")
    print("=" * 70)

    if not results:

        print("No matching manuals found.")

        return

    for index, result in enumerate(
        results,
        start=1,
    ):

        print()
        print(
            f"{index}. "
            f"Score={result['_score']} | "
            f"{display_name(result)}"
        )

        vessel = get_field(
            result,
            "vessel",
            "ship",
        )

        manufacturer = get_field(
            result,
            "manufacturer",
        )

        engine = get_field(
            result,
            "engine_model",
            "engine",
        )

        system = get_field(
            result,
            "system",
        )

        document_type = get_field(
            result,
            "document_type",
        )

        if vessel:

            print(
                f"   Vessel: {vessel}"
            )

        if manufacturer:

            print(
                f"   Manufacturer: {manufacturer}"
            )

        if engine:

            print(
                f"   Engine: {engine}"
            )

        if system:

            print(
                f"   System: {system}"
            )

        if document_type:

            print(
                f"   Document type: {document_type}"
            )

        reasons = result.get(
            "_reasons",
            [],
        )

        if reasons:

            print(
                "   Why selected: "
                + "; ".join(reasons)
            )

        print(
            f"   Path: {display_path(result)}"
        )


# ============================================================
# SAVE SELECTION
# ============================================================

def save_selection(
    results: list[dict[str, Any]],
    query: str,
    output_file: str,
) -> None:
    """Save selected manuals for later pipeline steps."""

    output = {
        "project": "MarineWise AI",
        "step": "STEP 19",
        "query": query,
        "selected_count": len(results),
        "results": results,
    }

    with open(
        output_file,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            output,
            file,
            indent=2,
            ensure_ascii=False,
        )


# ============================================================
# VERIFICATION
# ============================================================

def verify_step_19(
    catalog: list[dict[str, Any]],
    results: list[dict[str, Any]],
    query: str,
) -> None:
    """Verify STEP 19 intelligent manual selection."""

    assert len(catalog) == 283, (
        f"Expected 283 catalog records, "
        f"found {len(catalog)}."
    )

    assert len(results) > 0, (
        "STEP 19 returned no results."
    )

    top_names = [
        display_name(result).upper()
        for result in results[:3]
    ]

    combined_top = " ".join(
        top_names
    )

    # --------------------------------------------------------
    # Verify engine evidence
    # --------------------------------------------------------

    assert (
        "16V175D" in combined_top
        or any(
            "16V175D"
            in compact(
                get_field(
                    result,
                    "engine_model",
                    "engine",
                )
            )
            for result in results[:3]
        )
    ), (
        "STEP 19 top results do not show "
        "16V175D engine evidence."
    )

    # --------------------------------------------------------
    # Verify QL-40 / engine relevance
    # --------------------------------------------------------

    relevant_top = any(

        (
            "QL40"
            in compact(
                display_name(result)
            )
        )

        or (

            "16V175DMM"
            in compact(
                display_name(result)
            )
        )

        or (

            "16V175D"
            in compact(
                display_name(result)
            )
        )

        or (

            "QL40"
            in compact(
                get_field(
                    result,
                    "vessel",
                    "ship",
                )
            )
        )

        or (

            "16V175DMM"
            in compact(
                get_field(
                    result,
                    "engine_model",
                    "engine",
                )
            )
        )

        for result in results[:3]
    )

    assert relevant_top, (
        "STEP 19 top results do not contain "
        "the expected QL-40 / 16V175D-MM evidence."
    )

    # --------------------------------------------------------
    # Verify actual filename availability
    # --------------------------------------------------------

    filename_available = any(
        display_name(result)
        != "Unknown document"
        for result in results[:3]
    )

    assert filename_available, (
        "STEP 19 cannot read filenames from "
        "the catalog."
    )

    print()
    print("=" * 70)
    print("STEP 19 VERIFICATION")
    print("=" * 70)

    print(
        "Catalog loaded successfully."
    )

    print(
        f"Catalog records: {len(catalog)}"
    )

    print(
        f"Query: {query}"
    )

    print(
        f"Top results returned: {len(results)}"
    )

    print(
        "Exact vessel/engine intelligence detected."
    )

    print(
        "Relevant manuals ranked in top results."
    )

    print(
        "Catalog filenames successfully resolved."
    )

    print()
    print(
        "STEP 19: SUCCESS"
    )

    print(
        "GREEN"
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "MarineWise AI STEP 19 "
            "Advanced Smart Manual Selector"
        )
    )

    parser.add_argument(
        "--query",
        type=str,
        default=(
            "QL-40 MAN 16V175D-MM "
            "main engine high exhaust temperature alarm"
        ),
        help="Marine troubleshooting query.",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of manuals to return.",
    )

    parser.add_argument(
        "--catalog",
        type=str,
        default=str(CATALOG_FILE),
        help="Path to manual_catalog.json.",
    )

    parser.add_argument(
        "--output",
        type=str,
        default="selected_manuals.json",
        help="Output JSON file.",
    )

    args = parser.parse_args()

    catalog_path = Path(
        args.catalog
    )

    print("=" * 70)
    print(
        "MARINEWISE AI - STEP 19"
    )
    print(
        "ADVANCED SMART MANUAL SELECTION"
    )
    print("=" * 70)

    print()
    print(
        f"Catalog file: {catalog_path}"
    )

    catalog = load_catalog(
        catalog_path
    )

    print(
        f"Catalog records: {len(catalog)}"
    )

    print()
    print(
        f"Search query: {args.query}"
    )

    print_query_analysis(
        args.query
    )

    results = rank_manuals(
        catalog=catalog,
        query=args.query,
        top_k=args.top_k,
    )

    print_results(
        results
    )

    save_selection(
        results=results,
        query=args.query,
        output_file=args.output,
    )

    print()
    print(
        f"Selection file created: "
        f"{args.output}"
    )

    verify_step_19(
        catalog=catalog,
        results=results,
        query=args.query,
    )


if __name__ == "__main__":
    main()
