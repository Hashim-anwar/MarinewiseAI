from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import fitz


AI_LABEL = "AI Training Illustration — Not an OEM Figure"


VISUAL_SECTIONS = {
    "ENGINE INTRODUCTION": [
        "engine",
        "diesel",
        "marine",
        "engine overview",
        "engine arrangement",
    ],
    "SYSTEM OVERVIEW": [
        "system",
        "fuel",
        "circuit",
        "diagram",
        "schematic",
        "flow",
        "fuel system",
    ],
    "COMPONENT IDENTIFICATION": [
        "injector",
        "fuel",
        "component",
        "assembly",
        "cylinder",
        "nozzle",
    ],
    "TOOLS REQUIRED": [
        "tool",
        "special tool",
        "equipment",
        "maintenance tool",
    ],
    "SAFETY PRECAUTIONS": [
        "safety",
        "warning",
        "caution",
        "hazard",
        "protective",
    ],
    "REMOVAL PROCEDURE": [
        "remove",
        "removal",
        "injector",
        "disassembly",
        "dismantling",
    ],
    "INSPECTION": [
        "inspection",
        "check",
        "measure",
        "wear",
        "injector",
        "nozzle",
    ],
    "INSTALLATION": [
        "install",
        "installation",
        "assembly",
        "injector",
        "mounting",
    ],
    "TROUBLESHOOTING": [
        "fault",
        "troubleshooting",
        "alarm",
        "fuel",
        "injector",
        "failure",
    ],
    "PRACTICAL EXERCISE": [
        "exercise",
        "practical",
        "training",
        "maintenance",
        "inspection",
        "procedure",
    ],
}


FORBIDDEN_TECHNICAL_DETAILS = [
    "part number",
    "part no",
    "torque",
    "pressure",
    "bar",
    "psi",
    "dimension",
    "dimensions",
    "clearance",
    "tolerance",
    "voltage",
    "current",
    "temperature limit",
    "rpm",
    "calibration value",
    "calibration setting",
    "wiring",
    "pin number",
    "connector pin",
    "exact component location",
    "exact mounting location",
    "oem drawing",
    "oem figure",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="MarineWise AI - STEP 32B Visual Fallback Planner"
    )

    parser.add_argument(
        "--answer",
        default="training_answer.json",
    )

    parser.add_argument(
        "--workflow",
        default="training_workflow.json",
    )

    parser.add_argument(
        "--manual-dir",
        default="selected_manuals",
    )

    parser.add_argument(
        "--output",
        default="ai_visual_requests.json",
    )

    return parser.parse_args()


def load_json(
    path: str | Path,
) -> dict[str, Any]:

    file = Path(path)

    if not file.exists():
        raise FileNotFoundError(
            f"Required file not found: {file}"
        )

    return json.loads(
        file.read_text(
            encoding="utf-8"
        )
    )


def clean(value: Any) -> str:

    if value is None:
        return ""

    return str(value).strip()


def normalize_text(value: str) -> str:

    value = clean(value)

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def find_manual_files(
    manual_dir: Path,
) -> list[Path]:

    if not manual_dir.exists():
        return []

    files = []

    for pattern in (
        "*.pdf",
        "*.PDF",
    ):

        files.extend(
            manual_dir.rglob(pattern)
        )

    return sorted(
        set(files)
    )


def extract_training_sections(
    answer: dict[str, Any],
) -> dict[str, str]:

    content = clean(
        answer.get(
            "training_content",
            "",
        )
    )

    if not content:
        return {}

    section_names = list(
        VISUAL_SECTIONS.keys()
    )

    normalized = {
        section.upper(): section
        for section in section_names
    }

    lines = content.splitlines()

    positions = []

    for index, line in enumerate(lines):

        current = (
            line.strip()
            .upper()
            .replace(":", "")
        )

        if current in normalized:

            positions.append(
                (
                    index,
                    normalized[current],
                )
            )

    sections = {}

    for index, (
        start,
        name,
    ) in enumerate(positions):

        if index + 1 < len(positions):

            end = positions[index + 1][0]

        else:

            end = len(lines)

        body = "\n".join(
            lines[start + 1:end]
        ).strip()

        sections[name] = body

    return sections


def search_oem_visual_evidence(
    manual_files: list[Path],
    keywords: list[str],
    max_results: int = 5,
) -> list[dict[str, Any]]:

    matches = []

    for pdf_path in manual_files:

        document = None

        try:

            document = fitz.open(
                pdf_path
            )

            for page_number in range(
                len(document)
            ):

                page = document[
                    page_number
                ]

                text = page.get_text(
                    "text"
                )

                if not text:
                    continue

                lower = text.lower()

                matched_terms = []

                for keyword in keywords:

                    if keyword.lower() in lower:

                        matched_terms.append(
                            keyword
                        )

                if not matched_terms:
                    continue

                score = len(
                    matched_terms
                )

                # Stronger signal for pages containing
                # explicit technical-visual language.
                visual_terms = [
                    "figure",
                    "diagram",
                    "schematic",
                    "illustration",
                    "assembly",
                    "section",
                    "circuit",
                    "flow",
                    "component",
                ]

                visual_hits = sum(
                    1
                    for term in visual_terms
                    if term in lower
                )

                score += visual_hits * 2

                matches.append(
                    {
                        "source_file": pdf_path.name,
                        "page": page_number + 1,
                        "score": score,
                        "matched_terms": matched_terms,
                        "visual_terms": [
                            term
                            for term in visual_terms
                            if term in lower
                        ],
                        "text_preview": normalize_text(
                            text
                        )[:800],
                    }
                )

        except Exception as exc:

            print(
                "WARNING - Could not inspect "
                f"{pdf_path.name}: {exc}"
            )

        finally:

            if document is not None:
                document.close()

    matches.sort(
        key=lambda item: (
            -item["score"],
            item["source_file"],
            item["page"],
        )
    )

    return matches[:max_results]


def has_forbidden_technical_request(
    text: str,
) -> list[str]:

    lower = text.lower()

    return [
        item
        for item in FORBIDDEN_TECHNICAL_DETAILS
        if item in lower
    ]


def build_safe_ai_prompt(
    section: str,
    topic: str,
    manufacturer: str,
    engine_model: str,
    vessel: str,
) -> str:

    context_parts = []

    if manufacturer:
        context_parts.append(
            f"Manufacturer: {manufacturer}"
        )

    if engine_model:
        context_parts.append(
            f"Engine model: {engine_model}"
        )

    if vessel:
        context_parts.append(
            f"Vessel/equipment: {vessel}"
        )

    context = "\n".join(
        context_parts
    )

    prompt = f"""
Create a clean educational marine-engine training illustration
for the training section:

{section}

Training topic:
{topic}

{context}

Purpose:
Help a marine technician visually understand the general concept,
workflow, component relationship, inspection concept, or safe
maintenance sequence described in the training material.

IMPORTANT VISUAL SAFETY RULES:

1. This must be a generic educational illustration.
2. Do NOT reproduce an OEM drawing.
3. Do NOT claim that the illustration is an OEM figure.
4. Do NOT invent technical specifications.
5. Do NOT show part numbers.
6. Do NOT show torque values.
7. Do NOT show pressure values.
8. Do NOT show dimensions.
9. Do NOT show clearances or tolerances.
10. Do NOT show wiring diagrams or connector pinouts.
11. Do NOT show exact OEM component locations.
12. Do NOT invent calibration values.
13. Do NOT invent model-specific measurements.
14. Use generic labels such as:
    "Fuel Injector",
    "Fuel Supply",
    "Engine Cylinder",
    "Inspection Area",
    "Removal Direction",
    "Installation Direction",
    when appropriate.
15. Keep the illustration technically plausible but intentionally
    generic.
16. Use a clean professional marine-engine training style.
17. Include the following visible label:

{AI_LABEL}

The illustration should improve technician understanding without
replacing the OEM manual.
""".strip()

    return prompt


def main() -> None:

    args = parse_args()

    answer = load_json(
        args.answer
    )

    workflow = load_json(
        args.workflow
    )

    input_data = workflow.get(
        "input",
        {},
    )

    manufacturer = clean(
        input_data.get(
            "manufacturer"
        )
    )

    engine_model = clean(
        input_data.get(
            "engine_model"
        )
    )

    topic = clean(
        input_data.get(
            "topic"
        )
    )

    vessel = clean(
        input_data.get(
            "vessel"
        )
    )

    manual_dir = Path(
        args.manual_dir
    )

    manual_files = find_manual_files(
        manual_dir
    )

    if not manual_files:

        raise RuntimeError(
            "No selected OEM PDF manuals were found."
        )

    sections = extract_training_sections(
        answer
    )

    if not sections:

        raise RuntimeError(
            "No visual training sections were found "
            "in training_answer.json."
        )

    print("=" * 70)
    print("MARINEWISE AI - STEP 32B")
    print("AI VISUAL FALLBACK PLANNER")
    print("=" * 70)

    print(
        f"OEM manuals available : {len(manual_files)}"
    )

    print(
        f"Visual sections        : {len(sections)}"
    )

    requests = []

    section_results = {}

    for section, content in sections.items():

        keywords = VISUAL_SECTIONS.get(
            section,
            [],
        )

        oem_matches = search_oem_visual_evidence(
            manual_files,
            keywords,
            max_results=5,
        )

        # ----------------------------------------------------------
        # OEM-FIRST DECISION
        # ----------------------------------------------------------

        suitable_oem = bool(
            oem_matches
            and oem_matches[0].get("score", 0) >= 3
        )

        if suitable_oem:

            section_results[section] = {
                "visual_source": "OEM",
                "status": "OEM_VISUAL_AVAILABLE",
                "oem_candidates": oem_matches,
                "ai_request_created": False,
            }

            print(
                f"{section}: OEM visual available"
            )

            continue

        # ----------------------------------------------------------
        # AI FALLBACK
        # ----------------------------------------------------------

        ai_prompt = build_safe_ai_prompt(
            section=section,
            topic=topic,
            manufacturer=manufacturer,
            engine_model=engine_model,
            vessel=vessel,
        )

        forbidden = has_forbidden_technical_request(
            ai_prompt
        )

        if forbidden:

            raise RuntimeError(
                "Unsafe AI visual prompt detected in "
                f"{section}: {forbidden}"
            )

        request = {
            "request_id": (
                f"AI-VISUAL-{len(requests) + 1:03d}"
            ),
            "section": section,
            "visual_source": "AI_FALLBACK",
            "status": "PENDING_GENERATION",
            "label": AI_LABEL,
            "training_topic": topic,
            "manufacturer": manufacturer,
            "engine_model": engine_model,
            "vessel": vessel,
            "purpose": (
                "Generic educational illustration only. "
                "OEM manual remains the authoritative source "
                "for technical specifications and procedures."
            ),
            "ai_prompt": ai_prompt,
            "oem_search_attempt": {
                "keywords": keywords,
                "candidate_count": len(
                    oem_matches
                ),
                "candidates": oem_matches,
            },
            "technical_specification_policy": {
                "part_numbers": False,
                "torque_values": False,
                "pressure_values": False,
                "dimensions": False,
                "clearances": False,
                "tolerances": False,
                "wiring_details": False,
                "connector_pinouts": False,
                "calibration_values": False,
                "exact_oem_layout": False,
                "exact_component_location": False,
            },
            "source_policy": {
                "oem_visual_priority": True,
                "ai_is_fallback_only": True,
                "ai_visual_is_not_oem": True,
                "oem_manual_is_authoritative": True,
            },
        }

        requests.append(
            request
        )

        section_results[section] = {
            "visual_source": "AI_FALLBACK",
            "status": "AI_VISUAL_REQUEST_CREATED",
            "oem_candidates": oem_matches,
            "ai_request_created": True,
            "request_id": request[
                "request_id"
            ],
        }

        print(
            f"{section}: AI fallback request created"
        )

    output = {
        "step": 32,
        "substep": "32B",
        "stage": "ai_visual_fallback_planner",
        "status": "SUCCESS",
        "input": {
            "manufacturer": manufacturer,
            "engine_model": engine_model,
            "topic": topic,
            "vessel": vessel,
        },
        "manual_count": len(
            manual_files
        ),
        "visual_sections": len(
            sections
        ),
        "oem_visual_sections": sum(
            1
            for item in section_results.values()
            if item["visual_source"] == "OEM"
        ),
        "ai_fallback_sections": len(
            requests
        ),
        "ai_visual_label": AI_LABEL,
        "section_results": section_results,
        "ai_visual_requests": requests,
        "visual_policy": {
            "oem_visual_first": True,
            "ai_visual_only_when_oem_visual_is_unavailable": True,
            "ai_visual_is_generic_training_illustration": True,
            "ai_visual_not_oem_figure": True,
            "technical_specs_must_come_from_oem": True,
            "fake_oem_figures_blocked": True,
        },
    }

    output_path = Path(
        args.output
    )

    output_path.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 70)
    print("STEP 32B COMPLETE")
    print("=" * 70)

    print(
        f"OEM visual sections : "
        f"{output['oem_visual_sections']}"
    )

    print(
        f"AI fallback sections: "
        f"{output['ai_fallback_sections']}"
    )

    print(
        f"AI requests         : "
        f"{len(requests)}"
    )

    print(
        f"Output              : "
        f"{output_path}"
    )

    print()
    print("STEP 32B: SUCCESS")
    print("GREEN")


if __name__ == "__main__":
    main()
