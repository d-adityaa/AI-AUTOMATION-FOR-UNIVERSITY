"""AI configuration, live connection test, and local database information."""

from __future__ import annotations

import streamlit as st

from services.ai_assistant import test_ai_connection
from services.database import database_counts, get_setting, set_setting
from services.student_service import count_students
from utils.config import (
    DEFAULT_AI_MODEL,
    SUPPORTED_AI_MODELS,
    ai_is_configured,
    get_db_path,
)
from utils.ui import is_faculty, page_header, set_flash

page_header(
    "Settings",
    "Configure optional Gemini features and inspect this local demonstration database.",
    ":material/settings:",
)

if not is_faculty():
    st.info(
        "Settings changes are hidden in the Student demo role. This is a demonstration control, "
        "not real authorization or security.",
        icon=":material/lock:",
    )

ai_tab, data_tab, about_tab = st.tabs(["AI assistant", "Local data", "About & limitations"])

with ai_tab:
    configured = ai_is_configured()
    current_model = get_setting("ai_model", DEFAULT_AI_MODEL) or DEFAULT_AI_MODEL
    if current_model not in SUPPORTED_AI_MODELS:
        current_model = DEFAULT_AI_MODEL

    with st.container(border=True):
        st.subheader("Google Gemini", icon=":material/auto_awesome:")
        st.markdown(f"**API key:** {'detected' if configured else 'not configured'}")
        st.caption(
            "The key is read from GEMINI_API_KEY or Streamlit secrets. "
            "It is never displayed, logged, or written to the database."
        )
        st.markdown(f"**Provider:** Google Gemini · **Default model:** {DEFAULT_AI_MODEL}")
        st.markdown(
            "AI usage is optional. Core attendance, assignment, notice, timetable, reminder, "
            "and database-query features work without any API key."
        )
        if configured:
            st.success("Gemini is configured for optional phrasing and notice summaries.")
        else:
            st.warning(
                "Database-only mode is active. Set GEMINI_API_KEY in `.env` or add it to "
                "`.streamlit/secrets.toml` to enable AI features.",
                icon=":material/key_off:",
            )

    st.subheader("Model selection", icon=":material/model_training:")
    selected_model = st.selectbox(
        "Supported Gemini model",
        options=list(SUPPORTED_AI_MODELS),
        index=list(SUPPORTED_AI_MODELS).index(current_model),
        help="Only this allowlisted set is accepted by the application.",
        disabled=not is_faculty(),
    )
    if is_faculty():
        if st.button("Save model setting", icon=":material/save:", type="primary"):
            try:
                set_setting("ai_model", selected_model)
            except Exception as exc:
                st.error(str(exc), icon=":material/error:")
            else:
                st.session_state.pop("ai_connection_test", None)
                set_flash(f"AI model saved as {selected_model}.")
                st.rerun()

    st.subheader("Live connection test", icon=":material/network_check:")
    st.caption(
        "This sends one tiny live request ('Reply with OK') to the selected model. "
        "It can fail because of an invalid key, quota, model availability, or network restrictions. "
        "Results are reported honestly and no fake success is shown."
    )
    test_result = st.session_state.get("ai_connection_test")
    if configured and is_faculty():
        if st.button(
            "Test Gemini connection",
            icon=":material/network_check:",
            key="test_gemini_connection",
        ):
            with st.spinner("Sending a short live request to Gemini…"):
                success, message = test_ai_connection(model=selected_model)
            test_result = {
                "success": success,
                "message": message,
                "model": selected_model,
            }
            st.session_state.ai_connection_test = test_result
        if test_result and test_result.get("model") == selected_model:
            if test_result["success"]:
                st.success(test_result["message"], icon=":material/check_circle:")
            else:
                st.error(test_result["message"], icon=":material/error:")
            st.caption("Only an observed successful response is reported as success.")
    elif not configured:
        st.caption("Connection testing is unavailable until an API key is configured.")
    elif not is_faculty():
        st.caption("Switch to the Faculty demo role to run a live connection test.")

    with st.expander("Configuration instructions", icon=":material/help:"):
        st.markdown(
            "**Option 1: `.env` in the project root**\n\n"
            "```text\nGEMINI_API_KEY=your_key_here\n```\n\n"
            "**Option 2: `.streamlit/secrets.toml`**\n\n"
            "```toml\nGEMINI_API_KEY = \"your_key_here\"\n```\n\n"
            "Do not commit either file. Restart Streamlit after adding a key. "
            "Free-tier quotas can be small and may reset on the provider's schedule; "
            "the app reports quota errors instead of hiding them."
        )

with data_tab:
    db_path = get_db_path()
    counts = database_counts()
    active_students = count_students(active_only=True)
    total_students = count_students(active_only=False)
    st.subheader("Local SQLite database", icon=":material/database:")
    st.caption("Every operational record in this project is fictional demonstration data.")
    with st.container(border=True):
        st.markdown("**Database path**")
        st.code(str(db_path), language=None)
        try:
            size_kb = db_path.stat().st_size / 1024
            st.caption(f"File size: {size_kb:.1f} KB (WAL sidecar files may also exist).")
        except OSError:
            st.caption("The database file was not found at the configured path.")

    metric_columns = st.columns(4)
    metric_columns[0].metric("Active students", active_students, border=True)
    metric_columns[1].metric(
        "Total students",
        total_students,
        delta=total_students - active_students,
        delta_color="off",
        border=True,
    )
    metric_columns[2].metric("Attendance records", counts.get("attendance", 0), border=True)
    metric_columns[3].metric("Assignments", counts.get("assignments", 0), border=True)

    st.dataframe(
        [
            {"Table": table.replace("_", " ").title(), "Rows": count}
            for table, count in counts.items()
        ],
        hide_index=True,
        width="stretch",
        alt="Row counts for each local SQLite demonstration table",
    )
    st.caption(
        "Reminder rows are generated inside the app and deduplicated per day. "
        "No email, SMS, WhatsApp, or push notification is sent."
    )
    with st.expander("Change the database path", icon=":material/folder:"):
        st.markdown(
            "Set `SMART_UNI_DB_PATH` in `.env` before starting the app. "
            "This is useful for isolated tests or classroom demonstrations. "
            "The app creates the parent folder and schema automatically."
        )

with about_tab:
    st.subheader("About this project", icon=":material/info:")
    st.markdown(
        "**Smart University Automation System**  \n"
        "A local Streamlit and SQLite college workflow demonstration. "
        "It manages demo students, attendance, assignments, notices, timetables, and in-app reminders."
    )
    st.subheader("Honest limitations", icon=":material/warning:")
    st.markdown(
        "- There is no real authentication or authorization; the Faculty/Student role selector is a demo control.\n"
        "- All students, notices, assignments, and timetable entries are fictional.\n"
        "- Assignment submission only records a database flag and timestamp; no file upload exists.\n"
        "- Reminders are displayed only inside the app; no external messaging is implemented.\n"
        "- AI is optional, uses allowlisted read-only tools, and can still produce inaccurate phrasing.\n"
        "- No generated SQL, Python, shell commands, eval, or exec is executed.\n"
        "- The local database is suitable for a classroom prototype, not production deployment."
    )
    st.subheader("Privacy", icon=":material/privacy_tip:")
    st.markdown(
        "The Gemini API key is read from environment variables or Streamlit secrets and is never "
        "rendered in the UI. Questions and retrieved database context are sent to Gemini only when "
        "AI phrasing is enabled and only after you ask a question or request a notice summary. "
        "Use fictional data only."
    )
