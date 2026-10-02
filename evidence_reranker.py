from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


INPUT_FILE = Path("hybrid_results.json")
OUTPUT_FILE = Path("reranked_evidence.json")

TOP_N = 8
MIN_SCORE = 0.20


TEST_QUERY = (
    "QL-40 MAN 16V175D-MM main engine "
    "high exhaust temperature alarm"
)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value)
    ).strip()


def tokenize(text: str) -> list[str]:
    return re.findall(
        r"[A-Za-z0-9]+(?:[-_/][A-Za-z0-9]+)*",
        text.upper()
    )


def important_terms(query: str) -> list[str]:
    terms = tokenize(query)

    stop_words = {
        "THE",
        "AND",
        "OR",
        "FOR",
        "WITH",
        "FROM",
        "THIS",
        "THAT",
        "MAIN",
        "ENGINE",
    }

    return [
        term
        for term in terms
        if term not in stop_words
    ]


def exact_identifier_bonus(
    query: str,
    text: str
) -> float:
    query_upper = query.upper()
    text_upper = text.upper()

    bonus = 0.0

    identifiers = [
        "QL-40",
        "QL 40",
        "MAN",
        "16V175D-MM",
        "16V175D MM",
    ]

    for identifier in identifiers:
        if identifier.upper() in query_upper:
            if identifier.upper() in text_upper:
                bonus += 0.08

    return min(bonus, 0.30)


def fault_term_score(
    query: str,
    text: str
) -> float:
    query_terms = set(important_terms(query))
    text_terms = set(tokenize(text))

    if not query_terms:
        return 0.0

    matches = len(query_terms.intersection(text_terms))

    return min(
        matches / max(len(query_terms), 1),
        1.0
    )


def evidence_quality_score(
    text: str
) -> float:
    """
    Detect whether the chunk contains useful technical
    evidence rather than only headings or navigation text.
    """

    text_upper = text.upper()

    technical_terms = [
        "ALARM",
        "FAULT",
        "WARNING",
        "CAUSE",
        "CAUSES",
        "CHECK",
        "CHECKING",
        "INSPECT",
        "INSPECTION",
        "TROUBLESHOOT",
        "TROUBLESHOOTING",
        "PRESSURE",
        "TEMPERATURE",
        "EXHAUST",
        "SENSOR",
        "SENSORS",
        "ENGINE",
        "COOLANT",
        "FUEL",
        "LUBRICATING",
        "OIL",
        "INJECTOR",
        "VALVE",
        "FILTER",
        "REPLACE",
        "REPAIR",
        "MEASURE",
        "TEST",
        "SPECIFICATION",
    ]

    matches = sum(
        1
        for term in technical_terms
        if term in text_upper
    )

    return min(matches / 8.0, 1.0)


def page_evidence_bonus(text: str) -> float:
    """
    Slight bonus for chunks that contain actual procedural
    or diagnostic language.
    """

    text_upper = text.upper()

    patterns = [
        r"\bCHECK\b",
        r"\bINSPECT\b",
        r"\bMEASURE\b",
        r"\bVERIFY\b",
        r"\bCAUSE\b",
        r"\bCORRECTIVE ACTION\b",
        r"\bTROUBLESHOOTING\b",
        r"\bFAULT\b",
        r"\bALARM\b",
    ]

    matches = sum(
        1
        for pattern in patterns
        if re.search(pattern, text_upper)
    )

    return min(matches * 0.03, 0.15)


def calculate_score(
    result: dict[str, Any],
    query: str
) -> tuple[float, dict[str, float]]:

    text = normalize_text(result.get("text", ""))

    rrf_score = float(
        result.get("rrf_score", 0.0)
    )

    fault_score = fault_term_score(
        query,
        text
    )

    identifier_bonus = exact_identifier_bonus(
        query,
        text
    )

    quality_score = evidence_quality_score(
        text
    )

    procedure_bonus = page_evidence_bonus(
        text
    )

    # RRF provides the retrieval signal.
    # Additional signals improve evidence relevance.
    final_score = (
        (rrf_score * 8.0)
        + (fault_score * 0.35)
        + identifier_bonus
        + (quality_score * 0.20)
        + procedure_bonus
    )

    components = {
        "rrf": rrf_score,
        "fault_match": fault_score,
        "identifier_bonus": identifier_bonus,
        "quality": quality_score,
        "procedure_bonus": procedure_bonus,
        "final": final_score,
    }

    return final_score, components


def load_results() -> list[dict[str, Any]]:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Missing required file: {INPUT_FILE}"
        )

    with INPUT_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:
        data = json.load(file)

    if isinstance(data, dict):
        if "results" in data:
            results = data["results"]
        elif "items" in data:
            results = data["items"]
        else:
            raise ValueError(
                "hybrid_results.json does not contain "
                "'results' or 'items'."
            )
    elif isinstance(data, list):
        results = data
    else:
        raise ValueError(
            "Unexpected hybrid_results.json format."
        )

    if not results:
        raise ValueError(
            "No hybrid retrieval results found."
        )

    return results


def main() -> None:

    print("=" * 70)
    print("MARINEWISE AI - STEP 25")
    print("EVIDENCE RE-RANKING + QUALITY FILTERING")
    print("=" * 70)

    print()
    print("Test query:")
    print(TEST_QUERY)

    print()
    print("Loading hybrid retrieval results...")

    results = load_results()

    print(
        f"GREEN - hybrid results loaded: {len(results)}"
    )

    reranked = []

    for result in results:

        text = normalize_text(
            result.get("text", "")
        )

        if not text:
            continue

        final_score, components = calculate_score(
            result,
            TEST_QUERY
        )

        enriched = dict(result)

        enriched["rerank_score"] = round(
            final_score,
            6
        )

        enriched["score_components"] = {
            key: round(value, 6)
            for key, value in components.items()
        }

        reranked.append(enriched)

    if not reranked:
        raise RuntimeError(
            "No evidence remained after initial validation."
        )

    reranked.sort(
        key=lambda item: item["rerank_score"],
        reverse=True
    )

    filtered = [
        item
        for item in reranked
        if item["rerank_score"] >= MIN_SCORE
    ]

    if not filtered:
        raise RuntimeError(
            "No evidence passed the quality threshold."
        )

    final_results = filtered[:TOP_N]

    # Add final evidence rank.
    for rank, item in enumerate(
        final_results,
        start=1
    ):
        item["evidence_rank"] = rank

    output = {
        "query": TEST_QUERY,
        "input_results": len(results),
        "reranked_results": len(reranked),
        "quality_threshold": MIN_SCORE,
        "final_results": len(final_results),
        "results": final_results,
    }

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            output,
            file,
            indent=2,
            ensure_ascii=False
        )

    print()
    print("=" * 70)
    print("RERANKED OEM EVIDENCE")
    print("=" * 70)

    for item in final_results:

        print()
        print(
            f"{item['evidence_rank']}. "
            f"Score={item['rerank_score']:.4f}"
        )

        print(
            f"   RRF: "
            f"{item.get('rrf_score', 0):.6f}"
        )

        print(
            f"   Source: "
            f"{item.get('source_file', 'Unknown')}"
        )

        print(
            f"   Page: "
            f"{item.get('page', 'Unknown')}"
        )

        print(
            f"   Vessel: "
            f"{item.get('vessel', 'Unknown')}"
        )

        print(
            f"   Engine: "
            f"{item.get('engine_model', 'Unknown')}"
        )

        print(
            f"   Evidence quality: "
            f"{item['score_components']['quality']:.3f}"
        )

    print()
    print("=" * 70)
    print("STEP 25 VERIFICATION")
    print("=" * 70)

    assert len(reranked) > 0
    print("GREEN - evidence candidates loaded.")

    assert len(filtered) > 0
    print("GREEN - quality filtering verified.")

    assert len(final_results) > 0
    print(
        f"GREEN - final evidence results: "
        f"{len(final_results)}"
    )

    for item in final_results:
        assert "source_file" in item
        assert "page" in item
        assert "text" in item
        assert "rerank_score" in item
        assert "evidence_rank" in item

    print(
        "GREEN - source/page/text metadata preserved."
    )

    assert OUTPUT_FILE.exists()

    print(
        "GREEN - reranked_evidence.json created."
    )

    print()
    print("STEP 25: SUCCESS")
    print("GREEN")


if __name__ == "__main__":
    main()
