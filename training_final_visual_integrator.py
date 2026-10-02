from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


AI_LABEL = "AI Training Illustration — Not an OEM Figure"

VISUAL_SECTIONS = [
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
]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False,
        )


def get_section_result(
    validated_data: dict[str, Any],
    section: str,
) -> dict[str, Any] | None:

    for item in validated_data.get("section_results", []):
        if item.get("section") == section:
            return item

    return None


def get_ai_request(
    validated_data: dict[str, Any],
    section: str,
) -> dict[str, Any] | None:

    for item in validated_data.get("ai_visual_requests", []):
        if item.get("section") == section:
            return item

    return None


def get_ai_generated(
    ai_manifest: dict[str, Any],
    section: str,
) -> dict[str, Any] | None:

    for item in ai_manifest.get("generated", []):
        if item.get("section") == section:
            return item

    return None


def resolve_path(
    value: str | None,
    base_dir: Path,
) -> Path | None:

    if not value:
        return None

    path = Path(value)

    if path.exists():
        return path

    candidate = base_dir / path

    if candidate.exists():
        return candidate

    return None


def copy_visual(
    source: Path,
    destination: Path,
) -> None:

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(
        source,
        destination,
    )


def integrate_visuals(
    validated_data: dict[str, Any],
    ai_manifest: dict[str, Any],
    output_dir: Path,
) -> list[dict[str, Any]]:

    integrated_dir = output_dir / "visuals"
    integrated_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    results: list[dict[str, Any]] = []

    for section in VISUAL_SECTIONS:

        validated = get_section_result(
            validated_data,
            section,
        )

        if not validated:
            results.append(
                {
                    "section": section,
                    "status": "NO_VISUAL_RESULT",
                    "visual_source": None,
                }
            )
            continue

        visual_source = validated.get(
            "visual_source"
        )

        status = validated.get(
            "status"
        )

        # ---------------------------------------------------------
        # OEM VISUAL HAS PRIORITY
        # ---------------------------------------------------------

        if visual_source == "OEM":

            candidates = validated.get(
                "accepted_candidates",
                [],
            )

            if not candidates:
                candidates = validated.get(
                    "candidates",
                    [],
                )

            selected = None

            for candidate in candidates:
                candidate_path = resolve_path(
                    candidate.get("rendered_image"),
                    Path("."),
                )

                if candidate_path:
                    selected = (
                        candidate,
                        candidate_path,
                    )
                    break

            if selected:

                candidate, source_path = selected

                destination = (
                    integrated_dir
                    / f"{section.lower().replace(' ', '_')}_oem.png"
                )

                copy_visual(
                    source_path,
                    destination,
                )

                results.append(
                    {
                        "section": section,
                        "status": "INTEGRATED",
                        "visual_source": "OEM",
                        "file": str(destination),
                        "source_file": candidate.get(
                            "source_file"
                        ),
                        "page": candidate.get(
                            "page"
                        ),
                        "citation": candidate.get(
                            "citation"
                        ),
                        "ai_label_required": False,
                    }
                )

                continue

        # ---------------------------------------------------------
        # AI FALLBACK
        # ONLY USED WHEN OEM VISUAL IS UNAVAILABLE
        # ---------------------------------------------------------

        if visual_source == "AI_FALLBACK":

            ai_request = get_ai_request(
                validated_data,
                section,
            )

            ai_generated = get_ai_generated(
                ai_manifest,
                section,
            )

            if ai_generated:

                source_path = resolve_path(
                    ai_generated.get("file"),
                    Path("."),
                )

                if source_path:

                    destination = (
                        integrated_dir
                        / f"{section.lower().replace(' ', '_')}_ai.png"
                    )

                    copy_visual(
                        source_path,
                        destination,
                    )

                    results.append(
                        {
                            "section": section,
                            "status": "INTEGRATED",
                            "visual_source": "AI_FALLBACK",
                            "file": str(destination),
                            "source_file": None,
                            "page": None,
                            "citation": None,
                            "ai_label_required": True,
                            "ai_visual_label": AI_LABEL,
                            "prompt": (
                                ai_generated.get("prompt")
                                or (
                                    ai_request or {}
                                ).get("prompt")
                            ),
                        }
                    )

                    continue

            results.append(
                {
                    "section": section,
                    "status": "AI_VISUAL_NOT_AVAILABLE",
                    "visual_source": "AI_FALLBACK",
                    "file": None,
                    "source_file": None,
                    "page": None,
                    "citation": None,
                    "ai_label_required": True,
                    "ai_visual_label": AI_LABEL,
                }
            )

            continue

        # ---------------------------------------------------------
        # NO USABLE VISUAL
        # ---------------------------------------------------------

        results.append(
            {
                "section": section,
                "status": "NO_USABLE_VISUAL",
                "visual_source": visual_source,
                "file": None,
                "source_file": None,
                "page": None,
                "citation": None,
                "ai_label_required": False,
            }
        )

    return results


def validate_visual_policy(
    validated_data: dict[str, Any],
    ai_manifest: dict[str, Any],
) -> None:

    if validated_data.get("step") != 32:
        raise ValueError(
            "Invalid STEP 32 input."
        )

    if validated_data.get("substep") != "32C":
        raise ValueError(
            "Invalid STEP 32C input."
        )

    if validated_data.get("status") != "SUCCESS":
        raise ValueError(
            "STEP 32C input is not SUCCESS."
        )

    label = validated_data.get(
        "ai_visual_label"
    )

    if label != AI_LABEL:
        raise ValueError(
            "STEP 32C AI visual label is incorrect."
        )

    ai_label = ai_manifest.get(
        "ai_visual_label"
    )

    if ai_label and ai_label != AI_LABEL:
        raise ValueError(
            "STEP 32D AI visual label is incorrect."
        )


def build_manifest(
    training_answer: dict[str, Any],
    validated_data: dict[str, Any],
    ai_manifest: dict[str, Any],
    visual_results: list[dict[str, Any]],
) -> dict[str, Any]:

    oem_count = sum(
        1
        for item in visual_results
        if item.get("visual_source") == "OEM"
        and item.get("status") == "INTEGRATED"
    )

    ai_count = sum(
        1
        for item in visual_results
        if item.get("visual_source") == "AI_FALLBACK"
        and item.get("status") == "INTEGRATED"
    )

    unavailable_count = sum(
        1
        for item in visual_results
        if item.get("status") != "INTEGRATED"
    )

    return {
        "step": 32,
        "substep": "32E",
        "stage": "final_visual_package_integrator",
        "status": "SUCCESS",
        "input": {
            "manufacturer": (
                training_answer.get("input", {})
                .get("manufacturer")
            ),
            "engine_model": (
                training_answer.get("input", {})
                .get("engine_model")
            ),
            "topic": (
                training_answer.get("input", {})
                .get("topic")
            ),
            "vessel": (
                training_answer.get("input", {})
                .get("vessel")
            ),
        },
        "visual_sections": len(VISUAL_SECTIONS),
        "oem_visuals_integrated": oem_count,
        "ai_visuals_integrated": ai_count,
        "visuals_unavailable": unavailable_count,
        "ai_visual_label": AI_LABEL,
        "visual_policy": {
            "oem_visual_first": True,
            "ai_visual_only_when_oem_visual_is_unavailable": True,
            "ai_visual_is_generic_training_illustration": True,
            "ai_visual_not_oem_figure": True,
            "technical_specs_must_come_from_oem": True,
            "fake_oem_figures_blocked": True,
            "oem_source_traceability_required": True,
        },
        "visuals": visual_results,
    }


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "MarineWise STEP 32E final visual "
            "package integrator."
        )
    )

    parser.add_argument(
        "--training",
        required=True,
        help="Path to training_answer.json",
    )

    parser.add_argument(
        "--validated",
        required=True,
        help="Path to validated_visual_requests.json",
    )

    parser.add_argument(
        "--ai-manifest",
        required=True,
        help="Path to ai_training_visual_manifest.json",
    )

    parser.add_argument(
        "--output-dir",
        default="final_training_package",
        help="Final integration output directory.",
    )

    parser.add_argument(
        "--manifest",
        default="final_visual_package_manifest.json",
        help="Output STEP 32E manifest.",
    )

    args = parser.parse_args()

    training_path = Path(args.training)
    validated_path = Path(args.validated)
    ai_manifest_path = Path(args.ai_manifest)
    output_dir = Path(args.output_dir)
    manifest_path = Path(args.manifest)

    training_answer = load_json(
        training_path
    )

    validated_data = load_json(
        validated_path
    )

    ai_manifest = load_json(
        ai_manifest_path
    )

    validate_visual_policy(
        validated_data,
        ai_manifest,
    )

    visual_results = integrate_visuals(
        validated_data=validated_data,
        ai_manifest=ai_manifest,
        output_dir=output_dir,
    )

    final_manifest = build_manifest(
        training_answer=training_answer,
        validated_data=validated_data,
        ai_manifest=ai_manifest,
        visual_results=visual_results,
    )

    save_json(
        manifest_path,
        final_manifest,
    )

    print("")
    print("==============================================")
    print("MARINEWISE STEP 32E")
    print("FINAL VISUAL PACKAGE INTEGRATOR")
    print("==============================================")
    print(
        "OEM visuals integrated:",
        final_manifest[
            "oem_visuals_integrated"
        ],
    )
    print(
        "AI visuals integrated:",
        final_manifest[
            "ai_visuals_integrated"
        ],
    )
    print(
        "Visuals unavailable:",
        final_manifest[
            "visuals_unavailable"
        ],
    )
    print(
        "Manifest:",
        manifest_path,
    )
    print("==============================================")
    print("STEP 32E FILE 1 STATUS: GREEN")
    print("==============================================")


if __name__ == "__main__":
    main()
