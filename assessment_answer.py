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


SYSTEM_PROMPT = """
You are MarineWise AI, an evidence-controlled marine engine
training assessment generator.

Your task is to generate a technician assessment strictly from
the supplied assessment workflow and OEM evidence.

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
16. Every technical answer must have an OEM citation.
17. WEB evidence must never be represented as OEM evidence.
18. If reliable OEM evidence is unavailable, use exactly:

Insufficient OEM evidence available for a reliable conclusion.

19. Questions must be appropriate for marine technicians.
20. Questions must test the supplied training curriculum.
21. Include different difficulty levels.
22. Include the requested assessment types.
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
33. Do not wrap JSON in Markdown fences.
"""


def load_json(path: str) -> dict[str, Any]:
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with file_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")

    return data


def save_json(path: str, data: dict[str, Any]) -> None:
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


def compact_for_prompt(value: Any, max_chars: int = 30000) -> str:
    text = json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
    )

    if len(text) <= max_chars:
        return text

    return text[:max_chars] + "\n...[TRUNCATED]..."


def validate_workflow(workflow: dict[str, Any]) -> None:
    if workflow.get("step") != 33:
        raise ValueError(
            f"Expected assessment workflow step 33, "
            f"got {workflow.get('step')}"
        )

    if workflow.get("substep") != "33A":
        raise ValueError(
            f"Expected assessment workflow substep 33A, "
            f"got {workflow.get('substep')}"
        )

    if workflow.get("stage") != "assessment_workflow":
        raise ValueError(
            "Unexpected assessment workflow stage: "
            + str(workflow.get("stage"))
        )

    if workflow.get("status") != "READY_FOR_GROQ":
        raise ValueError(
            "Assessment workflow is not READY_FOR_GROQ: "
            + str(workflow.get("status"))
        )


def extract_context(
    workflow: dict[str, Any],
) -> dict[str, Any]:
    input_data = workflow.get("input", {})

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
        except (TypeError, ValueError):
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
        except (TypeError, ValueError):
            pass

    return 70


def build_user_prompt(
    workflow: dict[str, Any],
    evidence: list[Any],
) -> str:
    context = extract_context(workflow)

    question_count = get_question_count(workflow)
    passing_score = get_passing_score(workflow)

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

Return one valid JSON object.

Required top-level assessment content:

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

- question_id
- type
- area
- difficulty
- question
- options
- correct_answer
- expected_answer
- expected_answer_points
- explanation
- oem_citation
- scoring_points

Multiple-choice questions:
- exactly four options
- A, B, C and D
- exactly one correct answer

True/False:
- A = True
- B = False

Short-answer:
- include expected answer points

Practical scenario:
- include realistic technician scenario
- include scoring points
- remain strictly within supplied evidence

Technical evidence must include exact OEM citations such as:

[OEM: filename, Page X]

Do not fabricate citations.

If evidence is insufficient, use:

{MISSING_EVIDENCE_TEXT}

SOURCE DATA:

{compact_for_prompt(payload)}
"""


def extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()

    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"\s*```$
