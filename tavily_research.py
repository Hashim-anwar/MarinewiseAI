from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import requests


OUTPUT_FILE = Path("tavily_results.json")
TAVILY_URL = "https://api.tavily.com/search"


def clean_text(value: Any) -> str:
    """Normalize text for safe searching and storage."""
    if value is None:
        return ""

    text = str(value)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def build_search_query(
    manufacturer: str,
    engine_model: str,
    vessel: str,
    system: str,
    fault: str,
) -> str:
    """
    Build a focused marine-engine query.

    The query deliberately includes technical identifiers so that
    Tavily searches relevant marine/OEM material rather than generic
    automotive content.
    """

    parts = [
        clean_text(manufacturer),
        clean_text(engine_model),
        clean_text(vessel),
        clean_text(system),
        clean_text(fault),
    ]

    parts = [p for p in parts if p]

    query = " ".join(parts)

    marine_terms = (
        "marine engine troubleshooting "
        "service manual maintenance alarm technical"
    )

    return f"{query} {marine_terms}".strip()


def tavily_search(
    api_key: str,
    query: str,
    max_results: int = 5,
) -> dict[str, Any]:
    """Execute a controlled Tavily search."""

    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "advanced",
        "topic": "general",
        "max_results": max_results,
        "include_answer": False,
        "include_raw_content": True,
        "include_images": False,
    }

    response = requests.post(
        TAVILY_URL,
        json=payload,
        timeout=60,
    )

    response.raise_for_status()

    return response.json()


def normalize_results(
    raw_response: dict[str, Any],
    query: str,
) -> list[dict[str, Any]]:
    """Convert Tavily results into a stable internal format."""

    normalized: list[dict[str, Any]] = []

    for rank, item in enumerate(
        raw_response.get("results", []),
        start=1,
    ):
        title = clean_text(item.get("title"))
        url = clean_text(item.get("url"))
        content = clean_text(item.get("content"))
        raw_content = clean_text(item.get("raw_content"))

        # Prefer Tavily raw content when available because it generally
        # provides more context than the short search snippet.
        evidence = raw_content or content

        if not title and not url and not evidence:
            continue

        normalized.append(
            {
                "rank": rank,
                "title": title,
                "url": url,
                "content": content,
                "raw_content": raw_content,
                "evidence": evidence,
                "score": item.get("score"),
                "source": "Tavily Web Research",
                "query": query,
            }
        )

    return normalized


def validate_web_evidence(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Remove empty results and clearly unusable entries.

    This is intentionally conservative. Tavily results remain web evidence;
    they are never converted into OEM evidence.
    """

    valid: list[dict[str, Any]] = []

    for result in results:
        url = clean_text(result.get("url"))
        evidence = clean_text(result.get("evidence"))

        if not url:
            continue

        if len(evidence) < 40:
            continue

        valid.append(result)

    return valid


def run_research(
    manufacturer: str,
    engine_model: str,
    vessel: str,
    system: str,
    fault: str,
    max_results: int = 5,
) -> dict[str, Any]:
    """Main Tavily research workflow."""

    api_key = os.getenv("TAVILY_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError(
            "TAVILY_API_KEY is not configured."
        )

    query = build_search_query(
        manufacturer=manufacturer,
        engine_model=engine_model,
        vessel=vessel,
        system=system,
        fault=fault,
    )

    if not query:
        raise ValueError(
            "At least one research input is required."
        )

    print("=" * 70)
    print("MARINEWISE AI - STEP 27")
    print("CONTROLLED TAVILY ONLINE RESEARCH")
    print("=" * 70)

    print(f"Manufacturer : {manufacturer}")
    print(f"Engine       : {engine_model}")
    print(f"Vessel       : {vessel}")
    print(f"System       : {system}")
    print(f"Fault        : {fault}")
    print()
    print(f"Search query : {query}")
    print()

    raw_response = tavily_search(
        api_key=api_key,
        query=query,
        max_results=max_results,
    )

    normalized = normalize_results(
        raw_response,
        query,
    )

    valid_results = validate_web_evidence(
        normalized
    )

    output = {
        "step": 27,
        "research_type": "controlled_online_research",
        "provider": "Tavily",
        "query": query,
        "input": {
            "manufacturer": manufacturer,
            "engine_model": engine_model,
            "vessel": vessel,
            "system": system,
            "fault": fault,
        },
        "web_evidence_count": len(valid_results),
        "web_evidence": valid_results,
        "source_policy": {
            "oem_evidence_priority": True,
            "web_evidence_is_not_oem": True,
            "web_evidence_requires_source_url": True,
            "tavily_is_fallback_or_additional_research": True,
        },
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"Web evidence results : {len(valid_results)}")
    print(f"Output file          : {OUTPUT_FILE}")
    print()

    for item in valid_results:
        print(
            f"[{item['rank']}] "
            f"{item['title'][:90]}"
        )
        print(f"    {item['url']}")
        print()

    print("=" * 70)
    print("STEP 27 RESEARCH COMPLETE")
    print("=" * 70)

    return output


def main() -> None:
    """
    Test inputs for STEP 27.

    These are intentionally based on the existing MarineWise test case.
    """

    manufacturer = "MAN"
    engine_model = "16V175D-MM"
    vessel = "QL-40"
    system = "Main Engine"
    fault = "high exhaust temperature alarm"

    try:
        result = run_research(
            manufacturer=manufacturer,
            engine_model=engine_model,
            vessel=vessel,
            system=system,
            fault=fault,
            max_results=5,
        )

        if not result.get("web_evidence"):
            print(
                "WARNING: Tavily returned no usable web evidence."
            )
            sys.exit(1)

        print()
        print("STEP 27: SUCCESS")
        print("GREEN")

    except requests.HTTPError as exc:
        print()
        print("ERROR: Tavily HTTP request failed.")
        print(str(exc))
        sys.exit(1)

    except Exception as exc:
        print()
        print(f"ERROR: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
