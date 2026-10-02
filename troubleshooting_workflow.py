from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_MANUFACTURER = "MAN"
DEFAULT_ENGINE_MODEL = "16V175D-MM"
DEFAULT_SERIAL_NUMBER = ""
DEFAULT_VESSEL = "QL-40"
DEFAULT_OPERATING_HOURS = "5000"
DEFAULT_SYSTEM = "Main Engine"
DEFAULT_FAULT = "High exhaust temperature alarm"


def load_json(path: str | Path) -> Any:
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"Required file not found: {file_path}"
        )

    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def extract_list(
    data: Any,
    keys: list[str],
) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        return []

    for key in keys:
        value = data.get(key)

        if isinstance(value, list):
            return value

    return []


def clean_value(value: str | None) -> str:
    if value is None:
        return ""

    return str(value).strip()


def build_query(
    manufacturer: str,
    engine_model: str,
    serial_number: str,
    vessel: str,
    operating_hours: str,
    system: str,
    fault: str,
) -> str:

    parts = [
        vessel,
        manufacturer,
        engine_model,
    ]

    if serial_number:
        parts.append(f"Serial {serial_number}")

    if operating_hours:
        parts.append(f"{operating_hours} operating hours")

    if system:
        parts.append(system)

    if fault:
        parts.append(fault)

    parts.extend(
        [
            "marine engine",
            "troubleshooting",
            "alarm",
            "maintenance",
            "OEM manual",
        ]
    )

    return " ".join(
        part for part in parts if clean_value(part)
    )


def build_troubleshooting_workflow(
    manufacturer: str,
    engine_model: str,
    serial_number: str,
    vessel: str,
    operating_hours: str,
    system: str,
    fault: str,
    final_evidence_file: str = "final_evidence.json",
) -> dict[str, Any]:

    manufacturer = clean_value(manufacturer)
    engine_model = clean_value(engine_model)
    serial_number = clean_value(serial_number)
    vessel = clean_value(vessel)
    operating_hours = clean_value(operating_hours)
    system = clean_value(system)
    fault = clean_value(fault)

    if not manufacturer:
        raise ValueError(
            "Manufacturer is required."
        )

    if not engine_model:
        raise ValueError(
            "Engine model is required."
        )

    if not vessel:
        raise ValueError(
            "Vessel is required."
        )

    if not fault:
        raise ValueError(
            "Fault, alarm or symptom is required."
        )

    query = build_query(
        manufacturer=manufacturer,
        engine_model=engine_model,
        serial_number=serial_number,
        vessel=vessel,
        operating_hours=operating_hours,
        system=system,
        fault=fault,
    )

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
            "No OEM evidence is available "
            "for troubleshooting."
        )

    if not combined_evidence:
        raise ValueError(
            "No combined evidence is available."
        )

    workflow = {
        "step": 29,
        "stage": "marine_troubleshooting_workflow",
        "status": "READY_FOR_GROQ",

        "input": {
            "manufacturer": manufacturer,
            "engine_model": engine_model,
            "serial_number": serial_number,
            "vessel": vessel,
            "operating_hours": operating_hours,
            "system": system,
            "fault": fault,
        },

        "constructed_query": query,

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
            "Receive structured marine engine information",
            "Construct technical troubleshooting query",
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
        description=(
            "MarineWise AI structured "
            "troubleshooting workflow"
        )
    )

    parser.add_argument(
        "--manufacturer",
        default=DEFAULT_MANUFACTURER,
    )

    parser.add_argument(
        "--engine-model",
        default=DEFAULT_ENGINE_MODEL,
    )

    parser.add_argument(
        "--serial-number",
        default=DEFAULT_SERIAL_NUMBER,
    )

    parser.add_argument(
        "--vessel",
        default=DEFAULT_VESSEL,
    )

    parser.add_argument(
        "--operating-hours",
        default=DEFAULT_OPERATING_HOURS,
    )

    parser.add_argument(
        "--system",
        default=DEFAULT_SYSTEM,
    )

    parser.add_argument(
        "--fault",
        default=DEFAULT_FAULT,
    )

    parser.add_argument(
        "--evidence",
        default="final_evidence.json",
    )

    parser.add_argument(
        "--output",
        default="troubleshooting_workflow.json",
    )

    args = parser.parse_args()

    result = build_troubleshooting_workflow(
        manufacturer=args.manufacturer,
        engine_model=args.engine_model,
        serial_number=args.serial_number,
        vessel=args.vessel,
        operating_hours=args.operating_hours,
        system=args.system,
        fault=args.fault,
        final_evidence_file=args.evidence,
    )

    output_path = Path(args.output)

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
    print("STEP 29B VERIFICATION")
    print("=" * 70)
    print(
        f"Manufacturer      : "
        f"{result['input']['manufacturer']}"
    )
    print(
        f"Engine model      : "
        f"{result['input']['engine_model']}"
    )
    print(
        f"Serial number     : "
        f"{result['input']['serial_number'] or 'Not provided'}"
    )
    print(
        f"Vessel            : "
        f"{result['input']['vessel']}"
    )
    print(
        f"Operating hours   : "
        f"{result['input']['operating_hours'] or 'Not provided'}"
    )
    print(
        f"System            : "
        f"{result['input']['system']}"
    )
    print(
        f"Fault             : "
        f"{result['input']['fault']}"
    )
    print()
    print(
        f"Constructed query : "
        f"{result['constructed_query']}"
    )
    print()
    print(
        f"OEM evidence      : "
        f"{result['evidence']['oem_count']}"
    )
    print(
        f"WEB evidence      : "
        f"{result['evidence']['web_count']}"
    )
    print(
        f"Combined evidence : "
        f"{result['evidence']['combined_count']}"
    )
    print()
    print(
        f"Status            : "
        f"{result['status']}"
    )
    print()
    print("STEP 29B: SUCCESS")
    print("GREEN")


if __name__ == "__main__":
    main()
