from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_QUERY = (
    "QL-40 MAN 16V175D-MM main engine "
    "high exhaust temperature alarm"
)


def load_json(path: str | Path) -> Any:
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"Required file not found: {file_path}"
        )

    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def extract_list(data: Any, keys: list[str]) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        return []

    for key in keys:
        value = data.get(key)

        if isinstance(value, list):
            return value

    return []


def build_troubleshooting_workflow(
    query: str,
    final_evidence_file: str = "final_evidence.json",
) -> dict[str, Any]:

    evidence_data = load_json(final_evidence_file)

    oem_evidence = extract_list(
        evidence_data,
        ["oem_evidence", "oem_results"],
    )

    web_evidence = extract_list(
        evidence_data,
        ["web_evidence", "web_results"],
    )

    combined_evidence = extract_list(
        evidence_data,
        ["combined_evidence", "evidence"],
    )

    if not oem_evidence:
        raise ValueError(
            "No OEM evidence is available for troubleshooting."
        )

    if not combined_evidence:
        raise ValueError(
            "No combined evidence is available."
        )

    workflow = {
        "step": 29,
        "stage": "marine_troubleshooting_workflow",
        "status": "READY_FOR_GROQ",
        "query": query,

        "input": {
            "query": query,
        },

        "evidence": {
            "oem_count": len(oem_evidence),
            "web_count": len(web_evidence),
            "combined_count": len(combined_evidence),
        },

        "source_policy": {
            "oem_priority": True,
            "web_is_not_oem": True,
            "oem_required_for_technical_conclusion": True,
            "web_used_as_fallback_or_additional_research": True,
            "citations_required": True,
        },

        "workflow_sequence": [
            "User provides marine engine fault or alarm",
            "Identify relevant vessel, manufacturer and engine",
            "Select relevant OEM manuals",
            "Retrieve evidence using hybrid RAG",
            "Re-rank technical evidence",
            "Perform controlled web research when required",
            "Fuse OEM and WEB evidence",
            "Generate evidence-based troubleshooting response",
        ],

        "troubleshooting_output_sections": [
            "PROBLEM IDENTIFICATION",
            "ENGINE AND EQUIPMENT",
            "RELEVANT OEM EVIDENCE",
            "PROBABLE CAUSES",
            "TROUBLESHOOTING STEPS",
            "CHECKS AND MEASUREMENTS",
            "CORRECTIVE ACTION",
            "PARTS AND TOOLS",
            "OEM REFERENCES",
            "EVIDENCE STATUS",
            "SAFETY NOTE",
        ],

        "oem_evidence": oem_evidence,
        "web_evidence": web_evidence,
        "combined_evidence": combined_evidence,

        "next_stage": {
            "component": "Groq Evidence-Based Answer Engine",
            "input_file": final_evidence_file,
            "output_expected": "troubleshooting_answer.json",
        },
    }

    return workflow


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MarineWise AI troubleshooting workflow"
    )

    parser.add_argument(
        "--query",
        default=DEFAULT_QUERY,
        help="Marine troubleshooting query",
    )

    parser.add_argument(
        "--evidence",
        default="final_evidence.json",
        help="STEP 28 final evidence file",
    )

    parser.add_argument(
        "--output",
        default="troubleshooting_workflow.json",
        help="Workflow output JSON file",
    )

    args = parser.parse_args()

    result = build_troubleshooting_workflow(
        query=args.query,
        final_evidence_file=args.evidence,
    )

    output_path = Path(args.output)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            result,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print("=" * 70)
    print("STEP 29A VERIFICATION")
    print("=" * 70)
    print(f"Query              : {args.query}")
    print(
        f"OEM evidence       : "
        f"{result['evidence']['oem_count']}"
    )
    print(
        f"WEB evidence       : "
        f"{result['evidence']['web_count']}"
    )
    print(
        f"Combined evidence  : "
        f"{result['evidence']['combined_count']}"
    )
    print(
        f"Output             : {output_path}"
    )
    print(
        f"Status             : {result['status']}"
    )
    print()
    print("STEP 29A: SUCCESS")
    print("GREEN")


if __name__ == "__main__":
    main()
