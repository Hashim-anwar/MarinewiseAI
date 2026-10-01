import os
import streamlit as st


def get_api_key(name: str) -> str:
    """Get an API key from Streamlit secrets or environment variables."""
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""

    if value:
        return value

    return os.getenv(name, "")


def show_api_status() -> None:
    """Show which AI API keys are configured."""
    groq_key = get_api_key("GROQ_API_KEY")
    tavily_key = get_api_key("TAVILY_API_KEY")
    gemini_key = get_api_key("GEMINI_API_KEY")

    st.sidebar.subheader("🔐 API Status")

    st.sidebar.write(
        "Groq: " + ("✅ Ready" if groq_key else "⚪ Not configured")
    )

    st.sidebar.write(
        "Tavily: " + ("✅ Ready" if tavily_key else "⚪ Not configured")
    )

    st.sidebar.write(
        "Gemini: " + ("✅ Ready" if gemini_key else "⚪ Not configured")
    )
