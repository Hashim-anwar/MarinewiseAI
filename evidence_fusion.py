from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


OEM_INPUT = Path("reranked_evidence.json")
WEB_INPUT = Path("tavily_results.json")
OUTPUT_FILE = Path("final_evidence.json")


def clean_text(value: Any) -> str:
    """Normalize text without changing technical identifiers."""

    if value is None:
        return ""

    text = str(value)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object safely."""

    if not path.exists():
        raise FileNotFoundError(
            f"Required input file not found: {path}"
        )

    try:
        data = json.loads(
            path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {path}: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"Expected JSON object in {path}"
        )

    return data


def get_oem_results(data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract OEM evidence from reranked_evidence.json.

    The function supports the current STEP 25 structure and
    a few safe aliases so that minor upstream naming changes
    do not break the fusion layer.
    """

    candidates = [
        data.get("evidence"),
        data.get("results"),
        data.get("reranked_evidence"),
        data.get("items"),
    ]

    for candidate in candidates:
        if isinstance(candidate, list):
            return [
                item
                for item in candidate
                if isinstance(item, dict)
            ]

    return []


def get_web_results(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract web evidence from STEP 27 output."""

    candidate = data.get("web_evidence")

    if isinstance(candidate, list):
        return [
            item
            for item in candidate
            if isinstance(item, dict)
        ]

    return []


def normalize_oem_evidence(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Convert OEM evidence into a stable citation-ready format.

    OEM citations retain manual filename and page information.
    """

    normalized: list[dict[str, Any]] = []

    for index, item in enumerate(results, start=1):
        source_file = clean_text(
            item.get("source_file")
            or item.get("filename")
            or item.get("manual")
        )

        page = (
            item.get("page")
            or item.get("page_number")
            or item.get("source_page")
        )

        text = clean_text(
            item.get("text")
            or item.get("evidence")
            or item.get("content")
        )

        if not text:
            continue

        citation = (
            f"[OEM: {source_file}, Page {page}]"
            if source_file and page is not None
            else f"[OEM: {source_file}]"
            if source_file
            else "[OEM Evidence]"
        )

        normalized.append(
            {
                "evidence_id": f"OEM-{index:03d}",
                "source_type": "OEM",
                "source_file": source_file,
                "page": page,
                "text": text,
                "citation": citation,
                "rerank_score": item.get(
                    "rerank_score"
                ),
                "evidence_rank": item.get(
                    "evidence_rank"
                ),
                "source_priority": 1,
            }
        )

    return normalized


def normalize_web_evidence(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Convert Tavily evidence into a stable citation-ready format.

    Web evidence is explicitly marked as WEB and never as OEM.
    """

    normalized: list[dict[str, Any]] = []

    for index, item in enumerate(results, start=1):
        title = clean_text(
            item.get("title")
        )

        url = clean_text(
            item.get("url")
        )

        evidence = clean_text(
            item.get("evidence")
            or item.get("content")
            or item.get("raw_content")
        )

        if not url or not evidence:
            continue

        citation = (
            f"[WEB: {title}] {url}"
            if title
            else f"[WEB] {url}"
        )

        normalized.append(
            {
                "evidence_id": f"WEB-{index:03d}",
                "source_type": "WEB",
                "title": title,
                "url": url,
                "text": evidence,
                "citation": citation,
                "tavily_score": item.get(
                    "score"
                ),
                "source_priority": 2,
            }
        )

    return normalized


def build_fusion(
    oem_data: dict[str, Any],
    web_data: dict[str, Any],
) -> dict[str, Any]:
    """Build the final citation-ready evidence package."""

    oem_results = get_oem_results(oem_data)
    web_results = get_web_results(web_data)

    oem_evidence = normalize_oem_evidence(
        oem_results
    )

    web_evidence = normalize_web_evidence(
        web_results
    )

    # OEM evidence is intentionally placed first.
    combined = (
        oem_evidence +
        web_evidence
    )

    query = clean_text(
        web_data.get("query")
        or oem_data.get("query")
        or ""
    )

    output = {
        "step": 28,
        "stage": "evidence_and_citation_fusion",
        "query": query,
        "evidence_summary": {
            "total_evidence": len(combined),
            "oem_evidence_count": len(oem_evidence),
            "web_evidence_count": len(web_evidence),
        },
        "source_policy": {
            "oem_priority": True,
            "web_is_not_oem": True,
            "oem_requires_manual_reference": True,
            "web_requires_url": True,
            "source_types_are_separated": True,
        },
        "oem_evidence": oem_evidence,
        "web_evidence": web_evidence,
        "combined_evidence": combined,
    }

    return output


def validate_output(
    output: dict[str, Any],
) -> None:
    """Strict STEP 28 validation."""

    required = [
        "step",
        "stage",
        "evidence_summary",
        "source_policy",
        "oem_evidence",
        "web_evidence",
        "combined_evidence",
    ]

    for key in required:
        if key not in output:
            raise ValueError(
                f"Missing required output key: {key}"
            )

    if output["step"] != 28:
        raise ValueError(
            "Incorrect STEP 28 identifier."
        )

    policy = output["source_policy"]

    if policy.get("oem_priority") is not True:
        raise ValueError(
            "OEM priority policy failed."
        )

    if policy.get("web_is_not_oem") is not True:
        raise ValueError(
            "Web/OEM separation policy failed."
        )

    if policy.get("oem_requires_manual_reference") is not True:
        raise ValueError(
            "OEM reference policy failed."
        )

    if policy.get("web_requires_url") is not True:
        raise ValueError(
            "Web URL policy failed."
        )

    if policy.get("source_types_are_separated") is not True:
        raise ValueError(
            "Source separation policy failed."
        )

    oem = output["oem_evidence"]
    web = output["web_evidence"]
    combined = output["combined_evidence"]

    if not isinstance(oem, list):
        raise ValueError(
            "OEM evidence must be a list."
        )

    if not isinstance(web, list):
        raise ValueError(
            "Web evidence must be a list."
        )

    if not isinstance(combined, list):
        raise ValueError(
            "Combined evidence must be a list."
        )

    # Validate OEM evidence.
    for item in oem:
        if item.get("source_type") != "OEM":
            raise ValueError(
                "OEM evidence contains an invalid source type."
            )

        if not item.get("text"):
            raise ValueError(
                "OEM evidence contains empty text."
            )

        if not item.get("source_file"):
            raise ValueError(
                "OEM evidence is missing source_file."
            )

        if not item.get("citation", "").startswith(
            "[OEM:"
        ) and item.get("citation") != "[OEM Evidence]":
            raise ValueError(
                "Invalid OEM citation format."
            )

    # Validate web evidence.
    for item in web:
        if item.get("source_type") != "WEB":
            raise ValueError(
                "Web evidence contains an invalid source type."
            )

        if not item.get("text"):
            raise ValueError(
                "Web evidence contains empty text."
            )

        if not item.get("url"):
            raise ValueError(
                "Web evidence is missing URL."
            )

        if not item.get("citation", "").startswith(
            "[WEB"
        ):
            raise ValueError(
                "Invalid WEB citation format."
            )

    # Verify combined evidence count.
    if len(combined) != len(oem) + len(web):
        raise ValueError(
            "Combined evidence count does not match "
            "OEM + WEB evidence."
        )

    # Verify source types remain distinct.
    source_types = {
        item.get("source_type")
        for item in combined
    }

    allowed = {"OEM", "WEB"}

    if not source_types.issubset(allowed):
        raise ValueError(
            "Unexpected source type found."
        )


def main() -> None:
    print("=" * 70)
    print("MARINEWISE AI - STEP 28")
    print("EVIDENCE & CITATION FUSION")
    print("=" * 70)

    try:
        oem_data = load_json(OEM_INPUT)
        web_data = load_json(WEB_INPUT)

        output = build_fusion(
            oem_data=oem_data,
            web_data=web_data,
        )

        validate_output(output)

        OUTPUT_FILE.write_text(
            json.dumps(
                output,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        summary = output["evidence_summary"]

        print(
            f"OEM evidence     : "
            f"{summary['oem_evidence_count']}"
        )

        print(
            f"WEB evidence     : "
            f"{summary['web_evidence_count']}"
        )

        print(
            f"Total evidence   : "
            f"{summary['total_evidence']}"
        )

        print(
            f"Output file      : "
            f"{OUTPUT_FILE}"
        )

        print()
        print("Citation policy:")
        print("  OEM priority       : TRUE")
        print("  WEB is not OEM     : TRUE")
        print("  Source separation  : TRUE")
        print("  OEM references     : REQUIRED")
        print("  WEB URLs           : REQUIRED")

        print()
        print("STEP 28: SUCCESS")
        print("GREEN")

    except Exception as exc:
        print()
        print(f"ERROR - {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
