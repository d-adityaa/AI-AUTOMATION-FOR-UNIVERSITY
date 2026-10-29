"""Smart University Automation System — Streamlit entry point."""

from __future__ import annotations

import streamlit as st

from services.database import initialize_database
from utils.ui import init_session_state, render_sidebar

st.set_page_config(
    page_title="Smart University Automation System",
    page_icon=":material/school:",
    layout="wide",
    initial_sidebar_state="expanded",
)

initialize_database(seed=True)
init_session_state()

pages = [
    st.Page("app_pages/dashboard.py", title="Dashboard", icon=":material/space_dashboard:", default=True),
    st.Page("app_pages/students.py", title="Students", icon=":material/groups:"),
    st.Page("app_pages/attendance.py", title="Attendance", icon=":material/fact_check:"),
    st.Page("app_pages/assignments.py", title="Assignments", icon=":material/assignment:"),
    st.Page("app_pages/notices.py", title="Notices", icon=":material/campaign:"),
    st.Page("app_pages/timetable.py", title="Timetable", icon=":material/calendar_month:"),
    st.Page("app_pages/ai_assistant.py", title="AI assistant", icon=":material/smart_toy:"),
    st.Page("app_pages/settings.py", title="Settings", icon=":material/settings:"),
]

page = st.navigation(pages, position="sidebar")
render_sidebar()
page.run()
