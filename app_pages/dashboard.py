"""Home dashboard with database-backed counts, reminders, and quick actions."""

from __future__ import annotations

from datetime import date

import streamlit as st

from services import (
    assignment_service,
    attendance_service,
    notice_service,
    reminder_service,
    timetable_service,
)
from services.student_service import count_students
from utils.ui import (
    get_selected_student,
    is_faculty,
    page_header,
    status_badge,
)

today = date.today()
selected_student = get_selected_student()
selected_semester = selected_student["semester"] if selected_student else None

page_header(
    "Dashboard",
    f"{today.strftime('%A, %d %B %Y')} · Local college prototype with fictional DEMO records.",
    ":material/space_dashboard:",
)

reminder_service.generate_reminders(today=today)
today_attendance = attendance_service.today_summary(today)
active_students = count_students()
pending_assignments = (
    assignment_service.pending_count(
        selected_student["id"], semester=selected_student["semester"], today=today
    )
    if selected_student
    else 0
)
upcoming = (
    assignment_service.upcoming_deadlines(
        days=7,
        student_db_id=selected_student["id"],
        semester=selected_student["semester"],
        today=today,
    )
    if selected_student
    else assignment_service.upcoming_deadlines(days=7, today=today)
)
current_notices = notice_service.list_notices(today=today)
today_classes = timetable_service.list_entries(
    semester=selected_semester, weekday=today.weekday()
)
reminders = reminder_service.list_reminders(reminder_date=today)

metric_columns = st.columns(3)
metric_specs = [
    (
        "Active demo students",
        str(active_students),
        "Fictional records only",
        ":material/groups:",
    ),
    (
        "Today's attendance",
        f"{today_attendance['percentage']:.1f}%" if today_attendance["total"] else "No records",
        (
            f"{today_attendance['present']} present · {today_attendance['late']} late · "
            f"{today_attendance['absent']} absent"
            if today_attendance["total"]
            else "Attendance has not been recorded for today"
        ),
        ":material/fact_check:",
    ),
    (
        "Pending assignments",
        str(pending_assignments),
        (
            f"For {selected_student['student_id']} in semester {selected_student['semester']}"
            if selected_student
            else "Choose a demo student in the sidebar"
        ),
        ":material/assignment:",
    ),
    (
        "Upcoming deadlines",
        str(len(upcoming)),
        "Next 7 days",
        ":material/event_upcoming:",
    ),
    (
        "Active notices",
        str(len(current_notices)),
        "Current and not expired",
        ":material/campaign:",
    ),
    (
        "Today's classes",
        str(len(today_classes)),
        (
            f"Semester {selected_semester} timetable"
            if selected_semester
            else "All semesters"
        ),
        ":material/calendar_month:",
    ),
]
for index, (label, value, caption, icon) in enumerate(metric_specs):
    with metric_columns[index % 3]:
        with st.container(border=True):
            st.metric(label, value)
            st.caption(f"{icon} {caption}")

st.space("small")

left, right = st.columns(2, gap="large")
with left:
    with st.container(border=True):
        st.subheader("Upcoming deadlines", icon=":material/event_upcoming:")
        st.caption("Calculated from assignment due dates stored in SQLite.")
        if not upcoming:
            st.caption("No unsubmitted assignments are due in the next 7 days.")
        else:
            for assignment in upcoming[:6]:
                days_left = assignment["days_until_due"]
                when = "Due today" if days_left == 0 else f"Due in {days_left} day(s)"
                st.markdown(
                    f"**{assignment['title']}**  \n"
                    f"{assignment['subject_code']} · {assignment['due_date']} · {when}"
                )
                status_badge(assignment["status"])
        st.page_link(
            "app_pages/assignments.py",
            label="Open assignments",
            icon=":material/arrow_forward:",
        )

with right:
    with st.container(border=True):
        st.subheader("Today's timetable", icon=":material/calendar_month:")
        st.caption(
            f"Recurring classes for {today.strftime('%A')}"
            + (f" in semester {selected_semester}" if selected_semester else "")
        )
        if not today_classes:
            st.caption("No timetable entries are stored for today.")
        else:
            for entry in today_classes:
                st.markdown(
                    f"**{entry['start_time']}–{entry['end_time']} · {entry['subject_code']}**  \n"
                    f"{entry['subject_name']} · {entry['room']} · {entry['faculty_name']}"
                )
        st.page_link(
            "app_pages/timetable.py",
            label="Open weekly timetable",
            icon=":material/arrow_forward:",
        )

st.space("small")

left, right = st.columns(2, gap="large")
with left:
    with st.container(border=True):
        st.subheader("Recent college notices", icon=":material/campaign:")
        recent = current_notices[:4]
        if not recent:
            st.caption("No current notices are stored in the local database.")
        else:
            for notice in recent:
                st.markdown(f"**{notice['title']}**  \n{notice['publish_date']} · {notice['category']}")
                st.caption(notice["content"][:150] + ("…" if len(notice["content"]) > 150 else ""))
        st.page_link(
            "app_pages/notices.py",
            label="Open notice board",
            icon=":material/arrow_forward:",
        )

with right:
    with st.container(border=True):
        st.subheader("In-app reminders", icon=":material/notifications_active:")
        st.caption(
            "Generated from stored due/expiry dates. These messages appear only inside this "
            "app while it is running; no email, SMS, or WhatsApp is sent."
        )
        if not reminders:
            st.caption("No reminders for today. Deadlines or expiring notices will appear here.")
        else:
            counts = reminder_service.reminder_counts(reminder_date=today)
            st.markdown(
                f"{counts['assignment_overdue']} overdue · {counts['assignment_due']} due soon · "
                f"{counts['notice_expiring']} expiring notice(s)"
            )
            for reminder in reminders[:8]:
                if reminder["reminder_type"] == "assignment_overdue":
                    st.warning(reminder["message"], icon=":material/error:")
                elif reminder["reminder_type"] == "notice_expiring":
                    st.info(reminder["message"], icon=":material/event_busy:")
                else:
                    st.info(reminder["message"], icon=":material/schedule:")

st.space("small")
with st.container(border=True):
    st.subheader("Quick actions", icon=":material/bolt:")
    if is_faculty():
        st.caption("Faculty demo actions open the relevant page. No decorative buttons.")
        action_columns = st.columns(4)
        with action_columns[0]:
            st.page_link("app_pages/students.py", label="Manage students", icon=":material/groups:")
        with action_columns[1]:
            st.page_link("app_pages/attendance.py", label="Record attendance", icon=":material/fact_check:")
        with action_columns[2]:
            st.page_link("app_pages/assignments.py", label="Create assignment", icon=":material/add_task:")
        with action_columns[3]:
            st.page_link("app_pages/notices.py", label="Add a notice", icon=":material/post_add:")
    else:
        st.caption("Student demo actions. The sidebar role selector is not authentication.")
        action_columns = st.columns(4)
        with action_columns[0]:
            st.page_link("app_pages/assignments.py", label="View assignments", icon=":material/assignment:")
        with action_columns[1]:
            st.page_link("app_pages/timetable.py", label="View timetable", icon=":material/calendar_month:")
        with action_columns[2]:
            st.page_link("app_pages/notices.py", label="Read notices", icon=":material/campaign:")
        with action_columns[3]:
            st.page_link("app_pages/ai_assistant.py", label="Ask the assistant", icon=":material/smart_toy:")

st.caption(
    "All statistics above are queried from the local SQLite database. "
    "This is a single-user classroom prototype, not a production university system."
)
