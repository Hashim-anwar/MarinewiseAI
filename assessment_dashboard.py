import json
from pathlib import Path

import streamlit as st


ASSESSMENT_FILE = Path("assessment_answer.json")
EVIDENCE_FILE = Path("assessment_evidence.json")


st.set_page_config(
    page_title="MarineWise AI Assessment",
    page_icon="⚓",
    layout="wide",
)


def load_json(path: Path):
    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def find_recursive(data, target_keys):
    """Find the first matching key recursively."""
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


def normalize_questions(value):
    """Convert common question structures into a list."""
    if isinstance(value, list):
        return [q for q in value if isinstance(q, dict)]

    if isinstance(value, dict):
        for key in (
            "questions",
            "QUESTIONS",
            "items",
            "question_list",
            "assessment_questions",
        ):
            nested = value.get(key)
            if isinstance(nested, list):
                return [q for q in nested if isinstance(q, dict)]

    return []


def get_questions(assessment):
    value = find_recursive(
        assessment,
        {
            "QUESTIONS",
            "QUESTION",
            "ASSESSMENT QUESTIONS",
        },
    )

    return normalize_questions(value)


def get_assessment_section(assessment, section_name):
    value = find_recursive(
        assessment,
        {
            section_name.upper(),
        },
    )

    if isinstance(value, dict):
        return value

    return {}


def get_question_text(question, number):
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
    for key in (
        "type",
        "question_type",
        "assessment_type",
        "format",
    ):
        value = question.get(key)

        if isinstance(value, str):
            return value.upper().replace("-", "_").replace(" ", "_")

    return "MULTIPLE_CHOICE"


def get_question_area(question):
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
    options = question.get("options")

    if isinstance(options, dict):
        return [
            f"{key}. {value}"
            for key, value in options.items()
        ]

    if isinstance(options, list):
        result = []

        for item in options:
            if isinstance(item, dict):
                letter = (
                    item.get("letter")
                    or item.get("key")
                    or item.get("option")
                    or ""
                )
                text = (
                    item.get("text")
                    or item.get("value")
                    or item.get("answer")
                    or ""
                )

                if letter:
                    result.append(f"{letter}. {text}")
                else:
                    result.append(str(text))

            else:
                result.append(str(item))

        return result

    return []


def get_citation(question):
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


def get_evidence_records(evidence):
    if not isinstance(evidence, dict):
        return []

    records = evidence.get("evidence")

    if isinstance(records, list):
        return [
            item for item in records
            if isinstance(item, dict)
        ]

    return []


def render_question(question, number):
    qtype = get_question_type(question)
    text = get_question_text(question, number)
    area = get_question_area(question)

    st.markdown(
        f"### {number}. {text}"
    )

    st.caption(
        f"Area: {area}  |  Type: {qtype.replace('_', ' ').title()}"
    )

    widget_key = f"answer_{number}"

    if qtype in {
        "MULTIPLE_CHOICE",
        "MCQ",
        "MULTI_CHOICE",
    }:
        options = get_options(question)

        if options:
            return st.radio(
                "Select one answer:",
                options,
                key=widget_key,
            )

        return st.text_input(
            "Your answer:",
            key=widget_key,
        )

    if qtype in {
        "TRUE_FALSE",
        "TRUEFALSE",
        "TRUE_OR_FALSE",
    }:
        return st.radio(
            "Select your answer:",
            ["True", "False"],
            key=widget_key,
        )

    if qtype in {
        "SHORT_ANSWER",
        "SHORTANSWER",
    }:
        return st.text_area(
            "Your answer:",
            key=widget_key,
            height=120,
        )

    if qtype in {
        "PRACTICAL_SCENARIO",
        "PRACTICAL",
        "SCENARIO",
    }:
        return st.text_area(
            "Describe your response / procedure:",
            key=widget_key,
            height=180,
        )

    return st.text_area(
        "Your answer:",
        key=widget_key,
        height=120,
    )


def calculate_demo_score(questions, answers):
    """
    Basic local score calculation.

    This is intentionally conservative.
    The authoritative detailed scoring remains assessment_scoring.py.
    """

    answer_key = find_recursive(
        st.session_state.get("assessment_data", {}),
        {
            "ANSWER KEY",
            "ANSWER_KEY",
            "ANSWERKEY",
        },
    )

    if not isinstance(answer_key, (dict, list)):
        return None

    key_map = {}

    if isinstance(answer_key, dict):
        for key, value in answer_key.items():
            key_map[str(key)] = value

    elif isinstance(answer_key, list):
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
                key_map[str(number)] = answer

    if not key_map:
        return None

    correct = 0
    attempted = 0

    for number, user_answer in answers.items():
        if user_answer in (None, ""):
            continue

        attempted += 1

        expected = key_map.get(str(number))

        if expected is None:
            continue

        user_text = str(user_answer).strip().lower()
        expected_text = str(expected).strip().lower()

        if user_text == expected_text:
            correct += 1

    if not questions:
        return None

    return {
        "correct": correct,
        "attempted": attempted,
        "total": len(questions),
        "percentage": round(
            (correct / len(questions)) * 100,
            1,
        ),
    }


def show_evidence(evidence):
    records = get_evidence_records(evidence)

    if not records:
        st.info(
            "No assessment evidence records are available "
            "for display."
        )
        return

    for index, record in enumerate(records[:20], start=1):
        citation = record.get("citation", "")
        source_file = record.get("source_file", "")
        page = record.get("page", "")
        text = record.get("evidence_text", "")

        with st.expander(
            f"OEM Evidence {index}: {citation or source_file}"
        ):
            if source_file:
                st.write(f"**Source:** {source_file}")

            if page:
                st.write(f"**Page:** {page}")

            if citation:
                st.write(f"**Citation:** {citation}")

            if text:
                st.write(text)


def main():
    st.title("⚓ MarineWise AI Assessment")
    st.subheader("Marine Technician Knowledge & Practical Assessment")

    assessment = load_json(ASSESSMENT_FILE)
    evidence = load_json(EVIDENCE_FILE)

    if assessment is None:
        st.error(
            "assessment_answer.json was not found or could not be read."
        )

        st.info(
            "Place assessment_answer.json in the same folder "
            "as assessment_dashboard.py."
        )

        return

    st.session_state["assessment_data"] = assessment

    questions = get_questions(assessment)

    if not questions:
        st.error(
            "No assessment QUESTIONS were found in "
            "assessment_answer.json."
        )

        st.write(
            "The dashboard searches the assessment JSON recursively, "
            "so nested QUESTIONS sections are supported."
        )

        return

    overview = get_assessment_section(
        assessment,
        "ASSESSMENT OVERVIEW",
    )

    scoring = get_assessment_section(
        assessment,
        "SCORING GUIDE",
    )

    metadata = assessment.get("input", {})

    if not isinstance(metadata, dict):
        metadata = {}

    manufacturer = (
        metadata.get("manufacturer")
        or assessment.get("manufacturer")
        or "Not specified"
    )

    engine = (
        metadata.get("engine_model")
        or assessment.get("engine_model")
        or "Not specified"
    )

    vessel = (
        metadata.get("vessel")
        or assessment.get("vessel")
        or "Not specified"
    )

    topic = (
        metadata.get("topic")
        or assessment.get("topic")
        or "Marine Engine Training"
    )

    passing_score = (
        metadata.get("passing_score")
        or assessment.get("passing_score")
        or 70
    )

    st.markdown("---")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Manufacturer", manufacturer)

    with col2:
        st.metric("Engine", engine)

    with col3:
        st.metric("Vessel", vessel)

    with col4:
        st.metric(
            "Questions",
            len(questions),
        )

    st.info(
        f"**Training Topic:** {topic}  |  "
        f"**Passing Score:** {passing_score}%"
    )

    if overview:
        description = (
            overview.get("description")
            or overview.get("purpose")
            or overview.get("assessment_purpose")
        )

        if description:
            st.markdown("### Assessment Overview")
            st.write(description)

    st.markdown("---")

    if "assessment_started" not in st.session_state:
        st.session_state["assessment_started"] = False

    if not st.session_state["assessment_started"]:
        st.markdown("## Ready to Start")

        st.write(
            "This assessment evaluates the technician's knowledge "
            "of the engine, systems, components, safety, maintenance, "
            "inspection, installation and troubleshooting."
        )

        if st.button(
            "▶ Start Assessment",
            type="primary",
            use_container_width=True,
        ):
            st.session_state["assessment_started"] = True
            st.session_state["assessment_submitted"] = False
            st.rerun()

        return

    st.markdown("## Assessment Questions")

    answers = {}

    for index, question in enumerate(questions, start=1):
        answers[index] = render_question(
            question,
            index,
        )

        st.markdown("---")

    st.session_state["current_answers"] = answers

    if st.button(
        "Submit Assessment",
        type="primary",
        use_container_width=True,
    ):
        st.session_state["assessment_submitted"] = True

    if not st.session_state.get(
        "assessment_submitted",
        False,
    ):
        return

    st.markdown("## Assessment Submitted")

    result = calculate_demo_score(
        questions,
        answers,
    )

    if result is None:
        st.warning(
            "Answers have been collected. "
            "Use the MarineWise scoring engine "
            "(`assessment_scoring.py`) for the authoritative "
            "score and retraining analysis."
        )

        st.json(
            {
                "answers_submitted": len(answers),
                "questions": len(questions),
                "scoring_engine": "assessment_scoring.py",
            }
        )

    else:
        st.markdown("## Assessment Result")

        result_col1, result_col2, result_col3 = st.columns(3)

        with result_col1:
            st.metric(
                "Score",
                f"{result['percentage']}%",
            )

        with result_col2:
            st.metric(
                "Correct",
                f"{result['correct']} / {result['total']}",
            )

        with result_col3:
            st.metric(
                "Attempted",
                result["attempted"],
            )

        if result["percentage"] >= float(passing_score):
            st.success(
                "PASS — The trainee has reached the configured "
                "passing score."
            )
        else:
            st.warning(
                "RETRAINING REQUIRED — The trainee has not reached "
                "the configured passing score."
            )

    st.markdown("---")

    st.markdown("## OEM Evidence Used for Assessment")

    show_evidence(evidence)

    st.markdown("---")

    st.markdown("## Next Step: Retraining Intelligence")

    st.write(
        "The detailed MarineWise scoring engine identifies weak "
        "assessment areas and generates targeted retraining "
        "recommendations from the assessment result."
    )

    if st.button(
        "Prepare for Reassessment",
        use_container_width=True,
    ):
        st.info(
            "Complete the recommended retraining, then run the "
            "assessment again."
        )

    st.markdown("---")

    st.caption(
        "MarineWise AI | OEM-grounded marine technician assessment"
    )


if __name__ == "__main__":
    main()
