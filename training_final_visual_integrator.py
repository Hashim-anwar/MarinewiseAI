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


# ============================================================
# BASIC HELPERS
# ============================================================

def load_json(path: str | Path) -> dict[str, Any]:
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Required JSON file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(
            f"{path} must contain a JSON object."
        )

    return data


def save_json(path: str | Path, data: dict[str, Any]) -> None:
    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with path.open(
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )


# ============================================================
# NORMALIZE COLLECTIONS
# ============================================================

def normalize_items(value: Any) -> list[dict[str, Any]]:
    """
    Convert supported JSON collection formats into a list
    of dictionaries.

    Supported:

    1. List of dictionaries

       [
         {"section": "..."},
         {"section": "..."}
       ]

    2. Dictionary keyed by section

       {
         "ENGINE INTRODUCTION": {
             "section": "ENGINE INTRODUCTION"
         }
       }

    3. Dictionary containing a list

       {
         "visuals": [
             {"section": "..."}
         ]
       }

    4. Dictionary containing section records directly

       {
         "ENGINE INTRODUCTION": {...},
         "SYSTEM OVERVIEW": {...}
       }
    """

    if value is None:
        return []

    if isinstance(value, list):
        return [
            item
            for item in value
            if isinstance(item, dict)
        ]

    if isinstance(value, dict):

        # A dictionary containing a list
        for key in (
            "visuals",
            "visual_results",
            "results",
            "sections",
            "items",
            "requests",
            "ai_visual_requests",
            "accepted_candidates",
            "candidates",
        ):
            nested = value.get(key)

            if isinstance(nested, list):
                return [
                    item
                    for item in nested
                    if isinstance(item, dict)
                ]

        # Dictionary keyed by section
        result = []

        for key, item in value.items():

            if isinstance(item, dict):
                record = dict(item)

                if not record.get("section"):
                    record["section"] = key

                result.append(record)

        return result

    return []


# ============================================================
# SECTION LOOKUP
# ============================================================

def get_section_result(
    data: dict[str, Any],
    section: str
) -> dict[str, Any] | None:
    """
    Safely find one section regardless of whether the
    source JSON stores sections as a list or dictionary.
    """

    possible_collections = [
        data.get("visuals"),
        data.get("visual_results"),
        data.get("results"),
        data.get("sections"),
        data.get("items"),
        data.get("requests"),
        data.get("ai_visual_requests"),
    ]

    for collection in possible_collections:

        items = normalize_items(collection)

        for item in items:

            item_section = item.get("section")

            if item_section == section:
                return item

    # Some files may store the sections directly at root level.
    direct = data.get(section)

    if isinstance(direct, dict):
        result = dict(direct)

        if not result.get("section"):
            result["section"] = section

        return result

    return None


# ============================================================
# AI REQUEST LOOKUP
# ============================================================

def get_ai_request(
    data: dict[str, Any],
    section: str
) -> dict[str, Any] | None:

    requests = data.get("ai_visual_requests")

    for item in normalize_items(requests):

        if item.get("section") == section:
            return item

    return None


# ============================================================
# AI GENERATED VISUAL LOOKUP
# ============================================================

def get_ai_generated(
    data: dict[str, Any],
    section: str
) -> dict[str, Any] | None:

    possible_collections = [
        data.get("generated_visuals"),
        data.get("ai_visuals"),
        data.get("results"),
        data.get("visuals"),
    ]

    for collection in possible_collections:

        for item in normalize_items(collection):

            if item.get("section") == section:
                return item

    # Some generators may store generated items directly
    # inside ai_visual_requests.
    for item in normalize_items(
        data.get("ai_visual_requests")
    ):

        if item.get("section") == section:
            return item

    return None


# ============================================================
# PATH RESOLUTION
# ============================================================

def resolve_path(
    value: Any,
    base_dir: Path
) -> Path | None:

    if not value:
        return None

    try:
        candidate = Path(str(value))
    except Exception:
        return None

    # Absolute path
    if candidate.is_absolute() and candidate.exists():
        return candidate

    # Relative to current working directory
    if candidate.exists():
        return candidate

    # Relative to supplied base directory
    candidate2 = base_dir / candidate

    if candidate2.exists():
        return candidate2

    return None


# ============================================================
# COPY VISUAL
# ============================================================

def copy_visual(
    source: Path,
    destination: Path
) -> bool:

    if not source.exists():
        return False

    destination.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    shutil.copy2(
        source,
        destination
    )

    return destination.exists()


# ============================================================
# FIND RENDERED IMAGE
# ============================================================

def find_rendered_image(
    record: dict[str, Any],
    base_dir: Path
) -> Path | None:

    possible_keys = [
        "rendered_image",
        "image",
        "image_path",
        "visual_path",
        "file",
        "path",
        "output_file",
    ]

    for key in possible_keys:

        value = record.get(key)

        path = resolve_path(
            value,
            base_dir
        )

        if path:
            return path

    return None


# ============================================================
# INTEGRATE VISUALS
# ============================================================

def integrate_visuals(
    training: dict[str, Any],
    validated: dict[str, Any],
    ai_manifest: dict[str, Any],
    output_dir: Path
) -> list[dict[str, Any]]:

    visuals_dir = (
        output_dir / "visuals"
    )

    visuals_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    results: list[dict[str, Any]] = []

    # Base directories used for relative image paths
    validated_base = Path.cwd()
    ai_base = Path.cwd()

    for section in VISUAL_SECTIONS:

        result: dict[str, Any] = {
            "section": section,
            "visual_source": "NONE",
            "status": "NO_USABLE_VISUAL",
            "image": None,
            "source_file": None,
            "page": None,
            "citation": None,
            "ai_label": None,
        }

        validated_record = get_section_result(
            validated,
            section
        )

        # ----------------------------------------------------
        # OEM VISUAL
        # ----------------------------------------------------

        if validated_record:

            visual_source = str(
                validated_record.get(
                    "visual_source",
                    ""
                )
            ).upper()

            if visual_source == "OEM":

                # First try direct rendered image
                source = find_rendered_image(
                    validated_record,
                    validated_base
                )

                # Then inspect accepted candidates
                if source is None:

                    candidates = validated_record.get(
                        "accepted_candidates"
                    )

                    if not isinstance(
                        candidates,
                        list
                    ):
                        candidates = validated_record.get(
                            "candidates"
                        )

                    for candidate in normalize_items(
                        candidates
                    ):

                        source = find_rendered_image(
                            candidate,
                            validated_base
                        )

                        if source:
                            break

                if source:

                    destination = (
                        visuals_dir
                        / f"{section.lower().replace(' ', '_')}_oem.png"
                    )

                    copied = copy_visual(
                        source,
                        destination
                    )

                    if copied:

                        source_file = (
                            validated_record.get(
                                "source_file"
                            )
                        )

                        page = (
                            validated_record.get(
                                "page"
                            )
                        )

                        citation = (
                            validated_record.get(
                                "citation"
                            )
                        )

                        if not citation and source_file:
                            if page is not None:
                                citation = (
                                    f"[OEM: "
                                    f"{source_file}, "
                                    f"Page {page}]"
                                )
                            else:
                                citation = (
                                    f"[OEM: {source_file}]"
                                )

                        result.update(
                            {
                                "visual_source": "OEM",
                                "status": "OEM_INTEGRATED",
                                "image": str(destination),
                                "source_file": source_file,
                                "page": page,
                                "citation": citation,
                            }
                        )

                        results.append(result)
                        continue

        # ----------------------------------------------------
        # AI FALLBACK
        # ----------------------------------------------------

        ai_request = get_ai_request(
            validated,
            section
        )

        ai_generated = get_ai_generated(
            ai_manifest,
            section
        )

        if ai_request:

            request_source = str(
                ai_request.get(
                    "visual_source",
                    ""
                )
            ).upper()

            if request_source == "AI_FALLBACK":

                if ai_generated:

                    source = find_rendered_image(
                        ai_generated,
                        ai_base
                    )

                    if source:

                        destination = (
                            visuals_dir
                            / f"{section.lower().replace(' ', '_')}_ai.png"
                        )

                        copied = copy_visual(
                            source,
                            destination
                        )

                        if copied:

                            result.update(
                                {
                                    "visual_source": "AI_FALLBACK",
                                    "status": "AI_INTEGRATED",
                                    "image": str(destination),
                                    "source_file": None,
                                    "page": None,
                                    "citation": None,
                                    "ai_label": AI_LABEL,
                                }
                            )

                            results.append(result)
                            continue

        # ----------------------------------------------------
        # NO VISUAL
        # ----------------------------------------------------

        results.append(result)

    return results


# ============================================================
# POLICY VALIDATION
# ============================================================

def validate_visual_policy(
    validated: dict[str, Any],
    ai_manifest: dict[str, Any]
) -> None:

    if validated.get("step") != 32:
        raise ValueError(
            "Validated visual manifest is not STEP 32."
        )

    if validated.get("substep") != "32C":
        raise ValueError(
            "Validated visual manifest is not STEP 32C."
        )

    if validated.get("status") != "SUCCESS":
        raise ValueError(
            "Validated visual manifest status is not SUCCESS."
        )

    label = (
        validated.get("ai_visual_label")
        or ai_manifest.get("ai_visual_label")
    )

    if label != AI_LABEL:
        raise ValueError(
            "AI visual label does not match the required label."
        )


# ============================================================
# BUILD FINAL MANIFEST
# ============================================================

def build_manifest(
    training: dict[str, Any],
    visual_results: list[dict[str, Any]]
) -> dict[str, Any]:

    oem_count = sum(
        1
        for item in visual_results
        if item.get("visual_source") == "OEM"
    )

    ai_count = sum(
        1
        for item in visual_results
        if item.get("visual_source") == "AI_FALLBACK"
    )

    unavailable_count = sum(
        1
        for item in visual_results
        if item.get("visual_source") == "NONE"
    )

    input_data = training.get(
        "input",
        {}
    )

    if not isinstance(input_data, dict):
        input_data = {}

    return {
        "step": 32,
        "substep": "32E",
        "stage": "final_visual_package_integrator",
        "status": "SUCCESS",
        "input": {
            "manufacturer": input_data.get(
                "manufacturer"
            ),
            "engine_model": input_data.get(
                "engine_model"
            ),
            "topic": input_data.get(
                "topic"
            ),
            "vessel": input_data.get(
                "vessel"
            ),
        },
        "visual_sections": len(
            VISUAL_SECTIONS
        ),
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
            "validated_oem_visuals_are_never_replaced_by_ai": True,
        },
        "visuals": visual_results,
    }


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "MarineWise STEP 32E "
            "Final Visual Package Integrator"
        )
    )

    parser.add_argument(
        "--training",
        required=True
    )

    parser.add_argument(
        "--validated",
        required=True
    )

    parser.add_argument(
        "--ai-manifest",
        required=True
    )

    parser.add_argument(
        "--output-dir",
        default="final_training_package"
    )

    parser.add_argument(
        "--manifest",
        default="final_visual_package_manifest.json"
    )

    args = parser.parse_args()

    training = load_json(
        args.training
    )

    validated = load_json(
        args.validated
    )

    ai_manifest = load_json(
        args.ai_manifest
    )

    # Validate source policies first.
    validate_visual_policy(
        validated,
        ai_manifest
    )

    output_dir = Path(
        args.output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    visual_results = integrate_visuals(
        training=training,
        validated=validated,
        ai_manifest=ai_manifest,
        output_dir=output_dir
    )

    final_manifest = build_manifest(
        training=training,
        visual_results=visual_results
    )

    save_json(
        args.manifest,
        final_manifest
    )

    print(
        "STEP 32E FILE 1 STATUS: GREEN"
    )

    print(
        f"Visual sections: {len(VISUAL_SECTIONS)}"
    )

    print(
        "OEM visuals integrated:",
        final_manifest[
            "oem_visuals_integrated"
        ]
    )

    print(
        "AI visuals integrated:",
        final_manifest[
            "ai_visuals_integrated"
        ]
    )

    print(
        "Visuals unavailable:",
        final_manifest[
            "visuals_unavailable"
        ]
    )

    print(
        f"Manifest: {args.manifest}"
    )


if __name__ == "__main__":
    main()
