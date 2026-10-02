from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_PASSING_SCORE = 70

REQUIRED_AREAS = [
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


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def normalize_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_answer(value: Any) -> str:
    return normalize_text(value).lower().strip()


def find_questions(data: Any) -> list[dict[str, Any]]:
    """
    Recursively locate the generated QUESTIONS list.

    Supports the different nesting structures that may be returned
    by the Groq assessment generator.
    """
    if isinstance(data, list):
        if data and all(isinstance(item, dict) for item in data):
            question_like = 0

            for item in data:
                keys = {str(k).upper() for k in item.keys()}

                if (
                    "QUESTION" in keys
                    or "QUESTION_TEXT" in keys
                    or "TYPE" in keys
                    or "OPTIONS" in keys
                ):
                    question_like += 1

            if question_like >= max(1, len(data) // 2):
                return data

        for item in data:
            result = find_questions(item)

            if result:
                return result

        return []

    if isinstance(data, dict):
        for key, value in data.items():
            if str(key).upper() == "QUESTIONS":
                result = find_questions(value)

                if result:
                    return result

        for value in data.values():
            result = find_questions(value)

            if result:
                return result

    return []


def find_answer_key(data: Any) -> Any:
    """
    Recursively locate ANSWER KEY.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if str(key).upper() in {
                "ANSWER KEY",
                "ANSWER_KEY",
                "ANSWERKEY",
            }:
                return value

        for value in data.values():
            result = find_answer_key(value)

            if result is not None:
                return result

    elif isinstance(data, list):
        for item in data:
            result = find_answer_key(item)

            if result is not None:
                return result

    return None


def get_question_number(question: dict[str, Any], index: int) -> str:
    for key in (
        "number",
        "question_number",
        "id",
        "question_id",
    ):
        if key in question:
            return str(question[key])

    return str(index + 1)


def get_question_text(question: dict[str, Any]) -> str:
    for key in (
        "question",
        "question_text",
        "text",
        "prompt",
    ):
        value = question.get(key)

        if value:
            return normalize_text(value)

    return ""


def get_question_type(question: dict[str, Any]) -> str:
    for key in (
        "type",
        "question_type",
        "assessment_type",
    ):
        value = question.get(key)

        if value:
            return normalize_text(value).upper()

    return "UNKNOWN"


def get_question_area(question: dict[str, Any]) -> str:
    for key in (
        "area",
        "assessment_area",
        "category",
        "topic",
    ):
        value = question.get(key)

        if value:
            return normalize_text(value).upper()

    return "UNSPECIFIED"


def get_correct_answer(
    question: dict[str, Any],
    answer_key: Any,
) -> str:
    """
    First look inside the question.

    Then try common answer-key structures.
    """
    for key in (
        "correct_answer",
        "answer",
        "correct",
        "expected_answer",
    ):
        value = question.get(key)

        if value is not None:
            return normalize_text(value)

    number = get_question_number(question, 0)

    if isinstance(answer_key, list):
        for item in answer_key:
            if not isinstance(item, dict):
                continue

            item_number = str(
                item.get("number")
                or item.get("question_number")
                or item.get("id")
                or ""
            )

            if item_number == number:
                for key in (
                    "answer",
                    "correct_answer",
                    "correct",
                    "expected_answer",
                ):
                    if item.get(key) is not None:
                        return normalize_text(item[key])

    elif isinstance(answer_key, dict):
        direct = answer_key.get(number)

        if direct is not None:
            if isinstance(direct, dict):
                for key in (
                    "answer",
                    "correct_answer",
                    "correct",
                    "expected_answer",
                ):
                    if direct.get(key) is not None:
                        return normalize_text(direct[key])

            return normalize_text(direct)

    return ""


def extract_oem_citation(question: dict[str, Any]) -> str:
    for key in (
        "oem_citation",
        "citation",
        "source",
        "reference",
        "oem_reference",
    ):
        value = question.get(key)

        if value:
            return normalize_text(value)

    return ""


def build_answer_sheet(
    assessment: dict[str, Any],
    questions: list[dict[str, Any]],
) -> dict[str, Any]:
    rows = []

    for index, question in enumerate(questions):
        rows.append(
            {
                "question_number": get_question_number(
                    question,
                    index,
                ),
                "answer": "",
            }
        )

    return {
        "step": 34,
        "mode": "ANSWER_SHEET",
        "status": "READY_FOR_TRAINEE",
        "source_assessment": assessment.get(
            "step",
            33,
        ),
        "instructions": [
            "Enter one answer for each question.",
            "Do not modify question numbers.",
            "Submit the completed answer sheet for scoring.",
        ],
        "answers": rows,
    }


def answers_to_map(answers: Any) -> dict[str, str]:
    result: dict[str, str] = {}

    if isinstance(answers, dict):
        for key, value in answers.items():
            result[str(key)] = normalize_text(value)

    elif isinstance(answers, list):
        for item in answers:
            if not isinstance(item, dict):
                continue

            number = (
                item.get("question_number")
                or item.get("number")
                or item.get("id")
            )

            answer = (
                item.get("answer")
                or item.get("response")
                or ""
            )

            if number is not None:
                result[str(number)] = normalize_text(answer)

    return result


def answer_matches(
    trainee_answer: str,
    correct_answer: str,
    question_type: str,
) -> bool:
    trainee = normalize_answer(trainee_answer)
    correct = normalize_answer(correct_answer)

    if not trainee or not correct:
        return False

    # Exact match first.
    if trainee == correct:
        return True

    # Multiple-choice answers may appear as:
    # A
    # A.
    # A) ...
    if question_type in {
        "MULTIPLE_CHOICE",
        "MCQ",
    }:
        trainee_letter = trainee[:1]

        correct_letter = correct[:1]

        if (
            trainee_letter in {"a", "b", "c", "d"}
            and correct_letter in {"a", "b", "c", "d"}
        ):
            return trainee_letter == correct_letter

    # True/False normalization.
    true_values = {
        "true",
        "t",
        "yes",
        "correct",
    }

    false_values = {
        "false",
        "f",
        "no",
        "incorrect",
    }

    if trainee in true_values and correct in true_values:
        return True

    if trainee in false_values and correct in false_values:
        return True

    return False


def calculate_area_results(
    question_results: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    area_results: dict[str, dict[str, int]] = {}

    for result in question_results:
        area = result.get(
            "assessment_area",
            "UNSPECIFIED",
        )

        if area not in area_results:
            area_results[area] = {
                "questions": 0,
                "correct": 0,
            }

        area_results[area]["questions"] += 1

        if result.get("correct"):
            area_results[area]["correct"] += 1

    return area_results


def build_retraining_recommendations(
    area_results: dict[str, dict[str, int]],
) -> list[dict[str, Any]]:
    recommendations = []

    for area, result in area_results.items():
        total = result["questions"]
        correct = result["correct"]

        if total <= 0:
            continue

        percentage = round(
            (correct / total) * 100,
            1,
        )

        if percentage < 50:
            priority = "HIGH"
            action = (
                "Repeat the relevant OEM training section, "
                "followed by supervised practical training "
                "and reassessment."
            )
        elif percentage < 70:
            priority = "MEDIUM"
            action = (
                "Review the relevant OEM material and "
                "complete a focused practical exercise "
                "before reassessment."
            )
        else:
            continue

        recommendations.append(
            {
                "assessment_area": area,
                "score_percent": percentage,
                "priority": priority,
                "recommended_action": action,
            }
        )

    recommendations.sort(
        key=lambda item: (
            0 if item["priority"] == "HIGH" else 1,
            item["score_percent"],
        )
    )

    return recommendations


def score_assessment(
    assessment: dict[str, Any],
    answers: Any,
    passing_score: int,
) -> dict[str, Any]:
    questions = find_questions(assessment)

    if not questions:
        raise ValueError(
            "No assessment QUESTIONS were found."
        )

    answer_key = find_answer_key(assessment)

    answer_map = answers_to_map(answers)

    question_results = []

    for index, question in enumerate(questions):
        number = get_question_number(
            question,
            index,
        )

        question_type = get_question_type(
            question
        )

        area = get_question_area(
            question
        )

        trainee_answer = answer_map.get(
            number,
            "",
        )

        correct_answer = get_correct_answer(
            question,
            answer_key,
        )

        correct = answer_matches(
            trainee_answer,
            correct_answer,
            question_type,
        )

        question_results.append(
            {
                "question_number": number,
                "assessment_area": area,
                "question_type": question_type,
                "question": get_question_text(
                    question
                ),
                "trainee_answer": trainee_answer,
                "correct_answer_available": bool(
                    correct_answer
                ),
                "correct": correct,
                "oem_citation": extract_oem_citation(
                    question
                ),
            }
        )

    total_questions = len(question_results)

    correct_answers = sum(
        1
        for item in question_results
        if item["correct"]
    )

    unanswered = sum(
        1
        for item in question_results
        if not item["trainee_answer"]
    )

    score_percent = round(
        (correct_answers / total_questions) * 100,
        1,
    ) if total_questions else 0

    passed = score_percent >= passing_score

    area_results = calculate_area_results(
        question_results
    )

    area_scores = {}

    for area, result in area_results.items():
        total = result["questions"]
        correct = result["correct"]

        area_scores[area] = {
            "questions": total,
            "correct": correct,
            "score_percent": round(
                (correct / total) * 100,
                1,
            ) if total else 0,
        }

    weak_areas = [
        area
        for area, result in area_scores.items()
        if result["score_percent"] < 70
    ]

    strong_areas = [
        area
        for area, result in area_scores.items()
        if result["score_percent"] >= 80
    ]

    retraining = build_retraining_recommendations(
        area_scores
    )

    return {
        "step": 34,
        "stage": "assessment_scoring_retraining_intelligence",
        "status": "SUCCESS",
        "assessment_summary": {
            "total_questions": total_questions,
            "correct_answers": correct_answers,
            "unanswered": unanswered,
            "score_percent": score_percent,
            "passing_score_percent": passing_score,
            "passed": passed,
        },
        "question_results": question_results,
        "area_scores": area_scores,
        "strong_areas": strong_areas,
        "weak_areas": weak_areas,
        "retraining_recommendations": retraining,
        "training_recommendation": (
            "No additional targeted retraining identified."
            if not retraining
            else (
                "Targeted retraining is recommended for "
                "the identified weak areas."
            )
        ),
        "evidence_policy": {
            "assessment_answers_should_be_oem_grounded": True,
            "oem_citations_preserved": True,
            "unsupported_technical_claims_blocked": True,
            "invented_technical_values_blocked": True,
        },
        "safety_note": (
            "Assessment results support training decisions only. "
            "Actual maintenance work must follow applicable OEM "
            "procedures, safety requirements, and authorized "
            "technical supervision."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "MarineWise assessment scoring and "
            "retraining intelligence."
        )
    )

    parser.add_argument(
        "--assessment",
        required=True,
        help="Path to assessment_answer.json",
    )

    parser.add_argument(
        "--answers",
        required=False,
        help="Path to trainee answers JSON.",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Output JSON file.",
    )

    parser.add_argument(
        "--passing-score",
        type=int,
        default=DEFAULT_PASSING_SCORE,
        help="Passing score percentage.",
    )

    parser.add_argument(
        "--prepare",
        action="store_true",
        help="Create a blank trainee answer sheet.",
    )

    args = parser.parse_args()

    assessment_path = Path(args.assessment)
    output_path = Path(args.output)

    print("=" * 40)
    print("STEP 34")
    print("=" * 40)

    if not 1 <= args.passing_score <= 100:
        raise ValueError(
            "Passing score must be between 1 and 100."
        )

    print("Loading assessment...")

    assessment = load_json(
        assessment_path
    )

    questions = find_questions(
        assessment
    )

    if not questions:
        raise ValueError(
            "Assessment does not contain QUESTIONS."
        )

    print(
        f"Questions found: {len(questions)}"
    )

    if args.prepare:
        result = build_answer_sheet(
            assessment,
            questions,
        )

        save_json(
            output_path,
            result,
        )

        print(
            f"Answer sheet: {output_path}"
        )
        print(
            "STEP 34 STATUS: GREEN"
        )
        return

    if not args.answers:
        raise ValueError(
            "--answers is required unless --prepare is used."
        )

    answers_path = Path(
        args.answers
    )

    answers = load_json(
        answers_path
    )

    result = score_assessment(
        assessment,
        answers,
        args.passing_score,
    )

    save_json(
        output_path,
        result,
    )

    summary = result[
        "assessment_summary"
    ]

    print()
    print(
        f"Score: {summary['score_percent']}%"
    )
    print(
        f"Correct: {summary['correct_answers']}"
        f"/{summary['total_questions']}"
    )
    print(
        f"Passing score: "
        f"{summary['passing_score_percent']}%"
    )
    print(
        f"Result: "
        f"{'PASS' if summary['passed'] else 'RETRAINING REQUIRED'}"
    )

    print(
        "Weak areas:",
        len(result["weak_areas"]),
    )

    print(
        "Retraining recommendations:",
        len(
            result[
                "retraining_recommendations"
            ]
        ),
    )

    print(
        f"Output: {output_path}"
    )

    print(
        "STEP 34 STATUS: GREEN"
    )

    print("=" * 40)


if __name__ == "__main__":
    main()
