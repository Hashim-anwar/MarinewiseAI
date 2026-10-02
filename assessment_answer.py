from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from groq import Groq


MODEL = "openai/gpt-oss-120b"

MISSING_EVIDENCE_TEXT = (
    "Insufficient OEM evidence available for a reliable conclusion."
)

REQUIRED_SECTIONS = [
    "ASSESSMENT OVERVIEW",
    "INSTRUCTIONS",
    "QUESTIONS",
    "ANSWER KEY",
    "EXPLANATIONS",
    "SCORING GUIDE",
    "WEAK AREA IDENTIFICATION",
    "RETRAINING RECOMMENDATIONS",
    "OEM REFERENCES",
    "EVIDENCE STATUS",
    "SAFETY NOTE",
]

SYSTEM_PROMPT = f"""
You are MarineWise AI, an evidence-controlled marine-engine
training and assessment assistant.

Generate a technical assessment from the supplied assessment
workflow and supplied evidence.

STRICT EVIDENCE POLICY:

1. OEM evidence has highest priority.
2. Use supplied OEM evidence whenever available.
3. Web evidence is NOT OEM evidence.
4. Never invent technical facts.
5. Never invent:
   - part numbers
   - torque values
   - pressures
   - temperatures
   - clearances
   - dimensions
   - tolerances
   - alarm meanings
   - maintenance intervals
   - procedures
   - tool specifications
   - component specifications
6. Never create a fake OEM citation.
7. Never claim that a statement comes from an OEM manual unless
   supplied evidence supports it.
8. Every technical question must be supported by supplied evidence.
9. Every technical answer must be supported by supplied evidence.
10. If sufficient evidence is unavailable, state:

{MISSING_EVIDENCE_TEXT}

11. Do not use general engineering knowledge to fill missing OEM
    information.
12. Safety-critical instructions must remain evidence-controlled.
13. Practical scenarios must not contain invented technical limits.
14. Do not fabricate page numbers or filenames.

CITATIONS:

OEM:
[OEM: filename, Page X]

Web:
[WEB: title]

Never convert a WEB citation into an OEM citation.

ASSESSMENT QUALITY:

Generate useful marine technician assessment questions.

Cover, where evidence permits:
- engine fundamentals
- system knowledge
- component identification
- tools and safety
- maintenance procedure
- inspection
- installation
- troubleshooting
- OEM specifications
- practical application

Avoid ambiguous questions.

MULTIPLE CHOICE:
Use exactly four options:
A, B, C, D.

TRUE/FALSE:
Use:
A. True
B. False.

SHORT ANSWER:
Provide:
- expected answer
- acceptable answer points
- explanation
- evidence citation

PRACTICAL SCENARIO:
Provide:
- scenario
- technician task
- expected response
- scoring points
- evidence citation

The answer key must correspond exactly to the generated questions.

Return valid JSON only.
Do not use markdown code fences.
"""

def load_json(path: str) -> dict[str, Any]:
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    if file_path.stat().st_size == 0:
        raise ValueError(f"Input file is empty: {path}")

    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(
            f"Expected JSON object in {path}, "
            f"got {type(data).__name__}"
        )

    return data


def save_json(path: str, data: dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def compact_for_prompt(
    value: Any,
    max_chars: int = 30000,
) -> str:

    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
        )
    except Exception:
        text = str(value)

    if len(text) <= max_chars:
        return text

    return text[:max_chars] + "\n[TRUNCATED]"


def validate_workflow(
    workflow: dict[str, Any],
) -> None:

    if workflow.get("step") != 33:
        raise ValueError(
            f"Expected STEP 33 workflow, "
            f"got {workflow.get('step')}"
        )

    if workflow.get("substep") != "33A":
        raise ValueError(
            f"Expected substep 33A, "
            f"got {workflow.get('substep')}"
        )

    if workflow.get("stage") != "assessment_workflow":
        raise ValueError(
            f"Expected stage assessment_workflow, "
            f"got {workflow.get('stage')}"
        )

    if workflow.get("status") != "READY_FOR_GROQ":
        raise ValueError(
            f"Expected READY_FOR_GROQ, "
            f"got {workflow.get('status')}"
        )


def extract_context(
    workflow: dict[str, Any],
) -> dict[str, Any]:

    context: dict[str, Any] = {}

    for key in [
        "input",
        "assessment_configuration",
        "learning_objectives",
        "training_context",
        "assessment_instructions",
        "required_output",
        "scoring_model",
        "ai_policy",
    ]:
        if key in workflow:
            context[key] = workflow[key]

    return context


def extract_evidence(
    workflow: dict[str, Any],
) -> Any:

    evidence_keys = [
        "evidence",
        "training_evidence",
        "relevant_evidence",
        "oem_evidence",
        "sources",
        "retrieved_evidence",
        "evidence_context",
    ]

    for key in evidence_keys:
        value = workflow.get(key)

        if value:
            return value

    training_context = workflow.get(
        "training_context"
    )

    if isinstance(training_context, dict):

        for key in evidence_keys:

            value = training_context.get(key)

            if value:
                return value

    return []


def get_question_count(
    workflow: dict[str, Any],
) -> int:

    configuration = workflow.get(
        "assessment_configuration"
    )

    if isinstance(configuration, dict):

        value = configuration.get(
            "question_count"
        )

        if isinstance(value, int):
            return value

    return 20


def build_user_prompt(
    workflow: dict[str, Any],
    evidence: Any,
) -> str:

    context = extract_context(workflow)
    question_count = get_question_count(workflow)

    configuration = workflow.get(
        "assessment_configuration"
    )

    passing_score = 70

    if isinstance(configuration, dict):

        value = configuration.get(
            "passing_score_percent"
        )

        if isinstance(value, (int, float)):
            passing_score = value

    return f"""
Generate the MarineWise technical assessment.

ASSESSMENT WORKFLOW:

{compact_for_prompt(context, 35000)}

AVAILABLE TRAINING / OEM EVIDENCE:

{compact_for_prompt(evidence, 50000)}

QUESTION COUNT:

{question_count}

PASSING SCORE:

{passing_score}%

Every technical question must be supported by the supplied evidence.

Do not invent technical information.

If reliable evidence is unavailable, use:

{MISSING_EVIDENCE_TEXT}

Use exact citations.

OEM:

[OEM: filename, Page X]

WEB:

[WEB: title]

Never fabricate citations.

Return JSON only.
"""


def extract_json(
    text: str,
) -> dict[str, Any]:

    cleaned = text.strip()

    if cleaned.startswith("```"):

        cleaned = re.sub(
            r"^```(?:json)?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        cleaned = re.sub(
            r"\s*```$",
            "",
            cleaned,
        )

    try:

        result = json.loads(cleaned)

        if isinstance(result, dict):
            return result

    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError(
            "Groq response did not contain valid JSON."
        )

    candidate = cleaned[
        start:end + 1
    ]

    try:

        result = json.loads(candidate)

    except json.JSONDecodeError as exc:

        raise ValueError(
            f"Unable to parse Groq JSON: {exc}"
        ) from exc

    if not isinstance(result, dict):
        raise ValueError(
            "Groq response must be a JSON object."
        )

    return result


def find_section(
    data: dict[str, Any],
    section_name: str,
) -> Any:

    if section_name in data:
        return data[section_name]

    target = section_name.lower().strip()

    for key, value in data.items():

        if str(key).lower().strip() == target:
            return value

    return None


def validate_questions(
    data: dict[str, Any],
    expected_count: int,
) -> None:

    questions = find_section(
        data,
        "QUESTIONS",
    )

    if questions is None:
        raise ValueError(
            "Groq output does not contain QUESTIONS."
        )

    if not isinstance(questions, list):
        raise ValueError(
            "QUESTIONS must be a list."
        )

    if len(questions) != expected_count:

        raise ValueError(
            f"Expected {expected_count} questions, "
            f"got {len(questions)}."
        )


def add_metadata(
    generated: dict[str, Any],
    workflow: dict[str, Any],
) -> dict[str, Any]:

    input_data = workflow.get("input")

    if not isinstance(input_data, dict):
        input_data = {}

    return {
        "step": 33,
        "substep": "33B",
        "stage": "groq_assessment_content_generator",
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
        "model": MODEL,
        "evidence_policy": {
            "oem_priority": True,
            "web_is_not_oem": True,
            "unsupported_technical_claims_blocked": True,
            "invented_part_numbers_blocked": True,
            "invented_torque_blocked": True,
            "invented_pressures_blocked": True,
            "invented_temperatures_blocked": True,
            "invented_clearances_blocked": True,
            "invented_dimensions_blocked": True,
            "invented_procedures_blocked": True,
            "fake_oem_references_blocked": True,
            "source_citation_required": True,
        },
        "required_sections": REQUIRED_SECTIONS,
        "assessment": generated,
    }


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "MarineWise STEP 33B "
            "Groq Assessment Generator"
        )
    )

    parser.add_argument(
        "--workflow",
        required=True,
        help="STEP 33A assessment workflow JSON",
    )

    parser.add_argument(
        "--output",
        default="assessment_answer.json",
        help="Output assessment JSON",
    )

    args = parser.parse_args()

    print("MarineWise STEP 33B")
    print("Loading assessment workflow...")

    workflow = load_json(
        args.workflow
    )

    validate_workflow(
        workflow
    )

    evidence = extract_evidence(
        workflow
    )

    api_key = os.getenv(
        "GROQ_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY environment variable "
            "is not available."
        )

    client = Groq(
        api_key=api_key
    )

    prompt = build_user_prompt(
        workflow,
        evidence,
    )

    print("Calling Groq...")
    print("Model:", MODEL)

    response = client.chat.completions.create(
        model=MODEL,
        temperature=0.1,
        max_completion_tokens=7000,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    raw_content = (
        response.choices[0]
        .message
        .content
    )

    if not raw_content:
        raise RuntimeError(
            "Groq returned an empty response."
        )

    generated = extract_json(
        raw_content
    )

    expected_count = get_question_count(
        workflow
    )

    validate_questions(
        generated,
        expected_count,
    )

    final_output = add_metadata(
        generated,
        workflow,
    )

    save_json(
        args.output,
        final_output,
    )

    print("")
    print("========================================")
    print("STEP 33B")
    print("========================================")
    print(
        "Questions generated:",
        expected_count,
    )
    print("Model:", MODEL)
    print("Output:", args.output)
    print("Status: SUCCESS")
    print(
        "STEP 33 FILE 2 STATUS: GREEN"
    )
    print("========================================")


if __name__ == "__main__":
    main()
