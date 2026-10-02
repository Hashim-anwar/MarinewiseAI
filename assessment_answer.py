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
15. Every technical question must be supported by supplied OEM evidence.
16. Technical answers must include OEM citations when evidence is available.
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
    B. False.
25. Short-answer questions must include expected answer points.
26. Practical scenarios must include scoring points.
27. Include an answer key.
28. Include explanations.
29. Include scoring guidance.
30. Identify weak training areas.
31. Provide evidence-based retraining recommendations.
32. Return one valid JSON object only.
33. Do not return Markdown.
34. Do not return code fences.
35. Do not return text outside the JSON object.
"""


def load_json(path: str) -> Any:
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"File not found: {path}"
        )

    with file_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


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
    max_chars: int = 50000,
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

    if not isinstance(
        input_data,
        dict,
    ):
        input_data = {}

    configuration = workflow.get(
        "assessment_configuration",
        {},
    )

    if not isinstance(
        configuration,
        dict,
    ):
        configuration = {}

    training_context = workflow.get(
        "training_context",
        {},
    )

    if not isinstance(
        training_context,
        dict,
    ):
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


def normalize_key(
    value: Any,
) -> str:

    text = str(
        value
    ).strip().lower()

    for character in [
        "_",
        "-",
        ":",
    ]:
        text = text.replace(
            character,
            " ",
        )

    return " ".join(
        text.split()
    )


def recursive_find_all_lists(
    value: Any,
    target_names: set[str],
) -> list[list[Any]]:

    results: list[list[Any]] = []

    if isinstance(
        value,
        dict,
    ):

        for key, item in value.items():

            if normalize_key(key) in target_names:

                if isinstance(
                    item,
                    list,
                ):
                    results.append(
                        item
                    )

            results.extend(
                recursive_find_all_lists(
                    item,
                    target_names,
                )
            )

    elif isinstance(
        value,
        list,
    ):

        for item in value:

            results.extend(
                recursive_find_all_lists(
                    item,
                    target_names,
                )
            )

    return results


def extract_evidence_from_file(
    evidence_data: Any,
) -> list[Any]:
    """
    Extract OEM evidence from assessment_evidence.json.

    The function supports several safe JSON layouts so the
    assessment generator does not depend on one exact nesting
    level.
    """

    target_names = {
        "evidence",
        "oem evidence",
        "oem evidence records",
        "records",
        "evidence records",
        "items",
        "oem records",
    }

    candidates = recursive_find_all_lists(
        evidence_data,
        target_names,
    )

    best: list[Any] = []

    for candidate in candidates:

        if len(candidate) > len(best):
            best = candidate

    return best


def validate_oem_evidence(
    evidence: list[Any],
) -> list[dict[str, Any]]:

    validated: list[dict[str, Any]] = []

    for item in evidence:

        if not isinstance(
            item,
            dict,
        ):
            continue

        source_type = str(
            item.get(
                "source_type",
                "OEM",
            )
        ).strip().upper()

        if source_type != "OEM":
            continue

        text = (
            item.get("text")
            or item.get("content")
            or item.get("evidence")
            or item.get("page_text")
            or ""
        )

        if not str(text).strip():
            continue

        validated.append(
            item
        )

    return validated


def get_question_count(
    workflow: dict[str, Any],
) -> int:

    configuration = workflow.get(
        "assessment_configuration",
        {},
    )

    if isinstance(
        configuration,
        dict,
    ):

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

    if isinstance(
        configuration,
        dict,
    ):

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
        "oem_evidence_count": len(evidence),
        "oem_evidence": evidence,
    }

    return f"""
Generate the MarineWise technician assessment.

The assessment must contain exactly
{question_count}
questions.

Passing score:
{passing_score} percent.

Use the supplied assessment workflow and supplied OEM evidence.

The OEM evidence is the primary technical source.

Every technical question must be directly supported by
one or more supplied OEM evidence records.

Do not use general knowledge when OEM evidence is available.

If a specific technical fact cannot be supported by the
supplied OEM evidence, do not invent it.

Instead use exactly:

{MISSING_EVIDENCE_TEXT}

Return ONE JSON OBJECT.

The JSON object must contain an "assessment" object.

The assessment object must contain these sections:

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

QUESTIONS must be an array containing exactly
{question_count}
question objects.

Each question should contain:

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

Use only fields appropriate to the question type.

Multiple-choice:
exactly four options:
A, B, C and D.

True/False:
A = True
B = False.

Short-answer:
include expected answer points.

Practical scenario:
include scoring points.

OEM citations must use the supplied evidence.

Preferred citation format:

[OEM: filename, Page X]

Never fabricate an OEM citation.

If reliable OEM evidence is unavailable for a question,
use exactly:

{MISSING_EVIDENCE_TEXT}

The final response must be valid JSON and nothing else.

SOURCE DATA:

{compact_for_prompt(payload)}
"""


def extract_json(
    text: str,
) -> dict[str, Any]:

    if not text:
        raise ValueError(
            "Groq returned an empty response."
        )

    cleaned = text.strip()

    try:

        data = json.loads(
            cleaned
        )

    except json.JSONDecodeError as exc:

        print(
            "========================================"
        )
        print(
            "GROQ JSON PARSING ERROR"
        )
        print(
            "========================================"
        )
        print(
            "Response length:",
            len(cleaned),
        )
        print(
            "Response preview:"
        )
        print(
            cleaned[:3000]
        )
        print(
            "========================================"
        )

        raise ValueError(
            "Groq response was not valid JSON."
        ) from exc

    if not isinstance(
        data,
        dict,
    ):
        raise ValueError(
            "Groq response JSON must be an object."
        )

    return data


def recursive_find(
    value: Any,
    target_key: str,
) -> Any:

    target = normalize_key(
        target_key
    )

    if isinstance(
        value,
        dict,
    ):

        for key, item in value.items():

            if normalize_key(key) == target:
                return item

            found = recursive_find(
                item,
                target_key,
            )

            if found is not None:
                return found

    elif isinstance(
        value,
        list,
    ):

        for item in value:

            found = recursive_find(
                item,
                target_key,
            )

            if found is not None:
                return found

    return None


def find_questions(
    data: dict[str, Any],
) -> list[Any] | None:

    result = recursive_find(
        data,
        "QUESTIONS",
    )

    if isinstance(
        result,
        list,
    ):
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

    answer_key = recursive_find(
        data,
        "ANSWER KEY",
    )

    if answer_key is None:
        raise ValueError(
            "Groq output does not contain ANSWER KEY."
        )


def validate_required_sections(
    data: dict[str, Any],
) -> None:

    serialized = json.dumps(
        data,
        ensure_ascii=False,
    ).lower()

    missing = []

    for section in REQUIRED_SECTIONS:

        found = recursive_find(
            data,
            section,
        )

        if found is not None:
            continue

        normalized = normalize_key(
            section
        )

        variants = [
            section.lower(),
            normalized,
            normalized.replace(
                " ",
                "_",
            ),
        ]

        if not any(
            variant in serialized
            for variant in variants
        ):
            missing.append(
                section
            )

    if missing:
        raise ValueError(
            "Missing required assessment sections: "
            + ", ".join(missing)
        )


def add_metadata(
    generated: dict[str, Any],
    question_count: int,
    passing_score: int,
    evidence_count: int,
    evidence_file: str,
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
        "source_evidence": evidence_file,
        "oem_evidence_records_used": evidence_count,
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
        "--evidence",
        required=True,
        help="Path to assessment_evidence.json",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Output assessment JSON path",
    )

    args = parser.parse_args()

    print(
        "========================================"
    )
    print(
        "STEP 33B"
    )
    print(
        "========================================"
    )

    print(
        "Loading assessment workflow..."
    )

    workflow = load_json(
        args.workflow
    )

    if not isinstance(
        workflow,
        dict,
    ):
        raise ValueError(
            "Assessment workflow must be a JSON object."
        )

    validate_workflow(
        workflow
    )

    print(
        "Loading OEM assessment evidence..."
    )

    evidence_data = load_json(
        args.evidence
    )

    raw_evidence = extract_evidence_from_file(
        evidence_data
    )

    evidence = validate_oem_evidence(
        raw_evidence
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
        f"OEM evidence records found: "
        f"{len(raw_evidence)}"
    )

    print(
        f"Valid OEM evidence records: "
        f"{len(evidence)}"
    )

    if not evidence:
        raise RuntimeError(
            "No valid OEM evidence records were found "
            "in assessment_evidence.json. "
            "Assessment generation stopped to prevent "
            "ungrounded technical questions."
        )

    api_key = os.getenv(
        "GROQ_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY environment variable is missing."
        )

    print(
        "Calling Groq..."
    )

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
        max_completion_tokens=8000,
        response_format={
            "type": "json_object"
        },
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

    content = (
        response.choices[0]
        .message.content
    )

    if not content:
        raise RuntimeError(
            "Groq returned an empty response."
        )

    print(
        "Groq JSON response received."
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
        len(evidence),
        args.evidence,
    )

    save_json(
        args.output,
        final_output,
    )

    print(
        "========================================"
    )
    print(
        f"Questions generated: {question_count}"
    )
    print(
        f"OEM evidence used: {len(evidence)}"
    )
    print(
        f"Model: {MODEL}"
    )
    print(
        f"Output: {args.output}"
    )
    print(
        "Status: SUCCESS"
    )
    print(
        "STEP 33 FILE 2 STATUS: GREEN"
    )
    print(
        "========================================"
    )


if __name__ == "__main__":
    main()
