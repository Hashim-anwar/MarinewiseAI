from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ASSESSMENT_AREAS = [
    "ENGINE FUNDAMENTALS",
    "SYSTEM KNOWLEDGE",
    "COMPONENT IDENTIFICATION",
    "TOOLS AND SAFETY",
    "MAINTENANCE PROCEDURE",
    "INSPECTION",
    "INSTALLATION",
    "TROUBLESHOOTING",
    "OEM SPECIFICATIONS",
    "PRACTICAL APPLICATION",
]


AREA_KEYWORDS = {
    "ENGINE FUNDAMENTALS": [
        "engine",
        "diesel",
        "cylinder",
        "combustion",
        "engine operation",
        "engine principle",
    ],
    "SYSTEM KNOWLEDGE": [
        "fuel system",
        "fuel circuit",
        "lubrication",
        "cooling system",
        "air system",
        "exhaust",
        "fuel supply",
        "fuel injection",
        "system",
        "circuit",
    ],
    "COMPONENT IDENTIFICATION": [
        "injector",
        "injection valve",
        "fuel pump",
        "filter",
        "fuel line",
        "component",
        "assembly",
        "cylinder head",
        "nozzle",
        "sensor",
        "valve",
    ],
    "TOOLS AND SAFETY": [
        "tool",
        "special tool",
        "safety",
        "warning",
        "caution",
        "danger",
        "protective",
        "lockout",
        "personal protective",
    ],
    "MAINTENANCE PROCEDURE": [
        "maintenance",
        "service",
        "replacement",
        "remove",
        "removal",
        "install",
        "installation",
        "procedure",
        "disassembly",
        "assembly",
    ],
    "INSPECTION": [
        "inspection",
        "inspect",
        "check",
        "checking",
        "measure",
        "measurement",
        "wear",
        "condition",
        "test",
    ],
    "INSTALLATION": [
        "installation",
        "install",
        "assembly",
        "mounting",
        "fitting",
        "tighten",
        "torque",
        "connection",
    ],
    "TROUBLESHOOTING": [
        "troubleshooting",
        "fault",
        "failure",
        "malfunction",
        "alarm",
        "error",
        "cause",
        "symptom",
        "remedy",
        "corrective",
    ],
    "OEM SPECIFICATIONS": [
        "specification",
        "technical data",
        "technical specification",
        "torque",
        "pressure",
        "temperature",
        "clearance",
        "dimension",
        "limit",
        "tolerance",
        "capacity",
        "value",
    ],
    "PRACTICAL APPLICATION": [
        "procedure",
        "maintenance",
        "inspection",
        "fault",
        "troubleshooting",
        "replacement",
        "installation",
        "service",
        "check",
        "test",
    ],
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")

    return data


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def get_training_context(training: dict[str, Any]) -> dict[str, str]:
    input_data = training.get("input")

    if not isinstance(input_data, dict):
        input_data = {}

    manufacturer = normalize(
        input_data.get("manufacturer")
        or training.get("manufacturer")
        or "Unknown"
    )

    engine_model = normalize(
        input_data.get("engine_model")
        or training.get("engine_model")
        or "Unknown"
    )

    topic = normalize(
        input_data.get("topic")
        or training.get("topic")
        or "Marine engine maintenance"
    )

    vessel = normalize(
        input_data.get("vessel")
        or training.get("vessel")
        or "Unknown"
    )

    technician_level = normalize(
        input_data.get("technician_level")
        or training.get("technician_level")
        or "Basic"
    )

    return {
        "manufacturer": manufacturer,
        "engine_model": engine_model,
        "topic": topic,
        "vessel": vessel,
        "technician_level": technician_level,
    }


def get_selected_pdf_files(manual_dir: Path) -> list[Path]:
    if not manual_dir.exists():
        raise FileNotFoundError(
            f"Manual directory does not exist: {manual_dir}"
        )

    files = sorted(
        [
            p
            for p in manual_dir.rglob("*")
            if p.is_file() and p.suffix.lower() == ".pdf"
        ]
    )

    if not files:
        raise ValueError(
            f"No PDF manuals found inside {manual_dir}"
        )

    return files


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_into_evidence_blocks(text: str) -> list[str]:
    """
    Split a PDF page into useful evidence blocks.

    We retain paragraph boundaries where available and avoid
    producing extremely small fragments.
    """
    text = clean_text(text)

    if not text:
        return []

    paragraphs = re.split(r"\n\s*\n", text)

    blocks: list[str] = []

    for paragraph in paragraphs:
        paragraph = normalize(paragraph)

        if not paragraph:
            continue

        if len(paragraph) >= 80:
            blocks.append(paragraph)
        else:
            if blocks:
                blocks[-1] += " " + paragraph
            else:
                blocks.append(paragraph)

    if not blocks:
        blocks = [text]

    return blocks


def score_area(text: str, area: str) -> tuple[int, list[str]]:
    lower = text.lower()

    score = 0
    matched: list[str] = []

    for keyword in AREA_KEYWORDS.get(area, []):
        if keyword.lower() in lower:
            score += 1
            matched.append(keyword)

    return score, matched


def score_page(
    text: str,
    area: str,
    context: dict[str, str],
) -> tuple[int, list[str]]:
    lower = text.lower()

    score, matched = score_area(text, area)

    manufacturer = context["manufacturer"].lower()
    engine_model = context["engine_model"].lower()
    topic = context["topic"].lower()

    if manufacturer and manufacturer != "unknown":
        if manufacturer in lower:
            score += 5

    if engine_model and engine_model != "unknown":
        engine_normalized = engine_model.replace("-", " ")
        lower_normalized = lower.replace("-", " ")

        if engine_model in lower or engine_normalized in lower_normalized:
            score += 8

    topic_words = [
        word
        for word in re.findall(r"[a-zA-Z0-9]+", topic)
        if len(word) >= 4
    ]

    topic_matches = 0

    for word in topic_words:
        if word.lower() in lower:
            topic_matches += 1

    score += min(topic_matches * 2, 10)

    if any(
        marker in lower
        for marker in [
            "figure",
            "table",
            "procedure",
            "warning",
            "caution",
            "specification",
            "technical data",
        ]
    ):
        score += 2

    return score, matched


def import_fitz():
    try:
        import fitz
        return fitz
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF is required. Install it with: pip install pymupdf"
        ) from exc


def extract_page_records(
    pdf_path: Path,
    context: dict[str, str],
    max_pages: int = 0,
) -> list[dict[str, Any]]:
    fitz = import_fitz()

    records: list[dict[str, Any]] = []

    document = fitz.open(pdf_path)

    try:
        page_count = len(document)

        limit = page_count

        if max_pages > 0:
            limit = min(page_count, max_pages)

        for page_index in range(limit):
            page = document.load_page(page_index)

            raw_text = page.get_text("text")
            text = clean_text(raw_text)

            if not text:
                continue

            page_number = page_index + 1

            for area in ASSESSMENT_AREAS:
                page_score, matched = score_page(
                    text,
                    area,
                    context,
                )

                if page_score < 3:
                    continue

                blocks = split_into_evidence_blocks(text)

                for block_index, block in enumerate(blocks):
                    block_score, block_matches = score_area(
                        block,
                        area,
                    )

                    combined_score = page_score + min(
                        block_score * 2,
                        10,
                    )

                    if combined_score < 4:
                        continue

                    records.append(
                        {
                            "assessment_area": area,
                            "source_file": pdf_path.name,
                            "page": page_number,
                            "source_path": str(pdf_path),
                            "evidence_text": block,
                            "matched_keywords": sorted(
                                set(matched + block_matches)
                            ),
                            "score": combined_score,
                            "citation": (
                                f"[OEM: {pdf_path.name}, "
                                f"Page {page_number}]"
                            ),
                            "source_type": "OEM",
                        }
                    )

    finally:
        document.close()

    return records


def deduplicate_records(
    records: list[dict[str, Any]],
    max_per_area: int = 8,
) -> list[dict[str, Any]]:
    unique: dict[tuple[str, int, str, str], dict[str, Any]] = {}

    for record in records:
        key = (
            record["assessment_area"],
            int(record["page"]),
            record["source_file"],
            normalize(record["evidence_text"]).lower(),
        )

        existing = unique.get(key)

        if existing is None or record["score"] > existing["score"]:
            unique[key] = record

    by_area: dict[str, list[dict[str, Any]]] = {}

    for record in unique.values():
        area = record["assessment_area"]
        by_area.setdefault(area, []).append(record)

    final_records: list[dict[str, Any]] = []

    for area in ASSESSMENT_AREAS:
        area_records = by_area.get(area, [])

        area_records.sort(
            key=lambda item: (
                -int(item.get("score", 0)),
                item.get("source_file", ""),
                int(item.get("page", 0)),
            )
        )

        final_records.extend(area_records[:max_per_area])

    return final_records


def build_output(
    training: dict[str, Any],
    context: dict[str, str],
    pdf_files: list[Path],
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:

    area_counts = {
        area: 0
        for area in ASSESSMENT_AREAS
    }

    for item in evidence:
        area = item.get("assessment_area")

        if area in area_counts:
            area_counts[area] += 1

    return {
        "step": 33,
        "substep": "33C",
        "stage": "assessment_oem_evidence_grounding",
        "status": "SUCCESS" if evidence else "NO_EVIDENCE",
        "input": context,
        "source_manuals": [
            {
                "file": pdf.name,
                "path": str(pdf),
            }
            for pdf in pdf_files
        ],
        "manual_count": len(pdf_files),
        "evidence_count": len(evidence),
        "evidence_by_area": area_counts,
        "evidence": evidence,
        "evidence_policy": {
            "oem_priority": True,
            "oem_evidence_required": True,
            "web_is_not_oem": True,
            "unsupported_technical_claims_blocked": True,
            "invented_part_numbers_blocked": True,
            "invented_torque_values_blocked": True,
            "invented_pressures_blocked": True,
            "invented_temperatures_blocked": True,
            "invented_clearances_blocked": True,
            "invented_dimensions_blocked": True,
            "invented_procedures_blocked": True,
            "fake_oem_references_blocked": True,
            "source_page_required": True,
        },
        "assessment_areas": ASSESSMENT_AREAS,
        "grounding_instructions": [
            "Generate assessment questions only from supplied OEM evidence.",
            "Every technical question must have an OEM citation.",
            "Every answer key must be supported by the cited OEM evidence.",
            "Do not invent specifications, procedures, limits, tools, alarms, "
            "part numbers, torque values, pressures, temperatures, "
            "clearances, or dimensions.",
            "If evidence is insufficient, explicitly report insufficient evidence.",
        ],
        "training_workflow_reference": {
            "step": training.get("step"),
            "stage": training.get("stage"),
            "status": training.get("status"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build OEM-grounded evidence for MarineWise assessments."
    )

    parser.add_argument(
        "--training",
        required=True,
        help="Path to training_workflow.json",
    )

    parser.add_argument(
        "--manual-dir",
        required=True,
        help="Directory containing selected OEM PDF manuals",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Output JSON file",
    )

    parser.add_argument(
        "--max-pages",
        type=int,
        default=0,
        help="Optional page limit per PDF. 0 means all pages.",
    )

    args = parser.parse_args()

    training_path = Path(args.training)
    manual_dir = Path(args.manual_dir)
    output_path = Path(args.output)

    print("=" * 40)
    print("STEP 33C")
    print("=" * 40)

    print("Loading training workflow...")

    training = load_json(training_path)

    if training.get("step") != 30:
        raise ValueError(
            "training_workflow.json is not a valid STEP 30 workflow."
        )

    context = get_training_context(training)

    print(f"Manufacturer: {context['manufacturer']}")
    print(f"Engine: {context['engine_model']}")
    print(f"Topic: {context['topic']}")
    print(f"Vessel: {context['vessel']}")

    pdf_files = get_selected_pdf_files(manual_dir)

    print(f"OEM PDF manuals found: {len(pdf_files)}")
    print("Scanning OEM manuals for assessment evidence...")

    all_records: list[dict[str, Any]] = []

    for index, pdf_file in enumerate(pdf_files, start=1):
        print(
            f"[{index}/{len(pdf_files)}] "
            f"Scanning {pdf_file.name}"
        )

        records = extract_page_records(
            pdf_file,
            context,
            max_pages=args.max_pages,
        )

        all_records.extend(records)

    evidence = deduplicate_records(
        all_records,
        max_per_area=8,
    )

    result = build_output(
        training,
        context,
        pdf_files,
        evidence,
    )

    save_json(output_path, result)

    print()
    print("Assessment areas:")
    for area in ASSESSMENT_AREAS:
        count = result["evidence_by_area"].get(area, 0)
        print(f"  {area}: {count}")

    print()
    print(f"OEM evidence records: {len(evidence)}")
    print(f"Output: {output_path}")

    if not evidence:
        print("STEP 33C FILE 1 STATUS: RED")
        raise SystemExit(
            "No OEM evidence was found. "
            "Do not continue to assessment generation."
        )

    print("STEP 33C FILE 1 STATUS: GREEN")
    print("=" * 40)


if __name__ == "__main__":
    main()
