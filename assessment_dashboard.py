import json
import re
from pathlib import Path

import streamlit as st


ASSESSMENT_FILE = Path("assessment_answer.json")
EVIDENCE_FILE = Path("assessment_evidence.json")


def load_json(path):
    """Load a JSON file safely."""
    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return None


def find_recursive(data, target_keys):
    """Find the first matching key anywhere in nested JSON."""
    if isinstance(data, dict):
        for key, value in data.items():
            if str(key).upper() in target_keys:
                return value

        for value in data.values():
            result = find_recursive(value, target_keys)

            if result is not None:
                return result

    elif isinstance(data, list):
        for item in data:
            result = find_recursive(item, target_keys)

            if result is not None:
                return result

    return None


def get_questions(assessment):
    """Extract assessment questions from common JSON structures."""
    value = find_recursive(
        assessment,
        {
            "QUESTIONS",
            "QUESTION_LIST",
            "ASSESSMENT QUESTIONS",
        },
    )

    if isinstance(value, list):
        return [
            item
            for item in value
            if isinstance(item, dict)
        ]

    if isinstance(value, dict):
        for key in (
            "questions",
            "QUESTIONS",
            "items",
        ):
            items = value.get(key)

            if isinstance(items, list):
                return [
                    item
                    for item in items
                    if isinstance(item, dict)
                ]

    return []


def get_answer_key(assessment):
    """Extract the answer key recursively."""
    return find_recursive(
        assessment,
        {
            "ANSWER KEY",
            "ANSWER_KEY",
            "ANSWERKEY",
        },
    )


def normalize_answer_key(answer_key):
    """Convert different answer-key structures into one dictionary."""
    result = {}

    if isinstance(answer_key, dict):
        for key, value in answer_key.items():
            result[str(key)] = value

        return result

    if isinstance(answer_key, list):
        for item in answer_key:

            if not isinstance(item, dict):
                continue

            number = (
                item.get("question_number")
                or item.get("number")
                or item.get("id")
            )

            answer = (
                item.get("correct_answer")
                or item.get("answer")
                or item.get("correct")
            )

            if number is not None:
                result[str(number)] = answer

    return result


def get_question_text(question, number):
    """Get the question text."""
    for key in (
        "question",
        "QUESTION",
        "question_text",
        "text",
        "prompt",
    ):
        value = question.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return f"Question {number}"


def get_question_type(question):
    """Get and normalize the question type."""
    for key in (
        "type",
        "question_type",
        "assessment_type",
        "format",
    ):
        value = question.get(key)

        if isinstance(value, str):
            return (
                value.upper()
                .replace("-", "_")
                .replace(" ", "_")
            )

    return "MULTIPLE_CHOICE"


def get_question_area(question):
    """Get the assessment area."""
    for key in (
        "area",
        "assessment_area",
        "learning_area",
        "category",
    ):
        value = question.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return "GENERAL"


def get_options(question):
    """Extract MCQ options."""
    options = question.get("options")

    if isinstance(options, dict):
        return [
            f"{key}. {value}"
            for key, value in options.items()
        ]

    if isinstance(options, list):
        output = []

        for option in options:

            if isinstance(option, dict):

                letter = (
                    option.get("letter")
                    or option.get("key")
                    or option.get("option")
                    or ""
                )

                text = (
                    option.get("text")
                    or option.get("value")
                    or option.get("answer")
                    or ""
                )

                if letter:
                    output.append(
                        f"{letter}. {text}"
                    )
                else:
                    output.append(str(text))

            else:
                output.append(str(option))

        return output

    return []


def get_question_citation(question):
    """Get OEM citation attached to a question."""
    for key in (
        "citation",
        "source_citation",
        "oem_citation",
        "reference",
        "source",
    ):
        value = question.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def normalize_text(value):
    """Normalize answers for comparison."""
    if value is None:
        return ""

    text = str(value).strip().lower()

    text = re.sub(
        r"^[\s\(\[]*[a-d][\)\].:\-]\s*",
        "",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text


def answers_match(user_answer, correct_answer):
    """Compare trainee answer with answer key."""
    if user_answer is None or correct_answer is None:
        return False

    user = normalize_text(user_answer)
    correct = normalize_text(correct_answer)

    if not user or not correct:
        return False

    if user == correct:
        return True

    true_values = {
        "true",
        "t",
        "yes",
    }

    false_values = {
        "false",
        "f",
        "no",
    }

    if user in true_values and correct in true_values:
        return True

    if user in false_values and correct in false_values:
        return True

    return False


def extract_metadata(assessment):
    """Extract assessment metadata."""
    input_data = assessment.get(
        "input",
        {},
    )

    if not isinstance(input_data, dict):
        input_data = {}

    manufacturer = (
        input_data.get("manufacturer")
        or assessment.get("manufacturer")
        or "Not specified"
    )

    engine = (
        input_data.get("engine_model")
        or assessment.get("engine_model")
        or "Not specified"
    )

    vessel = (
        input_data.get("vessel")
        or assessment.get("vessel")
        or "Not specified"
    )

    topic = (
        input_data.get("topic")
        or assessment.get("topic")
        or "Marine Engine Training"
    )

    passing_score = (
        input_data.get("passing_score")
        or assessment.get("passing_score")
        or 70
    )

    try:
        passing_score = float(
            passing_score
        )
    except Exception:
        passing_score = 70.0

    return {
        "manufacturer": manufacturer,
        "engine": engine,
        "vessel": vessel,
        "topic": topic,
        "passing_score": passing_score,
    }


def calculate_result(
    questions,
    answers,
    answer_key,
    passing_score,
):
    """Calculate assessment result."""
    key_map = normalize_answer_key(
        answer_key
    )

    total = len(questions)
    correct = 0
    unanswered = 0

    area_totals = {}
    area_correct = {}

    question_results = []

    for number, question in enumerate(
        questions,
        start=1,
    ):
        area = get_question_area(
            question
        )

        user_answer = answers.get(
            number
        )

        if user_answer in (
            None,
            "",
        ):
            unanswered += 1

        area_totals[area] = (
            area_totals.get(area, 0) + 1
        )

        expected = key_map.get(
            str(number)
        )

        is_correct = False

        if (
            user_answer not in (
                None,
                "",
            )
            and expected is not None
        ):
            is_correct = answers_match(
                user_answer,
                expected,
            )

        if is_correct:
            correct += 1

            area_correct[area] = (
                area_correct.get(area, 0) + 1
            )

        question_results.append(
            {
                "question_number": number,
                "area": area,
                "question": get_question_text(
                    question,
                    number,
                ),
                "user_answer": (
                    user_answer or ""
                ),
                "correct": is_correct,
            }
        )

    percentage = (
        round(
            (correct / total) * 100,
            1,
        )
        if total
        else 0.0
    )

    area_scores = {}

    for area, count in area_totals.items():

        area_scores[area] = round(
            (
                area_correct.get(
                    area,
                    0,
                )
                / count
            )
            * 100,
            1,
        )

    weak_areas = []

    for area, score in area_scores.items():

        if score < 70:

            priority = (
                "HIGH"
                if score < 50
                else "MEDIUM"
            )

            weak_areas.append(
                {
                    "area": area,
                    "score_percent": score,
                    "priority": priority,
                }
            )

    retraining_recommendations = []

    for item in weak_areas:

        if item["score_percent"] < 50:

            recommendation = (
                f"Repeat focused OEM training for "
                f"{item['area']}, followed by a "
                f"supervised practical exercise and "
                f"reassessment."
            )

        else:

            recommendation = (
                f"Review OEM training material for "
                f"{item['area']}, complete a focused "
                f"practical exercise, and reassess."
            )

        retraining_recommendations.append(
            {
                "area": item["area"],
                "priority": item["priority"],
                "recommendation": recommendation,
            }
        )

    return {
        "total_questions": total,
        "correct_answers": correct,
        "unanswered": unanswered,
        "score_percent": percentage,
        "passing_score_percent": passing_score,
        "passed": percentage >= passing_score,
        "question_results": question_results,
        "area_scores": area_scores,
        "weak_areas": weak_areas,
        "retraining_recommendations": (
            retraining_recommendations
        ),
    }


def get_evidence_records(evidence):
    """Extract OEM evidence records."""
    if not isinstance(evidence, dict):
        return []

    records = evidence.get(
        "evidence"
    )

    if isinstance(records, list):
        return [
            item
            for item in records
            if isinstance(item, dict)
        ]

    return []


def render_oem_evidence(evidence):
    """Display OEM evidence."""
    records = get_evidence_records(
        evidence
    )

    if not records:
        st.info(
            "No OEM evidence records are available."
        )
        return

    for number, record in enumerate(
        records[:20],
        start=1,
    ):
        citation = record.get(
            "citation",
            "",
        )

        source_file = record.get(
            "source_file",
            "",
        )

        page = record.get(
            "page",
            "",
        )

        evidence_text = record.get(
            "evidence_text",
            "",
        )

        title = (
            citation
            or f"OEM Evidence {number}"
        )

        with st.expander(title):

            if source_file:
                st.write(
                    f"**Source:** {source_file}"
                )

            if page:
                st.write(
                    f"**Page:** {page}"
                )

            if citation:
                st.write(
                    f"**Citation:** {citation}"
                )

            if evidence_text:
                st.write(
                    evidence_text
                )


def show_assessment():
    """
    Display the MarineWise assessment module.

    This function is imported by app.py.
    It intentionally does not call
    st.set_page_config().
    """

    st.header(
        "📝 Technician Assessment"
    )

    st.write(
        "OEM-grounded marine technician "
        "knowledge and practical assessment."
    )

    assessment = load_json(
        ASSESSMENT_FILE
    )

    evidence = load_json(
        EVIDENCE_FILE
    )

    if assessment is None:

        st.error(
            "assessment_answer.json was not found."
        )

        st.info(
            "Make sure assessment_answer.json "
            "exists in the repository."
        )

        return

    questions = get_questions(
        assessment
    )

    if not questions:

        st.error(
            "No QUESTIONS were found in "
            "assessment_answer.json."
        )

        return

    answer_key = get_answer_key(
        assessment
    )

    metadata = extract_metadata(
        assessment
    )

    col1, col2, col3, col4 = st.columns(
        4
    )

    with col1:
        st.metric(
            "Manufacturer",
            metadata["manufacturer"],
        )

    with col2:
        st.metric(
            "Engine",
            metadata["engine"],
        )

    with col3:
        st.metric(
            "Vessel",
            metadata["vessel"],
        )

    with col4:
        st.metric(
            "Questions",
            len(questions),
        )

    st.info(
        f"**Training Topic:** "
        f"{metadata['topic']}  |  "
        f"**Passing Score:** "
        f"{metadata['passing_score']:.0f}%"
    )

    if "assessment_started" not in st.session_state:
        st.session_state.assessment_started = False

    if "assessment_submitted" not in st.session_state:
        st.session_state.assessment_submitted = False

    if not st.session_state.assessment_started:

        st.markdown(
            "### Ready to Start"
        )

        st.write(
            "This assessment evaluates technician "
            "knowledge of engine fundamentals, "
            "systems, components, safety, "
            "maintenance, inspection, installation "
            "and troubleshooting."
        )

        if st.button(
            "▶ Start Assessment",
            type="primary",
            use_container_width=True,
        ):
            st.session_state.assessment_started = True
            st.session_state.assessment_submitted = False

            st.rerun()

        return

    st.markdown(
        "### Assessment Questions"
    )

    answers = {}

    for number, question in enumerate(
        questions,
        start=1,
    ):

        st.markdown(
            f"#### {number}. "
            f"{get_question_text(question, number)}"
        )

        st.caption(
            f"Assessment Area: "
            f"{get_question_area(question)}"
        )

        qtype = get_question_type(
            question
        )

        widget_key = (
            f"marinewise_question_{number}"
        )

        if qtype in {
            "MULTIPLE_CHOICE",
            "MCQ",
            "MULTI_CHOICE",
        }:

            options = get_options(
                question
            )

            if options:

                answers[number] = st.radio(
                    "Select one answer:",
                    options,
                    key=widget_key,
                )

            else:

                answers[number] = st.text_input(
                    "Your answer:",
                    key=widget_key,
                )

        elif qtype in {
            "TRUE_FALSE",
            "TRUEFALSE",
            "TRUE_OR_FALSE",
        }:

            answers[number] = st.radio(
                "Select one answer:",
                [
                    "True",
                    "False",
                ],
                key=widget_key,
            )

        else:

            answers[number] = st.text_area(
                "Your answer:",
                key=widget_key,
                height=140,
            )

        citation = get_question_citation(
            question
        )

        if citation:

            st.caption(
                f"OEM Reference: {citation}"
            )

        st.markdown("---")

    if st.button(
        "Submit Assessment",
        type="primary",
        use_container_width=True,
    ):

        st.session_state.assessment_answers = (
            answers
        )

        st.session_state.assessment_submitted = True

        st.rerun()

    if not st.session_state.assessment_submitted:
        return

    submitted_answers = (
        st.session_state.get(
            "assessment_answers",
            {},
        )
    )

    result = calculate_result(
        questions,
        submitted_answers,
        answer_key,
        metadata["passing_score"],
    )

    st.markdown(
        "## 📊 Assessment Result"
    )

    result_col1, result_col2, result_col3 = (
        st.columns(3)
    )

    with result_col1:
        st.metric(
            "Score",
            f"{result['score_percent']:.1f}%",
        )

    with result_col2:
        st.metric(
            "Correct",
            (
                f"{result['correct_answers']} / "
                f"{result['total_questions']}"
            ),
        )

    with result_col3:
        st.metric(
            "Unanswered",
            result["unanswered"],
        )

    if result["passed"]:

        st.success(
            "PASS — Passing score achieved."
        )

    else:

        st.warning(
            "RETRAINING REQUIRED — "
            "Passing score not achieved."
        )

    st.markdown(
        "### Area Performance"
    )

    for area, score in result[
        "area_scores"
    ].items():

        st.write(
            f"**{area}: {score:.1f}%**"
        )

        st.progress(
            min(
                max(
                    score / 100,
                    0.0,
                ),
                1.0,
            )
        )

    st.markdown(
        "### Weak Areas"
    )

    if result["weak_areas"]:

        for item in result[
            "weak_areas"
        ]:

            st.warning(
                f"**{item['area']}** — "
                f"{item['score_percent']:.1f}% — "
                f"{item['priority']} priority"
            )

    else:

        st.success(
            "No weak assessment areas identified."
        )

    st.markdown(
        "### Personalized Retraining Recommendations"
    )

    recommendations = result[
        "retraining_recommendations"
    ]

    if recommendations:

        for item in recommendations:

            st.info(
                f"**{item['area']}** "
                f"({item['priority']}): "
                f"{item['recommendation']}"
            )

    else:

        st.success(
            "No additional retraining recommendation "
            "was generated."
        )

    st.markdown(
        "### OEM Evidence"
    )

    render_oem_evidence(
        evidence
    )

    st.markdown("---")

    if st.button(
        "🔄 Retake Assessment",
        use_container_width=True,
    ):

        keys_to_delete = [
            key
            for key in st.session_state.keys()
            if key.startswith(
                "marinewise_question_"
            )
        ]

        for key in keys_to_delete:
            del st.session_state[key]

        st.session_state.assessment_started = False
        st.session_state.assessment_submitted = False

        if "assessment_answers" in st.session_state:
            del st.session_state.assessment_answers

        st.rerun()

    st.caption(
        "MarineWise AI | OEM-grounded assessment "
        "and technician retraining"
    )
