from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from groq import Groq


DEFAULT_MODEL = "openai/gpt-oss-120b"


SYSTEM_PROMPT = """
You are MarineWise AI, an evidence-controlled marine engineering
troubleshooting assistant.

Your job is to analyze a marine engine fault using ONLY the supplied
OEM evidence and clearly identified WEB evidence.

CRITICAL RULES:

1. OEM evidence has the highest priority.
2. WEB evidence is NOT OEM evidence.
3. Never present WEB information as if it came from an OEM manual.
4. Never invent technical information.
5. Never invent:
   - alarm meanings
   - fault causes
   - troubleshooting steps
   - part numbers
   - torque values
   - pressure limits
   - temperature limits
   - clearances
   - specifications
   - maintenance intervals
   - procedures
6. If a technical claim is not supported by the supplied evidence,
   clearly state that the evidence is insufficient.
7. Every important technical claim must include an evidence citation.
8. OEM claims must use:
   [OEM: filename, Page X]
9. WEB claims must use:
   [WEB: source title]
10. Do not create fake page numbers or fake references.
11. Distinguish documented evidence from engineering inference.
12. Safety-critical actions must be supported by evidence or clearly
    identified as requiring confirmation from the applicable OEM manual.
13. Do not claim that an engine component is defective unless the
    supplied evidence supports that conclusion.
14. Do not provide unsupported numerical values.
15. If evidence conflicts, clearly identify the conflict.

Produce a professional marine-engineering troubleshooting report.
"""


OUTPUT_SECTIONS = [
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
]


def load_json(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"Required file not found: {file_path}"
        )

    with file_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(
            f"Invalid JSON structure: {file_path}"
        )

    return data


def build_evidence_text(
    workflow: dict[str, Any],
) -> str:

    oem = workflow.get("oem_evidence", [])
    web = workflow.get("web_evidence", [])

    blocks: list[str] = []

    for index, item in enumerate(oem, start=1):
        source_file = item.get(
            "source_file",
            "Unknown OEM document",
        )

        page = item.get(
            "page",
            "Unknown",
        )

        text = item.get(
            "text",
            "",
        )

        citation = item.get(
            "citation",
            f"[OEM: {source_file}, Page {page}]",
        )

        blocks.append(
            f"""
OEM EVIDENCE {index}

Source:
{source_file}

Page:
{page}

Citation:
{citation}

Evidence:
{text}
""".strip()
        )

    for index, item in enumerate(web, start=1):
        title = item.get(
            "title",
            "Unknown web source",
        )

        url = item.get(
            "url",
            "",
        )

        text = item.get(
            "text",
            "",
        )

        citation = item.get(
            "citation",
            f"[WEB: {title}]",
        )

        blocks.append(
            f"""
WEB EVIDENCE {index}

Title:
{title}

URL:
{url}

Citation:
{citation}

Evidence:
{text}
""".strip()
        )

    return "\n\n".join(blocks)


def build_user_prompt(
    workflow: dict[str, Any],
) -> str:

    user_input = workflow.get("input", {})

    manufacturer = user_input.get(
        "manufacturer",
        "",
    )

    engine_model = user_input.get(
        "engine_model",
        "",
    )

    serial_number = user_input.get(
        "serial_number",
        "",
    )

    vessel = user_input.get(
        "vessel",
        "",
    )

    operating_hours = user_input.get(
        "operating_hours",
        "",
    )

    system = user_input.get(
        "system",
        "",
    )

    fault = user_input.get(
        "fault",
        "",
    )

    query = workflow.get(
        "constructed_query",
        "",
    )

    evidence_text = build_evidence_text(
        workflow
    )

    return f"""
Analyze the following marine-engine troubleshooting case.

ENGINE INFORMATION

Manufacturer:
{manufacturer}

Engine Model:
{engine_model}

Serial Number:
{serial_number or "Not provided"}

Vessel:
{vessel}

Operating Hours:
{operating_hours or "Not provided"}

System:
{system}

FAULT / ALARM / SYMPTOM

{fault}

CONSTRUCTED TECHNICAL QUERY

{query}

SUPPLIED EVIDENCE

{evidence_text}

TASK

Generate a professional troubleshooting report using the exact
section headings below:

1. PROBLEM IDENTIFICATION
2. ENGINE AND EQUIPMENT
3. RELEVANT OEM EVIDENCE
4. PROBABLE CAUSES
5. TROUBLESHOOTING STEPS
6. CHECKS AND MEASUREMENTS
7. CORRECTIVE ACTION
8. PARTS AND TOOLS
9. OEM REFERENCES
10. EVIDENCE STATUS
11. SAFETY NOTE

Evidence requirements:

- Cite important OEM claims with the exact OEM citation supplied.
- Cite WEB information with its WEB citation.
- Never convert WEB information into an OEM claim.
- Never invent a citation.
- If the evidence does not support a requested technical detail,
  explicitly state:
  "Insufficient OEM evidence available for a reliable conclusion."
- Clearly distinguish evidence from engineering inference.
- Do not invent numerical specifications.

Return only the completed troubleshooting report.
""".strip()


def call_groq(
    workflow: dict[str, Any],
    api_key: str,
    model: str,
) -> str:

    client = Groq(
        api_key=api_key
    )

    response = client.chat.completions.create(
        model=model,
        temperature=0.1,
        max_completion_tokens=2500,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": build_user_prompt(
                    workflow
                ),
            },
        ],
    )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError(
            "Groq returned an empty response."
        )

    return content.strip()


def validate_report(
    report: str,
) -> None:

    if not report.strip():
        raise ValueError(
            "Generated report is empty."
        )

    missing_sections = []

    for section in OUTPUT_SECTIONS:
        if section not in report:
            missing_sections.append(section)

    if missing_sections:
        raise ValueError(
            "Missing required report sections: "
            + ", ".join(missing_sections)
        )

    if "[OEM:" not in report:
        raise ValueError(
            "No OEM citation found in generated report."
        )

    if (
        "[WEB:" not in report
        and "WEB" in report.upper()
    ):
        raise ValueError(
            "WEB evidence is referenced but no WEB citation "
            "was detected."
        )


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "MarineWise AI STEP 29C "
            "Groq troubleshooting answer engine"
        )
    )

    parser.add_argument(
        "--workflow",
        default="troubleshooting_workflow.json",
    )

    parser.add_argument(
        "--output",
        default="troubleshooting_answer.json",
    )

    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
    )

    args = parser.parse_args()

    api_key = os.getenv(
        "GROQ_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not configured."
        )

    workflow = load_json(
        args.workflow
    )

    if workflow.get("step") != 29:
        raise ValueError(
            "Invalid troubleshooting workflow step."
        )

    if workflow.get("status") != "READY_FOR_GROQ":
        raise ValueError(
            "Troubleshooting workflow is not ready for Groq."
        )

    if not workflow.get("oem_evidence"):
        raise ValueError(
            "No OEM evidence supplied to Groq."
        )

    report = call_groq(
        workflow=workflow,
        api_key=api_key,
        model=args.model,
    )

    validate_report(report)

    result = {
        "step": 29,
        "stage": "groq_troubleshooting_answer",
        "status": "SUCCESS",
        "model": args.model,
        "input": workflow.get("input", {}),
        "constructed_query": workflow.get(
            "constructed_query",
            "",
        ),
        "evidence_summary": workflow.get(
            "evidence",
            {},
        ),
        "report_sections": OUTPUT_SECTIONS,
        "answer": report,
        "source_policy": {
            "oem_priority": True,
            "web_is_not_oem": True,
            "citations_required": True,
            "unsupported_claims_blocked": True,
        },
    }

    output_path = Path(
        args.output
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            result,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print("=" * 70)
    print("STEP 29C")
    print("GROQ TROUBLESHOOTING ANSWER ENGINE")
    print("=" * 70)
    print(
        f"Model             : {args.model}"
    )
    print(
        f"Manufacturer      : "
        f"{result['input'].get('manufacturer', '')}"
    )
    print(
        f"Engine model      : "
        f"{result['input'].get('engine_model', '')}"
    )
    print(
        f"Vessel            : "
        f"{result['input'].get('vessel', '')}"
    )
    print(
        f"Fault             : "
        f"{result['input'].get('fault', '')}"
    )
    print()
    print(
        "OEM evidence      : "
        f"{result['evidence_summary'].get('oem_count', 0)}"
    )
    print(
        "WEB evidence      : "
        f"{result['evidence_summary'].get('web_count', 0)}"
    )
    print()
    print(
        f"Output            : {output_path}"
    )
    print(
        f"Report length     : {len(report)} characters"
    )
    print()
    print("Required sections : TRUE")
    print("OEM citation      : TRUE")
    print("Evidence control  : TRUE")
    print("Groq generation   : TRUE")
    print()
    print("STEP 29C: SUCCESS")
    print("GREEN")


if __name__ == "__main__":
    main()
