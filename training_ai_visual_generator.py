from __future__ import annotations

import argparse
import base64
import json
import os
import re
from pathlib import Path
from typing import Any

import requests


AI_LABEL = "AI Training Illustration — Not an OEM Figure"


SECTION_DESCRIPTIONS = {
    "ENGINE INTRODUCTION": (
        "a generic educational overview of a marine diesel engine, "
        "showing major engine systems and their functional relationships"
    ),
    "SYSTEM OVERVIEW": (
        "a generic educational fuel-system flow concept for a marine "
        "diesel engine, showing fuel movement between major system stages"
    ),
    "COMPONENT IDENTIFICATION": (
        "a generic educational illustration of typical fuel-injection "
        "system components such as an injector, fuel line, sealing element "
        "and related components"
    ),
    "TOOLS REQUIRED": (
        "a generic marine engine workshop illustration showing categories "
        "of hand tools and inspection tools used during injector maintenance"
    ),
    "SAFETY PRECAUTIONS": (
        "a generic marine engine maintenance safety illustration showing "
        "personal protective equipment, isolation and safe working practices"
    ),
    "REMOVAL PROCEDURE": (
        "a generic educational sequence showing the conceptual removal "
        "of a fuel injector from a marine diesel engine"
    ),
    "INSPECTION": (
        "a generic educational illustration showing visual inspection "
        "concepts for a fuel injector and related components"
    ),
    "INSTALLATION": (
        "a generic educational sequence showing the conceptual installation "
        "of a fuel injector in a marine diesel engine"
    ),
    "TROUBLESHOOTING": (
        "a generic educational diagnostic workflow for investigating "
        "a fuel-injection-related engine fault"
    ),
    "PRACTICAL EXERCISE": (
        "a generic marine-engine workshop training scene showing technicians "
        "performing a supervised injector-maintenance exercise"
    ),
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"Required JSON file not found: {path}"
        )

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(
            f"Expected JSON object in {path}"
        )

    return data


def save_json(
    path: Path,
    data: dict[str, Any],
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )


def safe_filename(value: str) -> str:
    cleaned = re.sub(
        r"[^A-Za-z0-9]+",
        "_",
        value,
    )

    cleaned = cleaned.strip("_")

    return cleaned or "visual"


def get_input_value(
    input_data: dict[str, Any],
    key: str,
) -> str:

    value = input_data.get(key)

    if value is None:
        return ""

    return str(value).strip()


def build_prompt(
    section: str,
    input_data: dict[str, Any],
    request_data: dict[str, Any],
) -> str:

    manufacturer = get_input_value(
        input_data,
        "manufacturer",
    )

    engine_model = get_input_value(
        input_data,
        "engine_model",
    )

    topic = get_input_value(
        input_data,
        "topic",
    )

    vessel = get_input_value(
        input_data,
        "vessel",
    )

    description = SECTION_DESCRIPTIONS.get(
        section,
        "a generic marine-engine training illustration",
    )

    restrictions = [
        "Create a generic educational training illustration.",
        "This must NOT reproduce an OEM figure.",
        "Do not make the image look like an official OEM manual figure.",
        "Do not invent technical specifications.",
        "Do not invent part numbers.",
        "Do not invent torque values.",
        "Do not invent pressures.",
        "Do not invent temperatures.",
        "Do not invent dimensions.",
        "Do not invent clearances.",
        "Do not invent electrical or wiring details.",
        "Do not invent exact component locations.",
        "Do not invent exact OEM geometry.",
        "Do not invent an exact OEM layout.",
        "Do not show unsupported numerical values.",
        "Do not imply that the illustration is an OEM-approved procedure.",
        f'Include this exact visible label: "{AI_LABEL}".',
        "Use clean professional technical-training artwork.",
        "Use generic component shapes where exact OEM geometry is unknown.",
        "Do not place fake part numbers or fake specifications in the image.",
    ]

    prompt_parts = [
        "Create a professional marine-engine technician training illustration.",
        f"Training section: {section}.",
        f"Training topic: {topic or 'Marine engine maintenance'}.",
        f"Manufacturer context: {manufacturer or 'Marine diesel engine'}.",
        f"Engine context: {engine_model or 'Marine diesel engine'}.",
        f"Vessel context: {vessel or 'Marine vessel'}.",
        f"Visual purpose: {description}.",
        "",
        "The illustration is an educational concept only.",
        "It is not an OEM technical drawing.",
        "",
        "Visual requirements:",
        *restrictions,
    ]

    prompt = "\n".join(prompt_parts)

    original_prompt = request_data.get(
        "prompt"
    )

    if original_prompt:
        prompt += (
            "\n\nThe following fallback request was created by "
            "the MarineWise visual planner. Preserve its safety "
            "restrictions while generating the image:\n"
            f"{original_prompt}"
        )

    return prompt


def add_required_label(
    image_path: Path,
) -> Path:
    """
    The image-generation provider is expected to place the required
    label in the generated image.

    This function deliberately does not modify the image pixels.
    The generated-image metadata records the mandatory label so that
    downstream document-generation stages can display the label
    independently if required.
    """

    return image_path


def decode_image_response(
    response: requests.Response,
) -> bytes:

    content_type = (
        response.headers.get(
            "content-type",
            "",
        )
        .lower()
    )

    if "application/json" in content_type:

        payload = response.json()

        image_data = None

        if isinstance(payload, dict):

            image_data = payload.get(
                "image"
            )

            if image_data is None:
                image_data = payload.get(
                    "image_base64"
                )

            if image_data is None:
                image_data = payload.get(
                    "b64_json"
                )

            if image_data is None:
                data = payload.get(
                    "data"
                )

                if isinstance(data, list) and data:
                    first = data[0]

                    if isinstance(first, dict):
                        image_data = (
                            first.get("b64_json")
                            or first.get("image_base64")
                            or first.get("image")
                        )

        if not image_data:
            raise ValueError(
                "Image API returned JSON but no base64 image "
                "field was found."
            )

        if isinstance(image_data, str):

            if image_data.startswith(
                "data:image"
            ):
                image_data = image_data.split(
                    ",",
                    1,
                )[1]

            return base64.b64decode(
                image_data
            )

        raise ValueError(
            "Unsupported image response format."
        )

    if content_type.startswith(
        "image/"
    ):
        return response.content

    raise ValueError(
        "Image API returned an unsupported content type: "
        f"{content_type}"
    )


def generate_image(
    prompt: str,
    output_path: Path,
) -> dict[str, Any]:

    api_url = os.getenv(
        "MARINEWISE_IMAGE_API_URL"
    )

    api_key = os.getenv(
        "MARINEWISE_IMAGE_API_KEY"
    )

    if not api_url:
        raise RuntimeError(
            "MARINEWISE_IMAGE_API_URL is not configured."
        )

    if not api_key:
        raise RuntimeError(
            "MARINEWISE_IMAGE_API_KEY is not configured."
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "prompt": prompt,
        "size": "1024x1024",
        "response_format": "b64_json",
    }

    response = requests.post(
        api_url,
        headers=headers,
        json=payload,
        timeout=180,
    )

    if response.status_code >= 400:
        raise RuntimeError(
            "Image generation API request failed. "
            f"HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    image_bytes = decode_image_response(
        response
    )

    if not image_bytes:
        raise RuntimeError(
            "Image generation API returned empty image data."
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_bytes(
        image_bytes
    )

    return {
        "status": "GENERATED",
        "provider_url": api_url,
        "file": str(output_path),
        "label": AI_LABEL,
    }


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "MarineWise AI controlled visual generator. "
            "Generates images only for sections explicitly "
            "marked as AI fallback by STEP 32C."
        )
    )

    parser.add_argument(
        "--validated",
        required=True,
        help="STEP 32C validated_visual_requests.json",
    )

    parser.add_argument(
        "--output-dir",
        default="ai_training_visuals",
        help="Directory for generated AI visuals.",
    )

    parser.add_argument(
        "--manifest",
        default="ai_training_visual_manifest.json",
        help="Output manifest JSON.",
    )

    args = parser.parse_args()

    validated_path = Path(
        args.validated
    )

    output_dir = Path(
        args.output_dir
    )

    manifest_path = Path(
        args.manifest
    )

    validated = load_json(
        validated_path
    )

    if validated.get("step") != 32:
        raise SystemExit(
            "ERROR: Input is not a STEP 32 result."
        )

    if validated.get("substep") != "32C":
        raise SystemExit(
            "ERROR: Input is not STEP 32C output."
        )

    if validated.get("stage") != (
        "oem_visual_quality_validator"
    ):
        raise SystemExit(
            "ERROR: Input stage is not "
            "oem_visual_quality_validator."
        )

    if validated.get("status") != "SUCCESS":
        raise SystemExit(
            "ERROR: STEP 32C status is not SUCCESS."
        )

    expected_label = (
        "AI Training Illustration — Not an OEM Figure"
    )

    if validated.get(
        "ai_visual_label"
    ) != expected_label:
        raise SystemExit(
            "ERROR: STEP 32C AI visual label is incorrect."
        )

    policy = validated.get(
        "visual_policy",
        {},
    )

    if not policy.get(
        "oem_visual_first"
    ):
        raise SystemExit(
            "ERROR: OEM-first policy is disabled."
        )

    if not policy.get(
        "ai_visual_only_when_oem_visual_is_unavailable"
    ):
        raise SystemExit(
            "ERROR: AI fallback policy is invalid."
        )

    if not policy.get(
        "technical_specs_must_come_from_oem"
    ):
        raise SystemExit(
            "ERROR: OEM technical-specification policy is missing."
        )

    input_data = validated.get(
        "input",
        {},
    )

    ai_requests = validated.get(
        "ai_visual_requests",
        [],
    )

    if not isinstance(
        ai_requests,
        list,
    ):
        raise SystemExit(
            "ERROR: ai_visual_requests must be a list."
        )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    generated_visuals: list[dict[str, Any]] = []

    failed_visuals: list[dict[str, Any]] = []

    skipped_count = 0

    if not ai_requests:

        print(
            "No AI fallback requests were created by STEP 32C."
        )

        print(
            "No AI images will be generated."
        )

    for request_data in ai_requests:

        if not isinstance(
            request_data,
            dict,
        ):
            failed_visuals.append(
                {
                    "status": "INVALID_REQUEST",
                    "reason": (
                        "AI request is not a JSON object."
                    ),
                }
            )
            continue

        section = str(
            request_data.get(
                "section",
                "",
            )
        ).strip()

        if not section:
            failed_visuals.append(
                {
                    "status": "INVALID_REQUEST",
                    "reason": (
                        "AI request has no section."
                    ),
                }
            )
            continue

        visual_source = str(
            request_data.get(
                "visual_source",
                "",
            )
        ).strip()

        if visual_source != "AI_FALLBACK":
            skipped_count += 1

            print(
                f"Skipping {section}: "
                f"visual source is {visual_source}."
            )

            continue

        prompt = build_prompt(
            section,
            input_data,
            request_data,
        )

        filename = (
            safe_filename(section)
            + "_AI_training_illustration.png"
        )

        output_path = (
            output_dir
            / filename
        )

        print()
        print(
            f"Generating AI visual: {section}"
        )

        try:

            generation_result = generate_image(
                prompt,
                output_path,
            )

            add_required_label(
                output_path
            )

            generated_record = {
                "section": section,
                "visual_source": "AI_FALLBACK",
                "status": "GENERATED",
                "label": AI_LABEL,
                "file": str(output_path),
                "prompt": prompt,
                "provider": generation_result.get(
                    "provider_url"
                ),
                "technical_specs_source": (
                    "OEM evidence only"
                ),
                "oem_figure": False,
            }

            generated_visuals.append(
                generated_record
            )

            print(
                f"Generated: {output_path}"
            )

        except Exception as exc:

            failure = {
                "section": section,
                "visual_source": "AI_FALLBACK",
                "status": "GENERATION_FAILED",
                "label": AI_LABEL,
                "error": str(exc),
                "technical_specs_source": (
                    "OEM evidence only"
                ),
                "oem_figure": False,
            }

            failed_visuals.append(
                failure
            )

            print(
                f"WARNING: AI visual generation failed "
                f"for {section}: {exc}"
            )

    manifest = {
        "step": 32,
        "substep": "32D",
        "stage": "controlled_ai_visual_generator",
        "status": (
            "SUCCESS"
            if not failed_visuals
            else "PARTIAL_SUCCESS"
        ),
        "input": input_data,
        "ai_visual_label": AI_LABEL,
        "requested_ai_visuals": len(
            ai_requests
        ),
        "generated_ai_visuals": len(
            generated_visuals
        ),
        "failed_ai_visuals": len(
            failed_visuals
        ),
        "skipped_non_ai_requests": skipped_count,
        "generated_visuals": generated_visuals,
        "failed_visuals": failed_visuals,
        "visual_policy": {
            "oem_visual_first": True,
            "generate_only_ai_fallbacks": True,
            "ai_visual_is_generic_training_illustration": True,
            "ai_visual_not_oem_figure": True,
            "required_label": AI_LABEL,
            "technical_specs_must_come_from_oem": True,
            "part_numbers_must_come_from_oem": True,
            "torque_values_must_come_from_oem": True,
            "pressures_must_come_from_oem": True,
            "temperatures_must_come_from_oem": True,
            "dimensions_must_come_from_oem": True,
            "clearances_must_come_from_oem": True,
            "wiring_details_must_come_from_oem": True,
            "fake_oem_figures_blocked": True,
        },
    }

    save_json(
        manifest_path,
        manifest,
    )

    print()
    print(
        "STEP 32D FILE 1 COMPLETE"
    )
    print(
        "Requested AI visuals:",
        len(ai_requests),
    )
    print(
        "Generated AI visuals:",
        len(generated_visuals),
    )
    print(
        "Failed AI visuals:",
        len(failed_visuals),
    )
    print(
        "Manifest:",
        manifest_path,
    )

    if failed_visuals:
        print()
        print(
            "STEP 32D FILE 1 STATUS: "
            "GENERATOR READY WITH GENERATION FAILURES"
        )
    else:
        print()
        print(
            "STEP 32D FILE 1 STATUS: GREEN"
        )


if __name__ == "__main__":
    main()
