from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


TRAINING_SECTIONS = [
    "TRAINING OBJECTIVE",
    "ENGINE INTRODUCTION",
    "SYSTEM OVERVIEW",
    "COMPONENT IDENTIFICATION",
    "TOOLS REQUIRED",
    "SAFETY PRECAUTIONS",
    "REMOVAL PROCEDURE",
    "INSPECTION",
    "INSTALLATION",
    "TORQUE AND SPECIFICATIONS",
    "COMMON FAULTS",
    "TROUBLESHOOTING",
    "PRACTICAL EXERCISE",
    "KNOWLEDGE CHECK",
    "FINAL ASSESSMENT",
    "OEM REFERENCES",
    "EVIDENCE STATUS",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="MarineWise AI Training Intelligence Workflow"
    )

    parser.add_argument(
        "--manufacturer",
        required=True,
    )

    parser.add_argument(
        "--engine-model",
        required=True,
    )

    parser.add_argument(
        "--topic",
        required=True,
    )

    parser.add_argument(
        "--technician-level",
        default="Basic",
    )

    parser.add_argument(
        "--duration",
        default="4 Days",
    )

    parser.add_argument(
        "--vessel",
        default="",
    )

    parser.add_argument(
        "--manuals",
        default="manual_catalog.json",
    )

    parser.add_argument(
        "--output",
        default="training_workflow.json",
    )

    return parser.parse_args()


def clean(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


def load_catalog(path: str) -> Any:
    file = Path(path)

    if not file.exists():
        raise FileNotFoundError(
            f"Manual catalog not found: {path}"
        )

    return json.loads(
        file.read_text(
            encoding="utf-8"
        )
    )


def get_records(catalog: Any) -> list[dict[str, Any]]:
    if isinstance(catalog, list):
        return [
            item
            for item in catalog
            if isinstance(item, dict)
        ]

    if isinstance(catalog, dict):
        for key in (
            "manuals",
            "records",
            "catalog",
            "items",
        ):
            value = catalog.get(key)

            if isinstance(value, list):
                return [
                    item
                    for item in value
                    if isinstance(item, dict)
                ]

    return []


def value_from_record(
    record: dict[str, Any],
    names: list[str],
) -> str:

    for name in names:
        value = record.get(name)

        if value is not None:
            text = clean(value)

            if text:
                return text

    return ""


def searchable_record(
    record: dict[str, Any],
) -> str:

    values = []

    for value in record.values():
        if isinstance(value, (str, int, float)):
            values.append(str(value))

    return " ".join(values).lower()


def score_manual(
    record: dict[str, Any],
    manufacturer: str,
    engine_model: str,
    topic: str,
    vessel: str,
) -> int:

    text = searchable_record(record)

    score = 0

    manufacturer_l = manufacturer.lower()
    engine_l = engine_model.lower()
    topic_l = topic.lower()
    vessel_l = vessel.lower()

    if manufacturer_l and manufacturer_l in text:
        score += 30

    if engine_l and engine_l in text:
        score += 45

    topic_terms = [
        term
        for term in topic_l.replace(
            "-", " "
        ).split()
        if len(term) >= 3
    ]

    for term in topic_terms:
        if term in text:
            score += 8

    if vessel_l and vessel_l in text:
        score += 20

    for keyword, points in [
        ("maintenance", 8),
        ("service", 8),
        ("workshop", 8),
        ("manual", 5),
        ("technical", 5),
        ("procedure", 10),
        ("operation", 5),
        ("repair", 8),
    ]:
        if keyword in text:
            score += points

    return score


def select_manuals(
    records: list[dict[str, Any]],
    manufacturer: str,
    engine_model: str,
    topic: str,
    vessel: str,
) -> list[dict[str, Any]]:

    scored = []

    for record in records:
        score = score_manual(
            record,
            manufacturer,
            engine_model,
            topic,
            vessel,
        )

        source_file = value_from_record(
            record,
            [
                "filename",
                "file_name",
                "source_file",
                "name",
            ],
        )

        scored.append(
            {
                "score": score,
                "source_file": source_file,
                "record": record,
            }
        )

    scored.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    selected = []

    for item in scored[:10]:
        selected.append(
            {
                "score": item["score"],
                "source_file": item["source_file"],
                "metadata": item["record"],
            }
        )

    return selected


def build_training_query(
    manufacturer: str,
    engine_model: str,
    topic: str,
    technician_level: str,
    duration: str,
    vessel: str,
) -> str:

    parts = [
        manufacturer,
        engine_model,
        topic,
        "marine engine",
        "OEM manual",
        "maintenance",
        "training",
        "procedure",
        "tools",
        "safety",
        "inspection",
        "installation",
        technician_level,
        duration,
    ]

    if vessel:
        parts.insert(
            0,
            vessel,
        )

    return " ".join(
        part
        for part in parts
        if part
    )


def build_curriculum(
    manufacturer: str,
    engine_model: str,
    topic: str,
    technician_level: str,
    duration: str,
) -> list[dict[str, Any]]:

    curriculum = []

    objectives = [
        (
            "TRAINING OBJECTIVE",
            "Define the learning outcomes for the requested "
            "marine-engine training topic."
        ),
        (
            "ENGINE INTRODUCTION",
            "Introduce the relevant engine, application and "
            "basic technical background supported by OEM evidence."
        ),
        (
            "SYSTEM OVERVIEW",
            "Explain the relevant engine system and its operating "
            "principle using documented evidence."
        ),
        (
            "COMPONENT IDENTIFICATION",
            "Identify relevant components, locations and functions "
            "when supported by the OEM documentation."
        ),
        (
            "TOOLS REQUIRED",
            "Identify tools and special tools documented by the OEM."
        ),
        (
            "SAFETY PRECAUTIONS",
            "Identify applicable safety precautions before practical work."
        ),
        (
            "REMOVAL PROCEDURE",
            "Document the OEM-supported removal procedure."
        ),
        (
            "INSPECTION",
            "Document inspection requirements and acceptance criteria "
            "supported by the OEM."
        ),
        (
            "INSTALLATION",
            "Document the OEM-supported installation procedure."
        ),
        (
            "TORQUE AND SPECIFICATIONS",
            "Provide only documented OEM torque values and technical "
            "specifications."
        ),
        (
            "COMMON FAULTS",
            "Identify documented faults and symptoms related to the topic."
        ),
        (
            "TROUBLESHOOTING",
            "Provide evidence-based troubleshooting for relevant faults."
        ),
        (
            "PRACTICAL EXERCISE",
            "Create an evidence-based technician practical exercise."
        ),
        (
            "KNOWLEDGE CHECK",
            "Create knowledge-check questions based on the supplied evidence."
        ),
        (
            "FINAL ASSESSMENT",
            "Define an assessment covering the training objectives."
        ),
        (
            "OEM REFERENCES",
            "List the OEM manuals and page references supporting the training."
        ),
        (
            "EVIDENCE STATUS",
            "Identify which training information is supported by OEM evidence "
            "and where additional OEM confirmation is required."
        ),
    ]

    for order, (section, purpose) in enumerate(
        objectives,
        start=1,
    ):
        curriculum.append(
            {
                "order": order,
                "section": section,
                "purpose": purpose,
                "evidence_required": True,
            }
        )

    return curriculum


def main() -> None:

    args = parse_args()

    catalog = load_catalog(
        args.manuals
    )

    records = get_records(
        catalog
    )

    if not records:
        raise ValueError(
            "No manual catalog records found."
        )

    selected = select_manuals(
        records,
        args.manufacturer,
        args.engine_model,
        args.topic,
        args.vessel,
    )

    if not selected:
        raise ValueError(
            "No relevant manuals were selected."
        )

    query = build_training_query(
        args.manufacturer,
        args.engine_model,
        args.topic,
        args.technician_level,
        args.duration,
        args.vessel,
    )

    curriculum = build_curriculum(
        args.manufacturer,
        args.engine_model,
        args.topic,
        args.technician_level,
        args.duration,
    )

    output = {
        "step": 30,
        "stage": "training_intelligence_curriculum_planner",
        "status": "READY_FOR_GROQ",

        "input": {
            "manufacturer": args.manufacturer,
            "engine_model": args.engine_model,
            "topic": args.topic,
            "technician_level": args.technician_level,
            "duration": args.duration,
            "vessel": args.vessel,
        },

        "constructed_query": query,

        "manual_selection": {
            "catalog_records": len(records),
            "selected_count": len(selected),
            "selected_manuals": selected,
        },

        "curriculum": curriculum,

        "evidence_policy": {
            "oem_priority": True,
            "oem_evidence_required": True,
            "web_is_not_oem": True,
            "unsupported_specifications_blocked": True,
            "unsupported_procedures_blocked": True,
            "fake_references_blocked": True,
        },

        "next_stage": "GROQ_TRAINING_CONTENT",
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

    print("=" * 70)
    print("STEP 30 VERIFICATION COMPLETE")
    print("=" * 70)

    print(
        f"Catalog records    : {len(records)}"
    )

    print(
        f"Selected manuals   : {len(selected)}"
    )

    print(
        f"Curriculum sections: {len(curriculum)}"
    )

    print(
        f"Training topic     : {args.topic}"
    )

    print(
        f"Technician level   : {args.technician_level}"
    )

    print(
        f"Duration           : {args.duration}"
    )

    print()
    print("OEM priority       : TRUE")
    print("Evidence required  : TRUE")
    print("Curriculum created : TRUE")
    print("Ready for Groq     : TRUE")
    print()
    print("STEP 30: SUCCESS")
    print("GREEN")


if __name__ == "__main__":
    main()
