from __future__ import annotations

import argparse
import json
import os
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


SYSTEM_PROMPT = """
You are MarineWise AI, an evidence-controlled marine engine
training assessment generator.

Generate a technician assessment strictly from the supplied
assessment workflow and supplied OEM evidence.

CRITICAL RULES:

1. OEM evidence has the highest priority.
2. Do not invent technical information.
3. Do not invent part numbers.
4. Do not invent torque values.
5. Do not invent pressures.
6. Do not invent temperatures.
7. Do not invent clearances.
8. Do not invent dimensions.
9. Do not invent maintenance intervals.
10. Do not invent procedures.
11. Do not invent tools or special tools.
12. Do not invent alarm meanings.
13. Do not invent component specifications.
14. Do not create fake OEM references.
15. Every technical question must be supported by supplied evidence.
16. Technical answers must include OEM citations.
17. Web evidence must never be represented as OEM evidence.
18. If reliable OEM evidence is unavailable, use exactly:

Insufficient OEM evidence available for a reliable conclusion.

19. Questions must be appropriate for marine technicians.
20. Questions must test the supplied training curriculum.
21. Include different difficulty levels.
22. Follow the requested assessment types.
23. Multiple-choice questions must have exactly four options:
    A, B, C and D.
24. True/False questions must use:
    A. True
    B. False
25. Short-answer questions must include expected answer points.
26. Practical scenarios must include scoring points.
27. Include an answer key.
28. Include explanations.
29. Include scoring guidance.
30. Identify weak training areas.
31. Provide evidence-based retraining recommendations.
32. Return valid JSON only.
33. Do not wrap the final JSON in Markdown.
"""


def load_json(path: str) -> dict[str, Any]:
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"File not found: {path}"
        )

    with file_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(
            f"{path} must contain a JSON object."
        )

    return data


def save_json(
    path: str,
    data: dict[str, Any],
) -> None:
    file_path = Path(path)

    file_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with file_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )


def compact_for_prompt(
    value: Any,
    max_chars: int = 30000,
) -> str:
    text = json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
    )

    if len(text) <= max_chars:
        return text

    return (
        text[:max_chars]
        + "\n...[TRUNCATED]..."
    )


def validate_workflow(
    workflow: dict[str, Any],
) -> None:
    if workflow.get("step") != 33:
        raise ValueError(
            "Expected assessment workflow step 33, "
            f"got {workflow.get('step')}"
        )

    if workflow.get("substep") != "33A":
        raise ValueError(
            "Expected assessment workflow substep 33A, "
            f"got {workflow.get('substep')}"
        )

    if workflow.get("stage") != "assessment_workflow":
        raise ValueError(
            "Unexpected assessment workflow stage: "
            f"{workflow.get('stage')}"
        )

    if workflow.get("status") != "READY_FOR_GROQ":
        raise ValueError(
            "Assessment workflow is not READY_FOR_GROQ: "
            f"{workflow.get('status')}"
        )


def extract_context(
    workflow: dict[str, Any],
) -> dict[str, Any]:

    input_data = workflow.get(
        "input",
        {},
    )

    if not isinstance(input_data, dict):
        input_data = {}

    configuration = workflow.get(
        "assessment_configuration",
        {},
    )

    if not isinstance(configuration, dict):
        configuration = {}

    training_context = workflow.get(
        "training_context",
        {},
    )

    if not isinstance(training_context, dict):
        training_context = {}

    return {
        "input": input_data,
        "assessment_configuration": configuration,
        "training_context": training_context,
        "learning_objectives": workflow.get(
            "learning_objectives",
            [],
        ),
        "assessment_instructions": workflow.get(
            "assessment_instructions",
            [],
        ),
        "required_output": workflow.get(
            "required_output",
            {},
        ),
        "scoring_model": workflow.get(
            "scoring_model",
            {},
        ),
    }


def extract_evidence(
    workflow: dict[str, Any],
) -> list[Any]:

    possible_keys = [
        "evidence",
        "training_evidence",
        "relevant_evidence",
        "oem_evidence",
        "sources",
    ]

    for key in possible_keys:
        value = workflow.get(key)

        if isinstance(value, list):
            return value

    training_context = workflow.get(
        "training_context",
        {},
    )

    if isinstance(training_context, dict):

        for key in possible_keys:
            value = training_context.get(key)

            if isinstance(value, list):
                return value

    return []


def get_question_count(
    workflow: dict[str, Any],
) -> int:

    configuration = workflow.get(
        "assessment_configuration",
        {},
    )

    if isinstance(configuration, dict):

        value = configuration.get(
            "question_count",
            20,
        )

        try:
            return int(value)
        except (
            TypeError,
            ValueError,
        ):
            pass

    return 20


def get_passing_score(
    workflow: dict[str, Any],
) -> int:

    configuration = workflow.get(
        "assessment_configuration",
        {},
    )

    if isinstance(configuration, dict):

        value = configuration.get(
            "passing_score_percent",
            configuration.get(
                "passing_score",
                70,
            ),
        )

        try:
            return int(value)
        except (
            TypeError,
            ValueError,
        ):
            pass

    return 70


def build_user_prompt(
    workflow: dict[str, Any],
    evidence: list[Any],
) -> str:

    context = extract_context(
        workflow
    )

    question_count = get_question_count(
        workflow
    )

    passing_score = get_passing_score(
        workflow
    )

    payload = {
        "assessment_context": context,
        "requested_question_count": question_count,
        "passing_score_percent": passing_score,
        "evidence": evidence,
    }

    return f"""
Generate the MarineWise technician assessment.

The assessment must contain exactly
{question_count}
questions.

Passing score:
{passing_score} percent.

Use the supplied assessment workflow and OEM evidence only.

Required assessment sections:

ASSESSMENT OVERVIEW
INSTRUCTIONS
QUESTIONS
ANSWER KEY
EXPLANATIONS
SCORING GUIDE
WEAK AREA IDENTIFICATION
RETRAINING RECOMMENDATIONS
OEM REFERENCES
EVIDENCE STATUS
SAFETY NOTE

For every question include, where applicable:

question_id
type
area
difficulty
question
options
correct_answer
expected_answer
expected_answer_points
explanation
oem_citation
scoring_points

Multiple-choice questions:
exactly four options:
A, B, C and D.

True/False questions:
A = True
B = False.

Short-answer questions:
include expected answer points.

Practical scenarios:
include scoring points.

Technical information must remain strictly within the
supplied evidence.

Technical citations should use this format:

[OEM: filename, Page X]

Do not fabricate citations.

If evidence is insufficient, use exactly:

{MISSING_EVIDENCE_TEXT}

SOURCE DATA:

{compact_for_prompt(payload)}
"""


def extract_json(
    text: str,
) -> dict[str, Any]:
    """
    Safely extract a JSON object from the Groq response.

    Handles:
    1. Pure JSON.
    2. JSON surrounded by Markdown code fences.
    3. JSON embedded inside additional response text.
    """

    cleaned = text.strip()

    if cleaned.startswith("```json"):
        cleaned = cleaned[7:].strip()

    elif cleaned.startswith("```"):
        cleaned = cleaned[3:].strip()

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    try:
        data = json.loads(
            cleaned
        )

        if isinstance(data, dict):
            return data

    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start >= 0 and end > start:

        candidate = cleaned[
            start:end + 1
        ]

        try:
            data = json.loads(
                candidate
            )

            if isinstance(data, dict):
                return data

        except json.JSONDecodeError:
            pass

    raise ValueError(
        "Groq response did not contain valid JSON."
    )


def recursive_find(
    value: Any,
    target_key: str,
) -> Any:

    target = target_key.lower()

    if isinstance(value, dict):

        for key, item in value.items():

            if str(key).lower() == target:
                return item

            found = recursive_find(
                item,
                target_key,
            )

            if found is not None:
                return found

    elif isinstance(value, list):

        for item in value:

            found = recursive_find(
                item,
                target_key,
            )

            if found is not None:
                return found

    return None


def find_section(
    data: dict[str, Any],
    section_name: str,
) -> Any:

    return recursive_find(
        data,
        section_name,
    )


def find_questions(
    data: dict[str, Any],
) -> list[Any] | None:

    result = find_section(
        data,
        "QUESTIONS",
    )

    if isinstance(result, list):
        return result

    result = find_section(
        data,
        "questions",
    )

    if isinstance(result, list):
        return result

    assessment = data.get(
        "assessment"
    )

    if isinstance(assessment, dict):

        result = assessment.get(
            "QUESTIONS"
        )

        if isinstance(result, list):
            return result

        result = assessment.get(
            "questions"
        )

        if isinstance(result, list):
            return result

    return None


def validate_questions(
    data: dict[str, Any],
    expected_count: int,
) -> list[Any]:

    questions = find_questions(
        data
    )

    if questions is None:
        raise ValueError(
            "Groq output does not contain QUESTIONS."
        )

    if not isinstance(
        questions,
        list,
    ):
        raise ValueError(
            "QUESTIONS must be a list."
        )

    if len(questions) != expected_count:
        raise ValueError(
            "Groq generated "
            f"{len(questions)} questions, "
            f"but {expected_count} were required."
        )

    for index, question in enumerate(
        questions,
        start=1,
    ):

        if not isinstance(
            question,
            dict,
        ):
            raise ValueError(
                f"Question {index} is not an object."
            )

        question_text = (
            question.get("question")
            or question.get("text")
            or question.get("prompt")
        )

        if not question_text:
            raise ValueError(
                f"Question {index} has no question text."
            )

    return questions


def validate_answer_key(
    data: dict[str, Any],
) -> None:

    answer_key = find_section(
        data,
        "ANSWER KEY",
    )

    if answer_key is None:
        answer_key = find_section(
            data,
            "answer_key",
        )

    if answer_key is None:
        raise ValueError(
            "Groq output does not contain ANSWER KEY."
        )


def validate_required_sections(
    data: dict[str, Any],
) -> None:

    missing = []

    for section in REQUIRED_SECTIONS:

        found = recursive_find(
            data,
            section,
        )

        if found is None:
            found = recursive_find(
                data,
                section.lower(),
            )

        if found is None:
            missing.append(section)

    if missing:
        raise ValueError(
            "Missing required assessment sections: "
            + ", ".join(missing)
        )


def add_metadata(
    generated: dict[str, Any],
    question_count: int,
    passing_score: int,
) -> dict[str, Any]:

    return {
        "step": 33,
        "substep": "33B",
        "stage": "groq_assessment_content_generator",
        "status": "SUCCESS",
        "model": MODEL,
        "question_count": question_count,
        "passing_score_percent": passing_score,
        "source_workflow": "assessment_workflow.json",
        "evidence_policy": {
            "oem_priority": True,
            "oem_evidence_required": True,
            "web_is_not_oem": True,
            "unsupported_technical_claims_blocked": True,
            "invented_part_numbers_blocked": True,
            "invented_torque_blocked": True,
            "invented_pressures_blocked": True,
            "invented_temperatures_blocked": True,
            "invented_clearances_blocked": True,
            "invented_dimensions_blocked": True,
            "invented_procedures_blocked": True,
            "invented_tools_blocked": True,
            "invented_alarm_meanings_blocked": True,
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
            "Groq Assessment and Quiz Generator"
        )
    )

    parser.add_argument(
        "--workflow",
        required=True,
        help="Path to assessment_workflow.json",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Output assessment JSON path",
    )

    args = parser.parse_args()

    print("========================================")
    print("STEP 33B")
    print("========================================")
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

    question_count = get_question_count(
        workflow
    )

    passing_score = get_passing_score(
        workflow
    )

    print(
        f"Questions requested: {question_count}"
    )

    print(
        f"Passing score: {passing_score}%"
    )

    print(
        f"Evidence records: {len(evidence)}"
    )

    api_key = os.getenv(
        "GROQ_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY environment variable is missing."
        )

    print("Calling Groq...")
    print(
        f"Model: {MODEL}"
    )

    client = Groq(
        api_key=api_key
    )

    user_prompt = build_user_prompt(
        workflow,
        evidence,
    )

    response = client.chat.completions.create(
        model=MODEL,
        temperature=0.1,
        max_completion_tokens=6000,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
    )

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError(
            "Groq returned an empty response."
        )

    generated = extract_json(
        content
    )

    validate_questions(
        generated,
        question_count,
    )

    validate_answer_key(
        generated
    )

    validate_required_sections(
        generated
    )

    final_output = add_metadata(
        generated,
        question_count,
        passing_score,
    )

    save_json(
        args.output,
        final_output,
    )

    print("========================================")
    print(
        f"Questions generated: {question_count}"
    )
    print(
        f"Model: {MODEL}"
    )
    print(
        f"Output: {args.output}"
    )
    print("Status: SUCCESS")
    print(
        "STEP 33 FILE 2 STATUS: GREEN"
    )
    print("========================================")


if __name__ == "__main__":
    main()
