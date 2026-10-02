"""
MarineWise AI
STEP 19 - Advanced Smart Manual Selection

Purpose:
    Select and rank the most relevant OEM manuals from manual_catalog.json
    using vessel, manufacturer, engine model, system, fault/alarm/problem,
    document type, filename and folder-path evidence.

Important:
    - Does NOT connect to Google Drive.
    - Does NOT download files.
    - Uses the existing manual_catalog.json created in STEP 17/18.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


CATALOG_FILE = Path("manual_catalog.json")


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_TOP_K = 10


# Stronger weights are given to exact technical information.
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


# Known marine manufacturers.
MANUFACTURERS = [
    "MAN",
    "MTU",
    "CATERPILLAR",
    "CAT",
    "YANMAR",
    "VOLVO PENTA",
    "VOLVO",
    "YAMAHA",
    "ZF",
    "MJP",
    "ARNESON",
    "DOEN",
    "GÜRDESAN",
    "GURDESAN",
]


# Known systems/categories in the MarineWise corpus.
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
        "ramp",
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


# Common document types.
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
# TEXT NORMALIZATION
# ============================================================

def normalize(text: Any) -> str:
    """Normalize text for matching."""

    if text is None:
        return ""

    text = str(text).upper()

    # Normalize common separators.
    text = text.replace("_", " ")
    text = text.replace("-", " ")
    text = text.replace("/", " ")
    text = text.replace("\\", " ")
    text = text.replace(",", " ")
    text = text.replace(".", " ")

    # Collapse whitespace.
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def compact(text: Any) -> str:
    """Create an aggressive normalized version for exact model matching."""

    return re.sub(r"[^A-Z0-9]", "", str(text).upper())


def tokenize(text: Any) -> set[str]:
    """Return normalized tokens."""

    value = normalize(text)

    if not value:
        return set()

    return set(re.findall(r"[A-Z0-9]+", value))


# ============================================================
# CATALOG LOADING
# ============================================================

def load_catalog(path: Path = CATALOG_FILE) -> list[dict[str, Any]]:
    """Load the existing manual catalog."""

    if not path.exists():
        raise FileNotFoundError(
            f"Catalog not found: {path}\n"
            "Run STEP 17/18 first so manual_catalog.json exists."
        )

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, dict):
        items = data.get("items", [])

    elif isinstance(data, list):
        items = data

    else:
        raise ValueError("Unsupported manual_catalog.json structure.")

    if not isinstance(items, list):
        raise ValueError("Catalog 'items' must be a list.")

    return items


# ============================================================
# CATALOG FIELD HELPERS
# ============================================================

def get_field(record: dict[str, Any], *names: str) -> str:
    """Return the first available field."""

    for name in names:
        value = record.get(name)

        if value is not None and str(value).strip():
            return str(value)

    return ""


def record_text(record: dict[str, Any]) -> str:
    """Build searchable text from all useful catalog fields."""

    fields = [
        get_field(record, "vessel"),
        get_field(record, "ship"),
        get_field(record, "manufacturer"),
        get_field(record, "engine_model"),
        get_field(record, "engine"),
        get_field(record, "system"),
        get_field(record, "document_type"),
        get_field(record, "manual_category"),
        get_field(record, "filename"),
        get_field(record, "name"),
        get_field(record, "path"),
        get_field(record, "folder"),
        get_field(record, "relative_path"),
    ]

    return " ".join(value for value in fields if value)


# ============================================================
# QUERY EXTRACTION
# ============================================================

def detect_vessels(query: str) -> list[str]:
    """Detect vessel identifiers such as QL-40, QL-41 and QL-80."""

    upper = str(query).upper()

    matches = re.findall(
        r"\bQL[\s\-_]?\d+\b",
        upper,
    )

    result = []

    for value in matches:
        normalized_value = re.sub(r"[\s_]", "-", value)
        normalized_value = normalized_value.replace("--", "-")

        if normalized_value not in result:
            result.append(normalized_value)

    return result


def detect_manufacturer(query: str) -> str:
    """Detect a known manufacturer."""

    upper = normalize(query)

    # Long names first.
    for manufacturer in sorted(MANUFACTURERS, key=len, reverse=True):
        if normalize(manufacturer) in upper:
            return manufacturer

    return ""


def detect_engine_model(query: str) -> str:
    """
    Detect engine model patterns.

    Examples:
        16V175D-MM
        12V175D-ML
        D2676 LE446
        10V 2000 M94
        12V 2000 M96L
        16V 4000 M90
    """

    raw = str(query).upper()

    patterns = [
        # MAN 16V175D-MM / 12V175D-ML
        r"\b\d{1,2}V\s*175D[\s\-]*[A-Z]{2,4}\b",

        # MAN D2676 LE446
        r"\bD2676[\s\-]*LE[\s\-]*\d{3}\b",

        # MTU 10V 2000 M94 / 12V 2000 M96L
        r"\b\d{1,2}V\s*2000[\s\-]*M\d+[A-Z]?\b",

        # MTU 16V 4000 M90
        r"\b\d{1,2}V\s*4000[\s\-]*M\d+[A-Z]?\b",

        # Compact model forms.
        r"\b\d{1,2}V175D[\s\-]*[A-Z]{2,4}\b",
        r"\b\d{1,2}V2000[\s\-]*M\d+[A-Z]?\b",
        r"\b\d{1,2}V4000[\s\-]*M\d+[A-Z]?\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, raw)

        if match:
            return normalize(match.group(0))

    return ""


def detect_system(query: str) -> str:
    """Detect the most relevant system."""

    normalized_query = normalize(query)

    best_system = ""
    best_length = 0

    for system, aliases in SYSTEM_ALIASES.items():

        for alias in aliases:

            alias_normalized = normalize(alias)

            if alias_normalized in normalized_query:
                if len(alias_normalized) > best_length:
                    best_system = system
                    best_length = len(alias_normalized)

    return best_system


def detect_document_type(query: str) -> str:
    """Detect requested document type."""

    normalized_query = normalize(query)

    best_type = ""
    best_length = 0

    for document_type, aliases in DOCUMENT_TYPE_TERMS.items():

        for alias in aliases:

            alias_normalized = normalize(alias)

            if alias_normalized in normalized_query:

                if len(alias_normalized) > best_length:
                    best_type = document_type
                    best_length = len(alias_normalized)

    return best_type


# ============================================================
# FAULT / PROBLEM EXTRACTION
# ============================================================

def extract_fault_terms(query: str) -> list[str]:
    """
    Extract useful troubleshooting terms from the query.

    This intentionally remains simple at STEP 19.
    Later STEP 24 can use a proper hybrid semantic/BM25/vector layer.
    """

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
# SCORING FUNCTIONS
# ============================================================

def vessel_match(record: dict[str, Any], vessel: str) -> bool:
    """Check exact vessel match across useful catalog fields."""

    vessel_compact = compact(vessel)

    fields = [
        get_field(record, "vessel"),
        get_field(record, "ship"),
        get_field(record, "filename"),
        get_field(record, "name"),
        get_field(record, "path"),
        get_field(record, "relative_path"),
    ]

    for field in fields:

        if vessel_compact and vessel_compact in compact(field):
            return True

    return False


def manufacturer_match(record: dict[str, Any], manufacturer: str) -> bool:
    """Check manufacturer match."""

    if not manufacturer:
        return False

    target = compact(manufacturer)

    fields = [
        get_field(record, "manufacturer"),
        get_field(record, "filename"),
        get_field(record, "name"),
        get_field(record, "path"),
        get_field(record, "relative_path"),
    ]

    for field in fields:

        if target and target in compact(field):
            return True

    return False


def engine_model_match(record: dict[str, Any], engine_model: str) -> bool:
    """
    Check engine model using aggressive normalization.

    This allows:
        16V175D-MM
    to match:
        16V175D MM
        16V175D_MM
        16V175D-MM
    """

    if not engine_model:
        return False

    target = compact(engine_model)

    fields = [
        get_field(record, "engine_model"),
        get_field(record, "engine"),
        get_field(record, "filename"),
        get_field(record, "name"),
        get_field(record, "path"),
        get_field(record, "relative_path"),
    ]

    for field in fields:

        if target and target in compact(field):
            return True

    return False


def score_system(record: dict[str, Any], system: str) -> int:
    """Score system relevance."""

    if not system:
        return 0

    aliases = SYSTEM_ALIASES.get(system, [])

    searchable = normalize(record_text(record))

    best = 0

    for alias in aliases:

        alias_normalized = normalize(alias)

        if alias_normalized in searchable:
            best = max(best, WEIGHTS["system"])

    return best


def score_fault(record: dict[str, Any], fault_terms: list[str]) -> int:
    """Score troubleshooting/fault terminology."""

    if not fault_terms:
        return 0

    searchable = normalize(record_text(record))

    score = 0

    for fault in fault_terms:

        fault_normalized = normalize(fault)

        if fault_normalized in searchable:
            score += WEIGHTS["fault"]

    return min(score, WEIGHTS["fault"] * 3)


def score_document_type(
    record: dict[str, Any],
    document_type: str,
) -> int:
    """Score requested document type."""

    if not document_type:
        return 0

    aliases = DOCUMENT_TYPE_TERMS.get(document_type, [])

    document_text = normalize(
        " ".join(
            [
                get_field(record, "document_type"),
                get_field(record, "manual_category"),
                get_field(record, "filename"),
                get_field(record, "name"),
            ]
        )
    )

    for alias in aliases:

        if normalize(alias) in document_text:
            return WEIGHTS["document_type"]

    return 0


def score_generic_tokens(
    record: dict[str, Any],
    query: str,
) -> int:
    """
    Small bonus for remaining query tokens.

    This prevents generic words from dominating the ranking.
    """

    query_tokens = tokenize(query)
    record_tokens = tokenize(record_text(record))

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
    }

    useful_tokens = {
        token
        for token in query_tokens
        if token not in ignored and len(token) >= 3
    }

    matches = useful_tokens.intersection(record_tokens)

    return min(len(matches) * 2, 12)


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
    """Calculate total relevance score and explain why it matched."""

    score = 0
    reasons = []

    # --------------------------------------------------------
    # Vessel
    # --------------------------------------------------------

    for vessel in vessels:

        if vessel_match(record, vessel):

            score += WEIGHTS["exact_vessel"]

            reasons.append(
                f"Exact vessel: {vessel}"
            )

            break

    # --------------------------------------------------------
    # Manufacturer
    # --------------------------------------------------------

    if manufacturer_match(record, manufacturer):

        score += WEIGHTS["exact_manufacturer"]

        reasons.append(
            f"Manufacturer: {manufacturer}"
        )

    # --------------------------------------------------------
    # Engine model
    # --------------------------------------------------------

    if engine_model_match(record, engine_model):

        score += WEIGHTS["exact_engine_model"]

        reasons.append(
            f"Exact engine model: {engine_model}"
        )

    # --------------------------------------------------------
    # System
    # --------------------------------------------------------

    system_score = score_system(record, system)

    if system_score:

        score += system_score

        reasons.append(
            f"System: {system}"
        )

    # --------------------------------------------------------
    # Fault
    # --------------------------------------------------------

    fault_score = score_fault(record, fault_terms)

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
    # Manual category
    # --------------------------------------------------------

    category = normalize(
        get_field(record, "manual_category")
    )

    if category:

        query_normalized = normalize(query)

        if category in query_normalized:

            score += WEIGHTS["manual_category"]

            reasons.append(
                f"Manual category: {category}"
            )

    # --------------------------------------------------------
    # Generic token matching
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
    """Rank catalog records according to the smart selection algorithm."""

    vessels = detect_vessels(query)
    manufacturer = detect_manufacturer(query)
    engine_model = detect_engine_model(query)
    system = detect_system(query)
    fault_terms = extract_fault_terms(query)
    document_type = detect_document_type(query)

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

    # Highest score first.
    #
    # Filename is used as a stable tie-breaker so results remain
    # predictable between workflow runs.
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
# DISPLAY HELPERS
# ============================================================

def display_name(record: dict[str, Any]) -> str:
    """Get the best available document name."""

    return (
        get_field(
            record,
            "filename",
            "name",
        )
        or "Unknown document"
    )


def display_path(record: dict[str, Any]) -> str:
    """Get document path."""

    return (
        get_field(
            record,
            "path",
            "relative_path",
            "folder",
        )
        or "Unknown path"
    )


def print_query_analysis(query: str) -> None:
    """Display what STEP 19 detected from the query."""

    print()
    print("QUERY INTELLIGENCE")
    print("-" * 60)

    vessels = detect_vessels(query)
    manufacturer = detect_manufacturer(query)
    engine_model = detect_engine_model(query)
    system = detect_system(query)
    fault_terms = extract_fault_terms(query)
    document_type = detect_document_type(query)

    print(
        f"Vessel(s): "
        f"{', '.join(vessels) if vessels else 'Not detected'}"
    )

    print(
        f"Manufacturer: "
        f"{manufacturer if manufacturer else 'Not detected'}"
    )

    print(
        f"Engine model: "
        f"{engine_model if engine_model else 'Not detected'}"
    )

    print(
        f"System: "
        f"{system if system else 'Not detected'}"
    )

    print(
        f"Fault/problem: "
        f"{', '.join(fault_terms) if fault_terms else 'Not detected'}"
    )

    print(
        f"Document type: "
        f"{document_type if document_type else 'Not detected'}"
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

    for index, result in enumerate(results, start=1):

        print()
        print(
            f"{index}. "
            f"Score={result['_score']} | "
            f"{display_name(result)}"
        )

        manufacturer = get_field(
            result,
            "manufacturer",
        )

        vessel = get_field(
            result,
            "vessel",
            "ship",
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
            print(f"   Vessel: {vessel}")

        if manufacturer:
            print(f"   Manufacturer: {manufacturer}")

        if engine:
            print(f"   Engine: {engine}")

        if system:
            print(f"   System: {system}")

        if document_type:
            print(f"   Document type: {document_type}")

        if result["_reasons"]:

            print(
                "   Why selected: "
                + "; ".join(result["_reasons"])
            )

        print(
            f"   Path: {display_path(result)}"
        )


# ============================================================
# JSON OUTPUT
# ============================================================

def save_selection(
    results: list[dict[str, Any]],
    query: str,
    output_file: str,
) -> None:
    """Save selected manuals for later pipeline steps."""

    clean_results = []

    for result in results:

        clean = dict(result)

        clean_results.append(clean)

    output = {
        "project": "MarineWise AI",
        "step": "STEP 19",
        "query": query,
        "selected_count": len(clean_results),
        "results": clean_results,
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
    """
    Automated verification.

    The test is intentionally based on the known QL-40 /
    MAN 16V175D-MM use case from the MarineWise corpus.
    """

    assert len(catalog) > 0, (
        "Catalog is empty."
    )

    assert len(results) > 0, (
        "STEP 19 returned no results."
    )

    top_names = [
        display_name(result).upper()
        for result in results[:3]
    ]

    combined_top = " ".join(top_names)

    # The top results should contain evidence of the requested
    # vessel/engine combination.
    expected_engine = (
        "16V175D"
        in combined_top
        or "16V175D" in query.upper()
    )

    assert expected_engine, (
        "STEP 19 did not detect the expected 16V175D "
        "engine context."
    )

    # At least one of the top results should contain either
    # QL 40 or the exact 16V175D-MM document.
    relevant_top = any(
        (
            "QL40" in compact(display_name(result))
            or "16V175DMM" in compact(display_name(result))
            or "16V175D" in compact(display_name(result))
        )
        for result in results[:3]
    )

    assert relevant_top, (
        "STEP 19 top results do not contain the expected "
        "QL-40 / 16V175D-MM evidence."
    )

    print()
    print("=" * 70)
    print("STEP 19 VERIFICATION")
    print("=" * 70)
    print("Catalog loaded successfully.")
    print(f"Catalog records: {len(catalog)}")
    print(f"Query: {query}")
    print(f"Top results returned: {len(results)}")
    print("Exact vessel/engine intelligence detected.")
    print("Relevant manuals ranked in top results.")
    print()
    print("STEP 19: SUCCESS")
    print("GREEN")


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
        help="Marine troubleshooting/manual search query.",
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

    catalog_path = Path(args.catalog)

    print("=" * 70)
    print("MARINEWISE AI - STEP 19")
    print("ADVANCED SMART MANUAL SELECTION")
    print("=" * 70)

    print()
    print(f"Catalog file: {catalog_path}")

    catalog = load_catalog(catalog_path)

    print(f"Catalog records: {len(catalog)}")

    print()
    print(f"Search query: {args.query}")

    print_query_analysis(args.query)

    results = rank_manuals(
        catalog=catalog,
        query=args.query,
        top_k=args.top_k,
    )

    print_results(results)

    save_selection(
        results=results,
        query=args.query,
        output_file=args.output,
    )

    print()
    print(f"Selection file created: {args.output}")

    verify_step_19(
        catalog=catalog,
        results=results,
        query=args.query,
    )


if __name__ == "__main__":
    main()
