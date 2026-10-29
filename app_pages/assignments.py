"""Assignment creation, deadline views, reminders, and demo submission tracking."""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from services import assignment_service, attendance_service, reminder_service
from utils.ui import (
    empty_state,
    get_selected_student,
    is_faculty,
    page_header,
    set_flash,
    status_badge,
)
from utils.validation import ValidationError

today = date.today()
page_header(
    "Assignments",
    "Track deadlines and statuses. Demo submission only records a flag — no document is uploaded.",
    ":material/assignment:",
)

faculty = is_faculty()
student = get_selected_student()
semester = student["semester"] if student else None
subjects = attendance_service.list_subjects(semester=semester)
subject_labels = {subject["id"]: f"{subject['code']} — {subject['name']}" for subject in subjects}

tabs = st.tabs(["Browse assignments", "Create assignment"] if faculty else ["Browse assignments"])
browse_tab = tabs[0]
create_tab = tabs[1] if faculty else None

reminder_service.generate_reminders(today=today)

with browse_tab:
    if not student:
        empty_state("Choose a demo student in the sidebar to view assignment statuses.")
    else:
        with st.container(border=True):
            st.subheader("Deadline reminders", icon=":material/notifications_active:")
            st.caption(
                "Generated from stored due dates and deduplicated for today. "
                "Displayed only inside this app; nothing is sent externally."
            )
            today_reminders = [
                reminder
                for reminder in reminder_service.list_reminders(reminder_date=today)
                if reminder["entity_type"] == "assignment"
            ]
            if not today_reminders:
                st.caption("No assignment reminders for today.")
            else:
                for reminder in today_reminders:
                    if reminder["reminder_type"] == "assignment_overdue":
                        st.warning(reminder["message"], icon=":material/error:")
                    else:
                        st.info(reminder["message"], icon=":material/schedule:")

        filter_columns = st.columns([2, 2])
        with filter_columns[0]:
            subject_choices = [None] + [subject["id"] for subject in subjects]
            subject_filter = st.selectbox(
                "Filter by subject",
                options=subject_choices,
                format_func=lambda value: "All subjects" if value is None else subject_labels[value],
                key="assignment_subject_filter",
            )
        with filter_columns[1]:
            status_filter = st.selectbox(
                "Filter by status",
                options=["All", "Pending", "Submitted", "Late", "Overdue"],
                key="assignment_status_filter",
            )

        assignments = assignment_service.list_assignments(
            student_db_id=student["id"],
            subject_id=subject_filter,
            semester=semester,
            status_filter=status_filter,
            today=today,
        )

        st.caption(
            f"{len(assignments)} assignment(s) shown for {student['student_id']} "
            f"(semester {semester}). Status is calculated from stored submissions and due dates."
        )
        if not assignments:
            empty_state("No assignments match the selected subject and status filters.")
        else:
            for assignment in assignments:
                with st.container(border=True):
                    title_col, status_col = st.columns([4, 1])
                    with title_col:
                        st.subheader(assignment["title"], icon=":material/description:")
                        st.caption(
                            f"{assignment['subject_code']} — {assignment['subject_name']} · "
                            f"Published {assignment['publish_date']} · Due {assignment['due_date']}"
                        )
                    with status_col:
                        status_badge(assignment["status"])
                    st.write(assignment["description"])
                    if assignment["status"] == "Overdue":
                        st.warning(
                            f"This assignment is {abs(assignment['days_until_due'])} day(s) overdue.",
                            icon=":material/error:",
                        )
                    elif assignment["days_until_due"] == 0:
                        st.warning("This assignment is due today.", icon=":material/schedule:")
                    elif assignment["submitted_at"]:
                        st.caption(f"Marked submitted at {assignment['submitted_at']}.")

                    if faculty:
                        counts = assignment_service.submission_stats_for_assignment(
                            assignment["id"], today=today
                        )
                        st.caption(
                            "Demo submission counts: "
                            f"Submitted {counts['Submitted']} · Late {counts['Late']} · "
                            f"Pending {counts['Pending']} · Overdue {counts['Overdue']} "
                            f"of {counts['Total']} active student(s)."
                        )
                    elif not assignment["submitted_at"]:
                        if st.button(
                            "Mark as submitted (demo)",
                            icon=":material/task_alt:",
                            key=f"submit_assignment_{assignment['id']}",
                        ):
                            try:
                                result = assignment_service.mark_submitted(
                                    assignment["id"], student["id"], submitted_date=today
                                )
                            except ValidationError as exc:
                                st.error(str(exc), icon=":material/error:")
                            else:
                                set_flash(
                                    "Demo submission recorded as "
                                    f"{result['status']}. No file was uploaded."
                                )
                                st.rerun()
                        st.caption(
                            "This only records a demo submission flag and timestamp. "
                            "Real document upload is not implemented."
                        )

if faculty and create_tab is not None:
    with create_tab:
        with st.container(border=True):
            st.subheader("Create an assignment", icon=":material/add_task:")
            all_subjects = attendance_service.list_subjects()
            all_labels = {subject["id"]: f"{subject['code']} — {subject['name']}" for subject in all_subjects}
            if not all_subjects:
                empty_state("No subjects are configured.")
            else:
                with st.form("create_assignment_form"):
                    title = st.text_input("Title", placeholder="DEMO: Week 6 laboratory report")
                    subject_id = st.selectbox(
                        "Subject",
                        options=[subject["id"] for subject in all_subjects],
                        format_func=lambda value: all_labels[value],
                    )
                    description = st.text_area(
                        "Description",
                        placeholder="Describe the fictional task, expected evidence, and submission instructions.",
                        height=130,
                    )
                    date_columns = st.columns(2)
                    with date_columns[0]:
                        publish_date = st.date_input("Publish date", value=today)
                    with date_columns[1]:
                        due_date = st.date_input("Due date", value=today + timedelta(days=7))
                    submitted = st.form_submit_button(
                        "Create assignment", icon=":material/add_task:", type="primary"
                    )
                if submitted:
                    try:
                        assignment_id = assignment_service.create_assignment(
                            title, subject_id, description, publish_date, due_date
                        )
                    except ValidationError as exc:
                        st.error(str(exc), icon=":material/error:")
                    else:
                        set_flash(f"Assignment #{assignment_id} created.")
                        st.rerun()
