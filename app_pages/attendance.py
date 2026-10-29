"""Faculty attendance entry plus filtered history and CSV export."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from services import attendance_service
from services.student_service import list_students
from utils.ui import (
    empty_state,
    get_selected_student,
    is_faculty,
    page_header,
    set_flash,
)

today = date.today()
page_header(
    "Attendance",
    "Record Present, Absent, or Late, then review percentages calculated from stored records.",
    ":material/fact_check:",
)

faculty = is_faculty()
subjects = attendance_service.list_subjects()
subject_labels = {subject["id"]: f"{subject['code']} — {subject['name']}" for subject in subjects}
tab_names = ["Record attendance", "History & analytics"] if faculty else ["History & analytics"]
tabs = st.tabs(tab_names)
record_tab = tabs[0] if faculty else None
history_tab = tabs[1] if faculty else tabs[0]

if faculty and record_tab is not None:
    with record_tab:
        st.subheader("Record or edit attendance", icon=":material/edit_calendar:")
        if not subjects:
            empty_state("No subjects are configured, so attendance cannot be recorded.")
        else:
            with st.container(border=True):
                filter_columns = st.columns([1, 1, 2])
                with filter_columns[0]:
                    attendance_date = st.date_input(
                        "Attendance date",
                        value=today,
                        max_value=today,
                        key="attendance_entry_date",
                    )
                with filter_columns[1]:
                    semester = st.selectbox(
                        "Student group (semester)",
                        options=list(range(1, 9)),
                        index=2,
                        key="attendance_entry_semester",
                    )
                with filter_columns[2]:
                    subject_id = st.selectbox(
                        "Subject",
                        options=[subject["id"] for subject in subjects],
                        format_func=lambda value: subject_labels[value],
                        key="attendance_entry_subject",
                    )
                subject = attendance_service.get_subject(subject_id)
                if subject and subject["semester"] != semester:
                    st.caption(
                        f"Note: {subject['code']} is normally offered in semester {subject['semester']}. "
                        "You can still record a cross-listed demo group."
                    )

                students = attendance_service.students_for_semester(semester)
                if not students:
                    empty_state(f"No active demo students are in semester {semester}.")
                else:
                    existing = attendance_service.get_attendance_map(
                        attendance_date, subject_id, semester
                    )
                    if existing:
                        st.info(
                            "Existing records for this date and subject were loaded. "
                            "Saving will update those records rather than create duplicates.",
                            icon=":material/history:",
                        )
                    statuses = pd.DataFrame(
                        {
                            "Student ID": [student["student_id"] for student in students],
                            "Name": [student["name"] for student in students],
                            "Semester": [student["semester"] for student in students],
                            "Status": [existing.get(student["id"], "Present") for student in students],
                        }
                    )
                    edited = st.data_editor(
                        statuses,
                        hide_index=True,
                        key=(
                            f"attendance_editor_{attendance_date.isoformat()}_"
                            f"{subject_id}_{semester}"
                        ),
                        disabled=["Student ID", "Name", "Semester"],
                        column_config={
                            "Status": st.column_config.SelectboxColumn(
                                "Status",
                                help="Choose Present, Absent, or Late.",
                                options=["Present", "Absent", "Late"],
                                required=True,
                            )
                        },
                        alt="Editable attendance table for the selected demo student group",
                    )
                    if st.button(
                        "Save attendance",
                        icon=":material/save:",
                        type="primary",
                        width="stretch",
                    ):
                        lookup = {student["student_id"]: student["id"] for student in students}
                        records = [
                            (lookup[row["Student ID"]], row["Status"])
                            for _, row in edited.iterrows()
                            if row["Student ID"] in lookup
                        ]
                        try:
                            saved = attendance_service.save_attendance_bulk(
                                attendance_date, subject_id, records
                            )
                        except Exception as exc:
                            st.error(str(exc), icon=":material/error:")
                        else:
                            set_flash(f"Saved {saved} attendance record(s) for {attendance_date.isoformat()}.")
                            st.rerun()

with history_tab:
    st.subheader("Attendance history", icon=":material/analytics:")
    selected_student = get_selected_student()
    student_rows = list_students(include_inactive=True)
    student_labels = {
        student["id"]: f"{student['student_id']} — {student['name']}" for student in student_rows
    }

    with st.container(border=True):
        if faculty:
            filter_columns = st.columns([2, 2, 2])
            with filter_columns[0]:
                student_choices = [None] + [student["id"] for student in student_rows]
                history_student = st.selectbox(
                    "Student",
                    options=student_choices,
                    format_func=lambda value: "All demo students" if value is None else student_labels[value],
                    key="attendance_history_student",
                )
            with filter_columns[1]:
                subject_choices = [None] + [subject["id"] for subject in subjects]
                history_subject = st.selectbox(
                    "Subject",
                    options=subject_choices,
                    format_func=lambda value: "All subjects" if value is None else subject_labels[value],
                    key="attendance_history_subject",
                )
            with filter_columns[2]:
                date_range = st.date_input(
                    "Date range",
                    value=(today - timedelta(days=30), today),
                    max_value=today,
                    key="attendance_history_dates",
                )
        else:
            history_student = selected_student["id"] if selected_student else None
            st.caption(
                "Student demo view: showing only the selected demo student's attendance records. "
                "This is not real access control."
            )
            filter_columns = st.columns([2, 2])
            with filter_columns[0]:
                subject_choices = [None] + [subject["id"] for subject in subjects]
                history_subject = st.selectbox(
                    "Subject",
                    options=subject_choices,
                    format_func=lambda value: "All subjects" if value is None else subject_labels[value],
                    key="student_attendance_history_subject",
                )
            with filter_columns[1]:
                date_range = st.date_input(
                    "Date range",
                    value=(today - timedelta(days=30), today),
                    max_value=today,
                    key="student_attendance_history_dates",
                )

    if isinstance(date_range, (tuple, list)):
        start_date = date_range[0]
        end_date = date_range[1] if len(date_range) > 1 else date_range[0]
    else:
        start_date = end_date = date_range

    summary = attendance_service.attendance_summary(
        student_db_id=history_student,
        subject_id=history_subject,
        start_date=start_date,
        end_date=end_date,
    )

    metric_columns = st.columns(4)
    metric_columns[0].metric(
        "Attendance percentage",
        f"{summary['percentage']:.1f}%" if summary["total"] else "No records",
        border=True,
    )
    metric_columns[1].metric("Present", summary["present"], border=True)
    metric_columns[2].metric("Late", summary["late"], border=True)
    metric_columns[3].metric("Absent", summary["absent"], border=True)
    st.caption(
        "Percentage = (Present + Late) / total stored records. "
        "Change the filters to update the calculation. Days with no records show as an empty state."
    )
    if summary["total"] and summary["percentage"] < 75:
        st.warning(
            f"Low attendance warning: the filtered percentage is {summary['percentage']:.1f}%, "
            "below the 75% demo threshold. This warning is informational, not an official policy.",
            icon=":material/notification_important:",
        )

    if not summary["records"]:
        empty_state("No attendance records match the selected filters.")
    else:
        rows = [
            {
                "Date": record["attendance_date"],
                "Student ID": record["student_id"],
                "Name": record["student_name"],
                "Subject": f"{record['subject_code']} — {record['subject_name']}",
                "Status": record["status"],
                "Recorded at": record["recorded_at"],
            }
            for record in summary["records"]
        ]
        history_frame = pd.DataFrame(rows)
        st.dataframe(
            history_frame,
            hide_index=True,
            alt="Filtered attendance history for demo students",
        )
        with st.expander("Subject-wise breakdown", icon=":material/bar_chart:"):
            by_subject: dict[str, dict[str, int]] = {}
            for record in summary["records"]:
                key = f"{record['subject_code']} — {record['subject_name']}"
                by_subject.setdefault(key, {"Present": 0, "Late": 0, "Absent": 0})
                by_subject[key][record["status"]] += 1
            breakdown_rows = []
            for subject_name, counts in sorted(by_subject.items()):
                total = sum(counts.values())
                attended = counts["Present"] + counts["Late"]
                breakdown_rows.append(
                    {
                        "Subject": subject_name,
                        "Present": counts["Present"],
                        "Late": counts["Late"],
                        "Absent": counts["Absent"],
                        "Total": total,
                        "Attendance %": round((attended / total) * 100, 1) if total else 0.0,
                    }
                )
            st.dataframe(
                pd.DataFrame(breakdown_rows),
                hide_index=True,
                alt="Subject-wise attendance breakdown for the filtered records",
            )
            st.caption(
                f"Total records: {summary['total']} · attended (present + late): {summary['attended']}"
            )
        csv_bytes = history_frame.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Export filtered attendance as CSV",
            data=csv_bytes,
            file_name=f"attendance_{start_date}_{end_date}.csv",
            mime="text/csv",
            icon=":material/download:",
        )
