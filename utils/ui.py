"""Shared Streamlit UI helpers and demonstration-role state."""

from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st

from services.student_service import get_student, list_students
from utils.config import DEMO_DATA_LABEL, ai_is_configured

DEMO_ROLES = ("Faculty", "Student")


def init_session_state() -> None:
    st.session_state.setdefault("demo_role", "Faculty")
    st.session_state.setdefault("demo_student_id", None)
    st.session_state.setdefault("ai_messages", [])
    st.session_state.setdefault("_flash", None)


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("#### Demo workspace")
        role_options = list(DEMO_ROLES)
        role = st.segmented_control(
            "Demo role",
            role_options,
            key="demo_role",
            help="This role selector is a demonstration control, not authentication.",
        )
        if role is None:
            st.session_state.demo_role = "Faculty"

        active_students = list_students()
        student_ids = [student["id"] for student in active_students]
        labels = {
            student["id"]: f"{student['student_id']} — {student['name']}" for student in active_students
        }
        if student_ids:
            if st.session_state.get("demo_student_id") not in student_ids:
                st.session_state.demo_student_id = student_ids[0]
            st.selectbox(
                "Demo student context",
                options=student_ids,
                format_func=lambda student_id: labels.get(student_id, str(student_id)),
                key="demo_student_id",
                help="Used for assignment status, attendance details, and student-facing actions.",
            )
        else:
            st.warning("No active demo students are available.")

        st.caption(
            "Demonstration roles only — there is no real college authentication, identity "
            "verification, or permission backend."
        )
        st.caption(
            ":material/smart_toy: AI: "
            + ("configured" if ai_is_configured() else "not configured (database-only mode)")
        )
        st.caption(DEMO_DATA_LABEL)


def is_faculty() -> bool:
    return st.session_state.get("demo_role", "Faculty") == "Faculty"


def is_student() -> bool:
    return st.session_state.get("demo_role") == "Student"


def get_selected_student() -> dict[str, Any] | None:
    student_id = st.session_state.get("demo_student_id")
    if student_id is None:
        return None
    return get_student(int(student_id))


def get_selected_student_id() -> int | None:
    value = st.session_state.get("demo_student_id")
    return int(value) if value is not None else None


def page_header(title: str, subtitle: str, icon: str) -> None:
    st.title(title, icon=icon)
    st.caption(subtitle)
    show_flash()


def set_flash(message: str, kind: str = "success") -> None:
    if kind not in {"success", "info", "warning", "error"}:
        kind = "success"
    st.session_state["_flash"] = (kind, message)


def show_flash() -> None:
    flash = st.session_state.get("_flash")
    if not flash:
        return
    kind, message = flash
    getattr(st, kind)(message)
    st.session_state["_flash"] = None


def faculty_only_notice() -> None:
    if not is_faculty():
        st.info(
            "Faculty-only actions are hidden in the Student demo role. Switch the demo role "
            "in the sidebar to manage records. This is not real authorization.",
            icon=":material/lock:",
        )


def status_badge(status: str) -> None:
    styles = {
        "Pending": ("orange", ":material/schedule:"),
        "Submitted": ("green", ":material/check_circle:"),
        "Late": ("orange", ":material/history:"),
        "Overdue": ("red", ":material/error:"),
        "Present": ("green", ":material/check_circle:"),
        "Absent": ("red", ":material/cancel:"),
        "Active": ("green", ":material/check_circle:"),
        "Inactive": ("gray", ":material/block:"),
    }
    color, icon = styles.get(status, ("blue", ":material/info:"))
    st.badge(status, icon=icon, color=color)


def empty_state(message: str, icon: str = ":material/inbox:") -> None:
    with st.container(border=True):
        st.markdown(f"**{icon} Nothing to show yet**")
        st.caption(message)


def date_label(value: date | str | None) -> str:
    if not value:
        return "No expiry"
    if isinstance(value, date):
        return value.isoformat()
    return str(value)
