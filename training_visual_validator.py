from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import fitz


AI_LABEL = "AI Training Illustration — Not an OEM Figure"


VISUAL_SECTIONS = {
    "ENGINE INTRODUCTION",
    "SYSTEM OVERVIEW",
    "COMPONENT IDENTIFICATION",
    "TOOLS REQUIRED",
    "SAFETY PRECAUTIONS",
    "REMOVAL PROCEDURE",
    "INSPECTION",
    "INSTALLATION",
    "TROUBLESHOOTING",
    "PRACTICAL EXERCISE",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize(value: Any) -> str:
    return str(value or "").strip()


def resolve_pdf(manual_dir: Path, source_file: str) -> Path | None:
    direct = manual_dir / source_file

    if direct.exists():
        return direct

    source_name = Path(source_file).name

    matches = list(manual_dir.rglob(source_name))

    if matches:
        return matches[0]

    return None


def render_page(
    pdf_path: Path,
    page_number: int,
    output_dir: Path,
    section_name: str,
) -> Path | None:

    try:
        document = fitz.open(pdf_path)

        zero_based_page = max(0, page_number - 1)

        if zero_based_page >= len(document):
            document.close()
            return None

        page = document.load_page(zero_based_page)

        matrix = fitz.Matrix(1.5, 1.5)

        safe_section = re.sub(
            r"[^A-Za-z0-9]+",
            "_",
            section_name,
        ).strip("_")

        safe_source = re.sub(
            r"[^A-Za-z0-9]+",
            "_",
            pdf_path.stem,
        ).strip("_")

        filename = (
            f"{safe_section}_"
            f"{safe_source}_"
            f"page_{page_number}.png"
        )

        output_path = output_dir / filename

        page.get_pixmap(
            matrix=matrix,
            alpha=False,
        ).save(str(output_path))

        document.close()

        return output_path

    except Exception as exc:
        print(
            f"WARNING: Could not render "
            f"{pdf_path.name} page {page_number}: {exc}"
        )

        return None


def analyze_page(
    pdf_path: Path,
    page_number: int,
) -> dict[str, Any]:

    result: dict[str, Any] = {
        "page": page_number,
        "usable_oem_visual": False,
        "visual_score": 0,
        "text_length": 0,
        "image_count": 0,
        "drawing_count": 0,
        "figure_mentions": 0,
        "list_of_figures": False,
        "reasons": [],
    }

    try:
        document = fitz.open(pdf_path)

        zero_based_page = max(0, page_number - 1)

        if zero_based_page >= len(document):
            result["reasons"].append(
                "Page number outside PDF range."
            )
            document.close()
            return result

        page = document.load_page(zero_based_page)

        text = page.get_text("text") or ""

        result["text_length"] = len(text)

        image_list = page.get_images(full=True)
        result["image_count"] = len(image_list)

        drawings = page.get_drawings()
        result["drawing_count"] = len(drawings)

        lower_text = text.lower()

        figure_mentions = len(
            re.findall(
                r"\bfigure\b|\billustration\b|\bdiagram\b|\bschematic\b",
                lower_text,
            )
        )

        result["figure_mentions"] = figure_mentions

        list_of_figures = (
            "list of figures" in lower_text
            or "lof" in lower_text[:500].lower()
        )

        result["list_of_figures"] = list_of_figures

        score = 0

        if result["image_count"] > 0:
            score += 8

        if result["drawing_count"] >= 5:
            score += 5
        elif result["drawing_count"] > 0:
            score += 2

        if figure_mentions > 0:
            score += 2

        if figure_mentions >= 2:
            score += 2

        if len(text) < 7000:
            score += 1

        if list_of_figures:
            score -= 8

        result["visual_score"] = score

        reasons = []

        if result["image_count"] > 0:
            reasons.append(
                f"embedded images={result['image_count']}"
            )

        if result["drawing_count"] > 0:
            reasons.append(
                f"vector drawings={result['drawing_count']}"
            )

        if figure_mentions > 0:
            reasons.append(
                f"figure-related terms={figure_mentions}"
            )

        if list_of_figures:
            reasons.append(
                "page appears to be a List of Figures/index"
            )

        if score >= 6 and not list_of_figures:
            result["usable_oem_visual"] = True
            reasons.append(
                "meets OEM visual quality threshold"
            )
        else:
            reasons.append(
                "does not meet OEM visual quality threshold"
            )

        result["reasons"] = reasons

        document.close()

        return result

    except Exception as exc:
        result["reasons"].append(
            f"Analysis error: {exc}"
        )
        return result


def create_ai_request(
    section: str,
    input_data: dict[str, Any],
) -> dict[str, Any]:

    topic = normalize(
        input_data.get("topic")
    )

    engine = normalize(
        input_data.get("engine_model")
    )

    manufacturer = normalize(
        input_data.get("manufacturer")
    )

    vessel = normalize(
        input_data.get("vessel")
    )

    section_description = {
        "ENGINE INTRODUCTION":
            "generic training illustration showing the major external engine systems and their functional relationships",

        "SYSTEM OVERVIEW":
            "generic training illustration showing the fuel system flow concept without exact OEM layout or dimensions",

        "COMPONENT IDENTIFICATION":
            "generic training illustration identifying typical fuel injection system components",

        "TOOLS REQUIRED":
            "generic training illustration of workshop tool categories used during injector maintenance",

        "SAFETY PRECAUTIONS":
            "generic marine engine maintenance safety illustration showing PPE, isolation and safe working practices",

        "REMOVAL PROCEDURE":
            "generic training illustration showing the conceptual sequence of removing a fuel injector",

        "INSPECTION":
            "generic training illustration showing visual inspection concepts for an injector and related components",

        "INSTALLATION":
            "generic training illustration showing the conceptual sequence of installing a fuel injector",

        "TROUBLESHOOTING":
            "generic training illustration showing a conceptual diagnostic workflow for a fuel injection fault",

        "PRACTICAL EXERCISE":
            "generic workshop training illustration showing technicians performing a supervised injector maintenance exercise",
    }.get(
        section,
        "generic marine-engine training illustration",
    )

    return {
        "section": section,
        "visual_source": "AI_FALLBACK",
        "status": "AI_REQUEST_CREATED",
        "label": AI_LABEL,
        "prompt": (
            f"Create a clean professional educational illustration for "
            f"marine-engine technician training. "
            f"Manufacturer context: {manufacturer}. "
            f"Engine context: {engine}. "
            f"Vessel context: {vessel}. "
            f"Training topic: {topic}. "
            f"Visual purpose: {section_description}. "
            f"Keep the illustration generic and instructional. "
            f"Do not reproduce an OEM drawing. "
            f"Do not invent or display technical specifications, "
            f"part numbers, torque values, pressures, temperatures, "
            f"dimensions, clearances, wiring details, exact component "
            f"locations, exact OEM geometry or exact OEM layout. "
            f"Do not present the illustration as an OEM figure. "
            f"Include the visible label: "
            f"'{AI_LABEL}'."
        ),
        "restrictions": [
            "Generic training illustration only.",
            "Not an OEM figure.",
            "No invented technical specifications.",
            "No invented part numbers.",
            "No invented torque values.",
            "No invented pressures.",
            "No invented temperatures.",
            "No invented dimensions.",
            "No invented clearances.",
            "No invented wiring details.",
            "No exact OEM layout.",
            "No exact OEM geometry.",
            "Technical specifications must come from OEM evidence.",
        ],
    }


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Validate OEM visual candidates and create "
            "controlled AI fallback requests."
        )
    )

    parser.add_argument(
        "--planner",
        required=True,
        help="STEP 32B ai_visual_requests.json",
    )

    parser.add_argument(
        "--manual-dir",
        required=True,
        help="Directory containing downloaded OEM manuals.",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Output JSON file.",
    )

    parser.add_argument(
        "--visual-dir",
        default="validated_oem_visuals",
        help="Directory for validated OEM page renders.",
    )

    args = parser.parse_args()

    planner_path = Path(args.planner)
    manual_dir = Path(args.manual_dir)
    output_path = Path(args.output)
    visual_dir = Path(args.visual_dir)

    if not planner_path.exists():
        raise SystemExit(
            f"ERROR: Planner file not found: {planner_path}"
        )

    if not manual_dir.exists():
        raise SystemExit(
            f"ERROR: Manual directory not found: {manual_dir}"
        )

    visual_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    planner = load_json(planner_path)

    input_data = planner.get(
        "input",
        {},
    )

    section_results = planner.get(
        "section_results",
        {},
    )

    validated_sections: dict[str, Any] = {}

    ai_requests: list[dict[str, Any]] = []

    oem_visual_sections: list[str] = []

    ai_fallback_sections: list[str] = []

    total_candidates = 0

    usable_oem_visuals = 0

    for section in VISUAL_SECTIONS:

        section_data = section_results.get(
            section,
            {},
        )

        candidates = section_data.get(
            "oem_candidates",
            [],
        )

        section_output = {
            "visual_source": None,
            "status": None,
            "validated_candidates": [],
            "selected_oem_visual": None,
            "ai_request_created": False,
        }

        total_candidates += len(candidates)

        for candidate in candidates:

            source_file = normalize(
                candidate.get("source_file")
            )

            page_number = int(
                candidate.get("page", 0) or 0
            )

            if not source_file or page_number <= 0:
                continue

            pdf_path = resolve_pdf(
                manual_dir,
                source_file,
            )

            candidate_result = {
                "source_file": source_file,
                "page": page_number,
                "planner_score": candidate.get(
                    "score",
                    0,
                ),
            }

            if pdf_path is None:

                candidate_result[
                    "validation_status"
                ] = "PDF_NOT_FOUND"

                candidate_result[
                    "usable_oem_visual"
                ] = False

                candidate_result[
                    "reasons"
                ] = [
                    "Referenced OEM PDF was not found."
                ]

                section_output[
                    "validated_candidates"
                ].append(candidate_result)

                continue

            analysis = analyze_page(
                pdf_path,
                page_number,
            )

            candidate_result.update(
                {
                    "validation_status":
                        "VALIDATED",
                    "usable_oem_visual":
                        analysis[
                            "usable_oem_visual"
                        ],
                    "visual_score":
                        analysis[
                            "visual_score"
                        ],
                    "image_count":
                        analysis[
                            "image_count"
                        ],
                    "drawing_count":
                        analysis[
                            "drawing_count"
                        ],
                    "figure_mentions":
                        analysis[
                            "figure_mentions"
                        ],
                    "list_of_figures":
                        analysis[
                            "list_of_figures"
                        ],
                    "reasons":
                        analysis[
                            "reasons"
                        ],
                }
            )

            if analysis[
                "usable_oem_visual"
            ]:

                rendered = render_page(
                    pdf_path,
                    page_number,
                    visual_dir,
                    section,
                )

                if rendered:

                    candidate_result[
                        "rendered_image"
                    ] = str(rendered)

                if section_output[
                    "selected_oem_visual"
                ] is None:

                    section_output[
                        "selected_oem_visual"
                    ] = candidate_result

            section_output[
                "validated_candidates"
            ].append(candidate_result)

        selected = section_output[
            "selected_oem_visual"
        ]

        if selected:

            section_output[
                "visual_source"
            ] = "OEM"

            section_output[
                "status"
            ] = "OEM_VISUAL_VALIDATED"

            oem_visual_sections.append(
                section
            )

            usable_oem_visuals += 1

        else:

            request = create_ai_request(
                section,
                input_data,
            )

            ai_requests.append(
                request
            )

            section_output[
                "visual_source"
            ] = "AI_FALLBACK"

            section_output[
                "status"
            ] = "AI_FALLBACK_REQUIRED"

            section_output[
                "ai_request_created"
            ] = True

            ai_fallback_sections.append(
                section
            )

        validated_sections[
            section
        ] = section_output

    output = {
        "step": 32,
        "substep": "32C",
        "stage": "oem_visual_quality_validator",
        "status": "SUCCESS",
        "input": input_data,
        "manual_count": planner.get(
            "manual_count",
            0,
        ),
        "visual_sections": len(
            VISUAL_SECTIONS
        ),
        "candidate_count": total_candidates,
        "usable_oem_visuals": usable_oem_visuals,
        "oem_visual_sections": len(
            oem_visual_sections
        ),
        "ai_fallback_sections": len(
            ai_fallback_sections
        ),
        "ai_visual_label": AI_LABEL,
        "section_results": validated_sections,
        "ai_visual_requests": ai_requests,
        "visual_policy": {
            "oem_visual_first": True,
            "ai_visual_only_when_oem_visual_is_unavailable": True,
            "ai_visual_is_generic_training_illustration": True,
            "ai_visual_not_oem_figure": True,
            "technical_specs_must_come_from_oem": True,
            "fake_oem_figures_blocked": True,
            "list_of_figures_pages_rejected": True,
            "visual_page_must_be_validated": True,
        },
    }

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            output,
            f,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print("STEP 32C - OEM VISUAL QUALITY VALIDATOR")
    print()
    print(
        "OEM visual sections:",
        len(oem_visual_sections),
    )

    print(
        "AI fallback sections:",
        len(ai_fallback_sections),
    )

    print(
        "AI requests:",
        len(ai_requests),
    )

    print(
        "Validated OEM visuals:",
        usable_oem_visuals,
    )

    print()
    print("OUTPUT:", output_path)
    print()
    print("STEP 32C SUCCESS - GREEN")


if __name__ == "__main__":
    main()
