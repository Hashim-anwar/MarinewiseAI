import streamlit as st
from groq import Groq

from config import get_api_key


def get_groq_client() -> Groq | None:
    """Create a Groq client when an API key is available."""
    api_key = get_api_key("GROQ_API_KEY")

    if not api_key:
        return None

    return Groq(api_key=api_key)


def ask_groq(question: str) -> str:
    """Send a question to Groq and return the AI response."""
    client = get_groq_client()

    if client is None:
        return "Groq API key is not configured."

    response = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": question,
            }
        ],
        model="openai/gpt-oss-120b",
    )

    return response.choices[0].message.content


def show_ai_test() -> None:
    """Display a simple Groq connection test."""
    st.subheader("🤖 AI Connection Test")

    question = st.text_input(
        "Ask MARINEWISE AI a simple question:"
    )

    if st.button("Ask AI"):
        if not question:
            st.warning("Please enter a question.")
            return

        with st.spinner("AI is thinking..."):
            answer = ask_groq(question)

        st.write(answer)
