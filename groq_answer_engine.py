from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from groq import Groq


INPUT_FILE = Path("reranked_evidence.json")
OUTPUT_FILE = Path("groq_answer.json")

MODEL = "openai/gpt-oss-120b"

TEST_QUERY = (
    "QL-40 MAN 16V175D-MM main engine "
    "high exhaust temperature alarm"
)


SYSTEM_PROMPT = """
You are MarineWise AI, an evidence-grounded marine
engine troubleshooting assistant.

You assist qualified marine engineers and technicians.

CRITICAL RULE:
Use ONLY the supplied OEM evidence.

Do NOT invent:
- troubleshooting steps
- causes
- alarm meanings
- part numbers
- torque values
- pressure values
- temperature limits
- clearances
- procedures
- specifications

If the supplied evidence does not contain enough information,
clearly state:

"Insufficient OEM evidence available for a reliable conclusion."

Do not fill missing information from general knowledge.

When evidence supports a statement, cite the source filename
and page number provided with the evidence.

Separate:
1. What the OEM evidence states
2. What should be checked
3. What corrective action is supported

Do not present assumptions as OEM instructions.

Return a practical engineering response using this structure:

PROBLEM IDENTIFICATION
RELEVANT OEM EVIDENCE
PROBABLE CAUSES
TROUBLESHOOTING STEPS
CORRECTIVE ACTION
OEM REFERENCES
EVIDENCE STATUS
SAFETY NOTE

For every important technical claim, include an OEM reference
such as:

[OEM: filename, Page X]

If evidence is insufficient for a section, write:
"Not established from supplied OEM evidence."

Keep the answer concise but technically useful.
"""


def load_evidence() -> list[dict[str, Any]]:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Missing required file: {INPUT_FILE}"
        )

    with INPUT_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:
        data = json.load(file)

    results = data.get("results", [])

    if not results:
        raise ValueError(
            "No reranked OEM evidence found."
        )

    return results


def build_evidence_context(
    results: list[dict[str, Any]]
) -> str:

    sections = []

    for item in results:

        source = item.get(
            "source_file",
            "Unknown source"
        )

        page = item.get(
            "page",
            "Unknown page"
        )

        vessel = item.get(
            "vessel",
            "Unknown"
        )

        engine = item.get(
            "engine_model",
            "Unknown"
        )

        text = str(
            item.get("text", "")
        ).strip()

        rank = item.get(
            "evidence_rank",
            "?"
        )

        score = item.get(
            "rerank_score",
            0
        )

        section = f"""
EVIDENCE {rank}

Source: {source}
Page: {page}
Vessel: {vessel}
Engine: {engine}
Evidence score: {score}

OEM TEXT:
{text}
"""

        sections.append(section)

    return "\n".join(sections)


def extract_answer_text(response: Any) -> str:

    if not response.choices:
        raise RuntimeError(
            "Groq returned no choices."
        )

    message = response.choices[0].message

    content = message.content

    if not content:
        raise RuntimeError(
            "Groq returned an empty answer."
        )

    return content.strip()


def main() -> None:

    print("=" * 70)
    print("MARINEWISE AI - STEP 26")
    print("GROQ EVIDENCE-BASED ANSWER ENGINE")
    print("=" * 70)

    print()
    print("Test query:")
    print(TEST_QUERY)

    print()
    print("Loading reranked OEM evidence...")

    evidence = load_evidence()

    print(
        f"GREEN - evidence records loaded: "
        f"{len(evidence)}"
    )

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY environment variable is not configured."
        )

    print(
        "GREEN - GROQ_API_KEY detected."
    )

    print()
    print("Building OEM evidence context...")

    evidence_context = build_evidence_context(
        evidence
    )

    if not evidence_context.strip():
        raise RuntimeError(
            "OEM evidence context is empty."
        )

    print(
        "GREEN - OEM evidence context created."
    )

    user_prompt = f"""
USER QUERY:

{TEST_QUERY}

SUPPLIED OEM EVIDENCE:

{evidence_context}

TASK:

Answer the user's query using ONLY the supplied OEM evidence.

Every important technical claim must include its source
filename and page number.

If the evidence does not establish a cause or procedure,
say that it is not established from the supplied OEM evidence.

Do not use outside knowledge.
"""

    print()
    print("Calling Groq...")
    print(
        f"Model: {MODEL}"
    )

    client = Groq(
        api_key=api_key
    )

    response = client.chat.completions.create(
        model=MODEL,
        temperature=0.1,
        max_completion_tokens=1800,
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

    answer = extract_answer_text(
        response
    )

    print(
        "GREEN - Groq response received."
    )

    output = {
        "query": TEST_QUERY,
        "model": MODEL,
        "evidence_count": len(evidence),
        "evidence_sources": [
            {
                "rank": item.get(
                    "evidence_rank"
                ),
                "source_file": item.get(
                    "source_file"
                ),
                "page": item.get(
                    "page"
                ),
                "rerank_score": item.get(
                    "rerank_score"
                ),
            }
            for item in evidence
        ],
        "answer": answer,
    }

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            output,
            file,
            indent=2,
            ensure_ascii=False
        )

    print()
    print("=" * 70)
    print("MARINEWISE AI ANSWER")
    print("=" * 70)
    print()
    print(answer)

    print()
    print("=" * 70)
    print("STEP 26 VERIFICATION")
    print("=" * 70)

    assert answer.strip()

    print(
        "GREEN - non-empty Groq answer verified."
    )

    assert OUTPUT_FILE.exists()

    print(
        "GREEN - groq_answer.json created."
    )

    assert len(evidence) > 0

    print(
        "GREEN - OEM evidence attached to answer."
    )

    print()
    print("STEP 26: SUCCESS")
    print("GREEN")


if __name__ == "__main__":
    main()
