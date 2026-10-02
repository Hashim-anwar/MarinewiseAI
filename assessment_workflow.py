from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


# ============================================================
# MARINEWISE AI
# STEP 33 - ASSESSMENT INTELLIGENCE
# FILE 1 - assessment_workflow.py
# ============================================================

STEP = 33
SUBSTEP = "33A"

STAGE = "assessment_workflow"

STATUS = "READY_FOR_GROQ"


REQUIRED_ASSESSMENT_AREAS = [
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


ASSESSMENT_TYPES = [
    "MULTIPLE_CHOICE",
    "TRUE_FALSE",
    "SHORT_ANSWER",
    "PRACTICAL_SCENARIO",
]


AI_POLICY = {
    "oem_priority": True,
    "oem_evidence_required": True,
    "web_is_not_oem": True,
    "unsupported_technical_claims_blocked": True,
    "invented_part_numbers_blocked": True,
    "invented_torque_values_blocked": True,
    "invented_pressures_blocked": True,
    "invented_clearances_blocked": True,
    "invented_dimensions_blocked": True,
    "invented_procedures_blocked": True,
    "fake_oem_references_blocked": True,
    "answer_key_required": True,
    "source_citation_required": True,
}


def load_json(path: str | Path) -> dict[str, Any]:
    """Load a JSON object from disk."""

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8"
    ) as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(
            f"{path} must contain a JSON object."
        )

    return data


def save_json(
    path: str | Path,
    data: dict[str, Any]
) -> None:
    """Save JSON with readable formatting."""

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


def get_input_data(
    training_workflow: dict[str, Any]
) -> dict[str, Any]:
    """
    Safely retrieve the training input information.

    Supports the existing MarineWise STEP 30 structure.
    """

    input_data = training_workflow.get(
        "input",
        {}
    )

    if not isinstance(input_data, dict):
        return {}

    return input_data


def get_training_evidence(
    training_workflow: dict[str, Any]
) -> list[dict[str, Any]]:
    """
    Collect evidence records from the training workflow.

    The function supports several possible evidence locations
    so the assessment workflow remains compatible with the
    existing training pipeline.
    """

    possible_keys = [
        "evidence",
        "training_evidence",
        "relevant_evidence",
        "oem_evidence",
        "sources",
    ]

    for key in possible_keys:

        value = training_workflow.get(key)

        if isinstance(value, list):

            return [
                item
                for item in value
                if isinstance(item, dict)
            ]

    return []


def get_curriculum(
    training_workflow: dict[str, Any]
) -> list[dict[str, Any]]:
    """
    Retrieve the training curriculum.

    STEP 30 already creates the curriculum, but its exact
    internal shape may vary. Therefore this function safely
    accepts list-based curriculum data.
    """

    curriculum = training_workflow.get(
        "curriculum",
        []
    )

    if isinstance(curriculum, list):

        return [
            item
            for item in curriculum
            if isinstance(item, dict)
        ]

    return []


def build_assessment_distribution(
    question_count: int
) -> dict[str, int]:
    """
    Build a balanced assessment distribution.

    The distribution is deterministic and always totals
    question_count.
    """

    if question_count < 10:
        question_count = 10

    multiple_choice = round(
        question_count * 0.50
    )

    true_false = round(
        question_count * 0.15
    )

    short_answer = round(
        question_count * 0.15
    )

    practical_scenario = (
        question_count
        - multiple_choice
        - true_false
        - short_answer
    )

    return {
        "MULTIPLE_CHOICE": multiple_choice,
        "TRUE_FALSE": true_false,
        "SHORT_ANSWER": short_answer,
        "PRACTICAL_SCENARIO": practical_scenario,
    }


def build_assessment_areas() -> list[dict[str, Any]]:
    """
    Create the required assessment areas.
    """

    areas = []

    for index, area in enumerate(
        REQUIRED_ASSESSMENT_AREAS,
        start=1
    ):

        areas.append(
            {
                "id": index,
                "area": area,
                "evidence_required": True,
                "oem_citation_required": True,
            }
        )

    return areas


def build_learning_objectives(
    training_workflow: dict[str, Any]
) -> list[str]:
    """
    Create assessment objectives based on the training topic.

    These are assessment targets, not technical claims.
    """

    input_data = get_input_data(
        training_workflow
    )

    topic = input_data.get(
        "topic",
        "Marine Engine Maintenance"
    )

    engine = input_data.get(
        "engine_model",
        "Specified Marine Engine"
    )

    return [
        f"Understand the key principles related to {topic}.",
        f"Identify major components and systems of the {engine}.",
        "Apply required workshop safety practices.",
        "Understand the sequence of maintenance activities.",
        "Recognize inspection requirements from OEM evidence.",
        "Apply OEM-supported troubleshooting methods.",
        "Identify when additional OEM information is required.",
        "Demonstrate knowledge through practical scenarios.",
    ]


def build_workflow(
    training_workflow: dict[str, Any],
    question_count: int,
    passing_score: int,
) -> dict[str, Any]:

    input_data = get_input_data(
        training_workflow
    )

    curriculum = get_curriculum(
        training_workflow
    )

    evidence = get_training_evidence(
        training_workflow
    )

    distribution = build_assessment_distribution(
        question_count
    )

    assessment_areas = build_assessment_areas()

    learning_objectives = build_learning_objectives(
        training_workflow
    )

    manufacturer = input_data.get(
        "manufacturer",
        "MAN"
    )

    engine_model = input_data.get(
        "engine_model",
        "16V175D-MM"
    )

    topic = input_data.get(
        "topic",
        "Fuel System and Injector Maintenance"
    )

    vessel = input_data.get(
        "vessel",
        "QL-40"
    )

    technician_level = input_data.get(
        "technician_level",
        "Basic"
    )

    duration = input_data.get(
        "duration",
        "4 Days"
    )

    assessment_instructions = [
        "Generate questions only from supplied training/OEM evidence.",
        "Every technical question must have supporting evidence.",
        "Every answer must be traceable to an OEM source where applicable.",
        "Do not invent technical specifications.",
        "Do not invent part numbers.",
        "Do not invent torque values.",
        "Do not invent pressure values.",
        "Do not invent dimensions or clearances.",
        "Do not create unsupported maintenance procedures.",
        "Clearly identify information that is not supported by evidence.",
        "Provide an answer key for every scored question.",
        "Provide an OEM citation for every technical answer.",
        "Use practical scenarios relevant to marine workshop technicians.",
        "Keep questions appropriate for the specified technician level.",
    ]

    return {
        "step": STEP,
        "substep": SUBSTEP,
        "stage": STAGE,
        "status": STATUS,

        "input": {
            "manufacturer": manufacturer,
            "engine_model": engine_model,
            "topic": topic,
            "vessel": vessel,
            "technician_level": technician_level,
            "duration": duration,
        },

        "assessment_configuration": {
            "question_count": question_count,
            "passing_score_percent": passing_score,
            "assessment_types": ASSESSMENT_TYPES,
            "distribution": distribution,
            "assessment_areas": assessment_areas,
        },

        "learning_objectives": learning_objectives,

        "training_context": {
            "curriculum_available": bool(
                curriculum
            ),
            "curriculum_count": len(
                curriculum
            ),
            "evidence_available": bool(
                evidence
            ),
            "evidence_count": len(
                evidence
            ),
        },

        "assessment_instructions": assessment_instructions,

        "required_output": {
            "questions": True,
            "answer_key": True,
            "explanations": True,
            "oem_citations": True,
            "difficulty_level": True,
            "assessment_area": True,
            "question_type": True,
            "practical_scenarios": True,
            "scoring": True,
            "weak_area_identification": True,
            "retraining_recommendations": True,
        },

        "scoring_model": {
            "multiple_choice": 1,
            "true_false": 1,
            "short_answer": 2,
            "practical_scenario": 3,
            "passing_score_percent": passing_score,
        },

        "ai_policy": AI_POLICY,
    }


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "MarineWise STEP 33A "
            "Assessment Intelligence Workflow"
        )
    )

    parser.add_argument(
        "--training",
        required=True,
        help="STEP 30 training_workflow.json"
    )

    parser.add_argument(
        "--output",
        default="assessment_workflow.json",
        help="Output assessment workflow JSON"
    )

    parser.add_argument(
        "--question-count",
        type=int,
        default=20,
        help="Number of assessment questions"
    )

    parser.add_argument(
        "--passing-score",
        type=int,
        default=70,
        help="Passing score percentage"
    )

    args = parser.parse_args()

    if args.question_count < 10:
        raise ValueError(
            "Question count must be at least 10."
        )

    if not 1 <= args.passing_score <= 100:
        raise ValueError(
            "Passing score must be between 1 and 100."
        )

    training_workflow = load_json(
        args.training
    )

    if training_workflow.get("step") != 30:
        raise ValueError(
            "Input training workflow is not STEP 30."
        )

    assessment_workflow = build_workflow(
        training_workflow=training_workflow,
        question_count=args.question_count,
        passing_score=args.passing_score,
    )

    save_json(
        args.output,
        assessment_workflow
    )

    print(
        "STEP 33 FILE 1 STATUS: GREEN"
    )

    print(
        f"Assessment questions planned: "
        f"{args.question_count}"
    )

    print(
        f"Passing score: "
        f"{args.passing_score}%"
    )

    print(
        f"Assessment areas: "
        f"{len(REQUIRED_ASSESSMENT_AREAS)}"
    )

    print(
        f"Assessment workflow: "
        f"{args.output}"
    )


if __name__ == "__main__":
    main()
