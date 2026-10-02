import streamlit as st

from ai_engine import show_ai_test
from config import show_api_status
from assessment_dashboard import show_assessment


def show_header():
    """Display the MARINEWISE AI header."""
    st.title("⚓ MARINEWISE AI")
    st.subheader("From OEM Knowledge to Skilled Technicians.")

    st.write(
        "AI-Powered Marine Workshop Knowledge, "
        "Training & Assessment Platform"
    )


def show_status():
    """Display the current application status."""
    st.success("MARINEWISE AI is running.")
    st.info("Knowledge Base: Not indexed yet")


def main():
    """Run the MARINEWISE AI Streamlit application."""

    st.set_page_config(
        page_title="MARINEWISE AI",
        page_icon="⚓",
        layout="wide",
    )

    show_header()
    show_status()
    show_api_status()
    show_ai_test()

    st.markdown("---")

    st.header("📝 Technician Assessment")

    st.write(
        "Test technician knowledge using the "
        "OEM-grounded MarineWise assessment."
    )

    show_assessment()


if __name__ == "__main__":
    main()
