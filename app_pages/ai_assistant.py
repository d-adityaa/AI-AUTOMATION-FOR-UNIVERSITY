"""Database-grounded assistant chat with optional Gemini phrasing."""

from __future__ import annotations

from typing import Any

import streamlit as st

from services.ai_assistant import answer_question
from services.database import get_setting
from utils.config import DEFAULT_AI_MODEL, ai_is_configured
from utils.ui import get_selected_student, is_faculty, page_header

page_header(
    "AI assistant",
    "Ask about this app's stored demo data. Every answer is grounded in allowlisted database queries.",
    ":material/smart_toy:",
)

student = get_selected_student()
configured = ai_is_configured()
model = get_setting("ai_model", DEFAULT_AI_MODEL) or DEFAULT_AI_MODEL
messages: list[dict[str, Any]] = st.session_state.setdefault("ai_messages", [])

status_columns = st.columns([1, 1, 1])
with status_columns[0]:
    with st.container(border=True):
        st.markdown("**AI mode**")
        st.markdown("Gemini configured" if configured else "Database-only mode")
        st.caption(
            "AI can phrase grounded results when a key is configured. "
            "Without it, answers still come from SQLite."
        )
with status_columns[1]:
    with st.container(border=True):
        st.markdown("**Selected model**")
        st.markdown(model)
        st.caption("Change the model in Settings.")
with status_columns[2]:
    with st.container(border=True):
        st.markdown("**Student context**")
        if student:
            st.markdown(f"{student['student_id']} — {student['name']}")
            st.caption(f"Semester {student['semester']} · Demo context selected in the sidebar.")
        else:
            st.markdown("No active student selected")
            st.caption("Assignment questions can still be answered by semester.")

if configured:
    st.success(
        "Gemini is configured. Answers first query the local database, then Gemini may rephrase "
        "those results. Provider calls are never made without a question.",
        icon=":material/auto_awesome:",
    )
else:
    st.info(
        "No Gemini API key is configured. The assistant is fully usable in database-only mode: "
        "it routes your question to stored attendance, assignments, timetable, or notices. "
        "Set GEMINI_API_KEY or Streamlit secrets to enable AI phrasing and notice summaries.",
        icon=":material/database:",
    )
st.caption(
    "Safety boundary: no generated SQL, Python, shell commands, eval, or exec. "
    "The allowlisted tools are read-only, and the app never claims that external notifications were sent."
)

suggestions = [
    "What assignments are due this week?",
    "Show overdue assignments.",
    "What is today's timetable?",
    "Show the latest examination notice.",
    "What is the attendance percentage for STU001?",
]
st.markdown("**Try a suggested question**")
suggestion_columns = st.columns(len(suggestions))
suggested_question: str | None = None
for index, suggestion in enumerate(suggestions):
    with suggestion_columns[index]:
        if st.button(
            suggestion,
            key=f"ai_suggestion_{index}",
            width="stretch",
        ):
            suggested_question = suggestion

if messages:
    if st.button("Clear chat history", icon=":material/delete_sweep:", key="ai_clear_chat"):
        st.session_state.ai_messages = []
        st.rerun()

for message in messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        meta = message.get("meta")
        if meta:
            mode_text = {
                "ai": "Gemini phrasing of database results",
                "database": "Database-only answer",
                "ai_failed": "AI request failed; database fallback shown",
                "error": "Request error",
            }.get(meta.get("mode"), "Database-grounded response")
            st.caption(
                f"{mode_text} · Tool: {meta.get('tool') or 'none'}"
                + (f" · Error: {meta['error']}" if meta.get("error") else "")
            )
            records = meta.get("records") or []
            if records:
                with st.expander("Show database evidence", icon=":material/database:"):
                    st.json(records, expanded=False)
                    st.caption(
                        "These are the read-only local database records used to ground the answer."
                    )


def ask(question: str) -> None:
    messages.append({"role": "user", "content": question})
    try:
        result = answer_question(
            question,
            student_db_id=student["id"] if student else None,
            role="Faculty" if is_faculty() else "Student",
        )
    except Exception as exc:
        messages.append(
            {
                "role": "assistant",
                "content": (
                    "The assistant could not process that request. "
                    "No answer was generated, and no external action was taken."
                ),
                "meta": {
                    "mode": "error",
                    "tool": None,
                    "records": [],
                    "error": str(exc),
                },
            }
        )
    else:
        messages.append(
            {
                "role": "assistant",
                "content": result["answer"],
                "meta": {
                    "mode": result["mode"],
                    "tool": result["tool"],
                    "records": result["records"],
                    "error": result["error"],
                },
            }
        )


if suggested_question:
    with st.spinner("Querying the local database…"):
        ask(suggested_question)
    st.rerun()

prompt = st.chat_input(
    "Ask about assignments, attendance, the timetable, or notices…",
    key="ai_chat_input",
)
if prompt:
    with st.spinner("Querying the local database…"):
        ask(prompt)
    st.rerun()
