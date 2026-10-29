"""Weekly timetable, conflict-checked faculty editing, and academic information."""

from __future__ import annotations

from datetime import date, time

import streamlit as st

from services import attendance_service, timetable_service
from services.database import get_academic_info, set_settings
from utils.ui import (
    empty_state,
    get_selected_student,
    is_faculty,
    page_header,
    set_flash,
)
from utils.validation import ValidationError

page_header(
    "Timetable",
    "Weekly class schedule with room/faculty conflict checks and editable demo academic information.",
    ":material/calendar_month:",
)

faculty = is_faculty()
student = get_selected_student()
default_semester = student["semester"] if student else 3
subjects = attendance_service.list_subjects()
subject_labels = {subject["id"]: f"{subject['code']} â€” {subject['name']}" for subject in subjects}
weekday_names = list(timetable_service.WEEKDAY_NAMES)

tab_names = ["Weekly timetable", "Add / edit entry", "Academic information"] if faculty else [
    "Weekly timetable",
    "Academic information",
]
tabs = st.tabs(tab_names)
weekly_tab = tabs[0]
edit_tab = tabs[1] if faculty else None
info_tab = tabs[2] if faculty else tabs[1]

with weekly_tab:
    with st.container(border=True):
        st.subheader("Weekly class grid", icon=":material/calendar_view_week:")
        semester_options = [None] + list(range(1, 9))
        semester_filter = st.selectbox(
            "Semester",
            options=semester_options,
            index=default_semester,
            format_func=lambda value: "All semesters" if value is None else f"Semester {value}",
            key="timetable_semester_filter",
        )
        st.caption(
            "All entries are fictional demo data. Times use 24-hour HH:MM format. "
            "Overlapping entries are rejected when added or edited."
        )

    entries = timetable_service.list_entries(semester=semester_filter)
    if not entries:
        empty_state(
            "No timetable entries match the selected semester. "
            "Faculty can add an entry in the next tab."
        )
    else:
        today_name = timetable_service.WEEKDAY_NAMES[date.today().weekday()]
        by_day = {
            weekday: [entry for entry in entries if entry["weekday"] == weekday]
            for weekday in range(7)
        }
        day_columns = st.columns(3)
        for weekday, day_name in enumerate(weekday_names):
            with day_columns[weekday % 3]:
                with st.container(border=True):
                    suffix = " Â· Today" if day_name == today_name else ""
                    st.markdown(f"**{day_name}{suffix}**")
                    day_entries = by_day[weekday]
                    if not day_entries:
                        st.caption("No classes")
                    for entry in day_entries:
                        st.markdown(
                            f"**{entry['start_time']}â€“{entry['end_time']}**  \n"
                            f"{entry['subject_code']} â€” {entry['subject_name']}  \n"
                            f":material/meeting_room: {entry['room']}  \n"
                            f":material/person: {entry['faculty_name']}"
                        )
                        if semester_filter is None:
                            st.caption(f"Semester {entry['semester']}")
                        st.divider()

if faculty and edit_tab is not None:
    with edit_tab:
        if not subjects:
            empty_state("No subjects are configured, so timetable entries cannot be created.")
        else:
            st.subheader("Add a timetable entry", icon=":material/calendar_month:")
            with st.form("add_timetable_form"):
                first_row = st.columns([2, 1, 1])
                with first_row[0]:
                    weekday = st.selectbox("Weekday", options=weekday_names)
                with first_row[1]:
                    start_time = st.time_input("Start time", value=time(9, 0))
                with first_row[2]:
                    end_time = st.time_input("End time", value=time(10, 0))
                second_row = st.columns([3, 1, 2])
                with second_row[0]:
                    subject_id = st.selectbox(
                        "Subject",
                        options=[subject["id"] for subject in subjects],
                        format_func=lambda value: subject_labels[value],
                    )
                with second_row[1]:
                    semester = st.number_input(
                        "Semester",
                        min_value=1,
                        max_value=8,
                        value=default_semester,
                        step=1,
                    )
                with second_row[2]:
                    room = st.text_input("Room", value="Room 101")
                faculty_name = st.text_input("Faculty name", value="Dr. Demo Faculty")
                submitted = st.form_submit_button(
                    "Add entry", icon=":material/calendar_month:", type="primary"
                )
            if submitted:
                try:
                    timetable_service.add_entry(
                        weekday_names.index(weekday),
                        start_time.strftime("%H:%M"),
                        end_time.strftime("%H:%M"),
                        subject_id,
                        room,
                        faculty_name,
                        int(semester),
                    )
                except ValidationError as exc:
                    st.error(str(exc), icon=":material/error:")
                else:
                    set_flash("Timetable entry added after conflict validation.")
                    st.rerun()

        st.divider()
        st.subheader("Manage existing entries", icon=":material/edit_calendar:")
        all_entries = timetable_service.list_entries()
        if not all_entries:
            empty_state("There are no timetable entries to edit.")
        else:
            entry_labels = {
                entry["id"]: (
                    f"{entry['weekday_name']} {entry['start_time']}â€“{entry['end_time']} Â· "
                    f"{entry['subject_code']} Â· Semester {entry['semester']}"
                )
                for entry in all_entries
            }
            entry_ids = [entry["id"] for entry in all_entries]
            selected_entry_id = st.selectbox(
                "Timetable entry",
                options=entry_ids,
                format_func=lambda entry_id: entry_labels[entry_id],
                key="timetable_manage_select",
            )
            entry = timetable_service.get_entry(selected_entry_id)
            if entry:
                with st.container(border=True):
                    with st.form(f"edit_timetable_form_{selected_entry_id}"):
                        first_row = st.columns([2, 1, 1])
                        with first_row[0]:
                            edit_weekday = st.selectbox(
                                "Weekday",
                                options=weekday_names,
                                index=entry["weekday"],
                            )
                        with first_row[1]:
                            edit_start = st.time_input(
                                "Start time",
                                value=time.fromisoformat(entry["start_time"]),
                            )
                        with first_row[2]:
                            edit_end = st.time_input(
                                "End time",
                                value=time.fromisoformat(entry["end_time"]),
                            )
                        second_row = st.columns([3, 1, 2])
                        with second_row[0]:
                            subject_options = [subject["id"] for subject in subjects]
                            subject_index = (
                                subject_options.index(entry["subject_id"])
                                if entry["subject_id"] in subject_options
                                else 0
                            )
                            edit_subject_id = st.selectbox(
                                "Subject",
                                options=subject_options,
                                index=subject_index,
                                format_func=lambda value: subject_labels[value],
                            )
                        with second_row[1]:
                            edit_semester = st.number_input(
                                "Semester",
                                min_value=1,
                                max_value=8,
                                value=entry["semester"],
                                step=1,
                            )
                        with second_row[2]:
                            edit_room = st.text_input("Room", value=entry["room"])
                        edit_faculty = st.text_input("Faculty name", value=entry["faculty_name"])
                        saved = st.form_submit_button(
                            "Save entry", icon=":material/save:", type="primary"
                        )
                    if saved:
                        try:
                            timetable_service.update_entry(
                                selected_entry_id,
                                weekday_names.index(edit_weekday),
                                edit_start.strftime("%H:%M"),
                                edit_end.strftime("%H:%M"),
                                edit_subject_id,
                                edit_room,
                                edit_faculty,
                                int(edit_semester),
                            )
                        except ValidationError as exc:
                            st.error(str(exc), icon=":material/error:")
                        else:
                            set_flash("Timetable entry updated.")
                            st.rerun()

                    confirm_delete = st.checkbox(
                        "I understand this permanently deletes the demo timetable entry.",
                        key=f"confirm_delete_timetable_{selected_entry_id}",
                    )
                    if st.button(
                        "Delete entry",
                        icon=":material/delete:",
                        disabled=not confirm_delete,
                        key=f"delete_timetable_{selected_entry_id}",
                    ):
                        try:
                            timetable_service.delete_entry(selected_entry_id)
                        except ValidationError as exc:
                            st.error(str(exc), icon=":material/error:")
                        else:
                            set_flash("Timetable entry deleted.", "warning")
                            st.rerun()

with info_tab:
    info = get_academic_info()
    st.subheader("Demo academic information", icon=":material/school:")
    if faculty:
        st.caption(
            "These settings feed the dashboard and the database-grounded assistant. "
            "Keep them clearly marked as demo information."
        )
        with st.form("academic_info_form"):
            info_columns = st.columns([1, 1])
            with info_columns[0]:
                current_semester = st.selectbox(
                    "Current academic semester",
                    options=list(range(1, 9)),
                    index=max(
                        0,
                        min(
                            7,
                            int(info.get("academic_current_semester", "3") or 3) - 1,
                        ),
                    ),
                )
                exam_notice = st.text_area(
                    "Examination notice",
                    value=info.get("academic_exam_notice", ""),
                    height=130,
                )
            with info_columns[1]:
                office_hours = st.text_area(
                    "Office hours",
                    value=info.get("academic_office_hours", ""),
                    height=130,
                )
                calendar = st.text_area(
                    "Academic calendar notes",
                    value=info.get("academic_calendar", ""),
                    height=130,
                )
            saved = st.form_submit_button(
                "Save academic information", icon=":material/save:", type="primary"
            )
        if saved:
            try:
                set_settings(
                    {
                        "academic_current_semester": str(current_semester),
                        "academic_exam_notice": exam_notice,
                        "academic_office_hours": office_hours,
                        "academic_calendar": calendar,
                    }
                )
            except Exception as exc:
                st.error(str(exc), icon=":material/error:")
            else:
                set_flash("Academic information updated.")
                st.rerun()
    else:
        st.info(
            "Read-only in the Student demo role. This demo does not implement real authorization.",
            icon=":material/visibility:",
        )

    display_columns = st.columns(2)
    with display_columns[0]:
        with st.container(border=True):
            st.markdown("**Current academic semester**")
            st.markdown(f"Semester {info.get('academic_current_semester', 'â€”')}")
        with st.container(border=True):
            st.markdown("**Examination notice**")
            st.write(info.get("academic_exam_notice") or "Not provided.")
    with display_columns[1]:
        with st.container(border=True):
            st.markdown("**Office hours**")
            st.write(info.get("academic_office_hours") or "Not provided.")
        with st.container(border=True):
            st.markdown("**Academic calendar notes**")
            st.write(info.get("academic_calendar") or "Not provided.")
