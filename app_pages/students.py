"""Student directory, detail view, and faculty CRUD actions."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from services import assignment_service, attendance_service
from services.student_service import (
    add_student,
    deactivate_student,
    get_student,
    list_departments,
    list_students,
    reactivate_student,
    update_student,
)
from utils.ui import (
    empty_state,
    faculty_only_notice,
    is_faculty,
    page_header,
    set_flash,
    status_badge,
)
from utils.validation import ValidationError

page_header(
    "Students",
    "Search student records, view details, and manage fictional demo students.",
    ":material/groups:",
)

faculty = is_faculty()
if not faculty:
    faculty_only_notice()

departments = list_departments()
tabs = st.tabs(["Directory", "Add student", "Edit & deactivate"] if faculty else ["Directory"])
directory_tab = tabs[0]
add_tab = tabs[1] if faculty else None
edit_tab = tabs[2] if faculty else None

with directory_tab:
    with st.container(border=True):
        st.subheader("Search and filter", icon=":material/search:")
        search_col, department_col, status_col = st.columns([2, 1, 1])
        with search_col:
            search = st.text_input(
                "Search",
                placeholder="Search by student ID, name, email, or department",
                key="student_search",
            )
        with department_col:
            department = st.selectbox("Department", ["All"] + departments, key="student_department")
        with status_col:
            include_inactive = st.toggle("Include inactive", value=False, key="student_include_inactive")

    students = list_students(
        search=search,
        department=None if department == "All" else department,
        include_inactive=include_inactive,
    )

    if not students:
        empty_state("No student records match the current filters.")
    else:
        table_rows = [
            {
                "Student ID": student["student_id"],
                "Name": student["name"],
                "Department": student["department"],
                "Semester": student["semester"],
                "Email": student["email"],
                "Status": "Active" if student["is_active"] else "Inactive",
            }
            for student in students
        ]
        st.dataframe(
            pd.DataFrame(table_rows),
            hide_index=True,
            column_config={
                "Semester": st.column_config.NumberColumn("Semester", width="small"),
            },
            alt="Searchable table of demo student records",
        )
        st.caption(f"{len(students)} record(s) shown. All records are fictional DEMO data.")

        st.subheader("Student detail", icon=":material/badge:")
        student_ids = [student["id"] for student in students]
        labels = {
            student["id"]: f"{student['student_id']} — {student['name']}" for student in students
        }
        selected_id = st.selectbox(
            "Choose a student",
            options=student_ids,
            format_func=lambda student_id: labels[student_id],
            key="student_detail_select",
        )
        student = get_student(selected_id)
        if student:
            attendance = attendance_service.attendance_summary(student_db_id=student["id"])
            stats = assignment_service.student_assignment_stats(
                student["id"], semester=student["semester"]
            )
            with st.container(border=True):
                header_left, header_right = st.columns([3, 1])
                with header_left:
                    st.subheader(student["name"])
                    st.caption(
                        f"{student['student_id']} · {student['department']} · "
                        f"Semester {student['semester']} · {student['email']}"
                    )
                with header_right:
                    status_badge("Active" if student["is_active"] else "Inactive")
                metric_columns = st.columns(4)
                metric_columns[0].metric(
                    "Attendance",
                    f"{attendance['percentage']:.1f}%" if attendance["total"] else "No records",
                )
                metric_columns[1].metric("Pending work", stats["Pending"])
                metric_columns[2].metric("Submitted", stats["Submitted"] + stats["Late"])
                metric_columns[3].metric("Overdue", stats["Overdue"])
                st.caption(
                    "Attendance counts Present and Late as attended. "
                    f"Stored attendance records: {attendance['total']}. "
                    f"Present {attendance['present']} · Late {attendance['late']} · Absent {attendance['absent']}."
                )

            if attendance["records"]:
                by_subject: dict[str, dict[str, int]] = {}
                for record in attendance["records"]:
                    subject = f"{record['subject_code']} — {record['subject_name']}"
                    by_subject.setdefault(subject, {"Present": 0, "Late": 0, "Absent": 0})
                    by_subject[subject][record["status"]] += 1
                subject_rows = []
                for subject, counts in sorted(by_subject.items()):
                    total = sum(counts.values())
                    percentage = round(((counts["Present"] + counts["Late"]) / total) * 100, 1) if total else 0.0
                    subject_rows.append(
                        {
                            "Subject": subject,
                            "Present": counts["Present"],
                            "Late": counts["Late"],
                            "Absent": counts["Absent"],
                            "Attendance %": percentage,
                        }
                    )
                st.dataframe(
                    pd.DataFrame(subject_rows),
                    hide_index=True,
                    alt="Attendance summary by subject for the selected demo student",
                )

if faculty and add_tab is not None:
    with add_tab:
        with st.container(border=True):
            st.subheader("Add a demo student", icon=":material/person_add:")
            st.caption("Student IDs must be unique. Email format and semester are validated.")
            with st.form("add_student_form"):
                left, right = st.columns(2)
                with left:
                    new_student_id = st.text_input("Student ID", placeholder="STU011")
                    new_name = st.text_input("Full name", placeholder="Demo Student")
                    new_department = st.text_input("Department", value="Computer Science")
                with right:
                    new_semester = st.number_input("Semester", min_value=1, max_value=8, value=1, step=1)
                    new_email = st.text_input("Email", placeholder="student@demo.example.edu")
                submitted = st.form_submit_button("Add student", icon=":material/person_add:", type="primary")
            if submitted:
                try:
                    new_id = add_student(
                        new_student_id,
                        new_name,
                        new_department,
                        int(new_semester),
                        new_email,
                    )
                except ValidationError as exc:
                    st.error(str(exc), icon=":material/error:")
                else:
                    st.session_state.demo_student_id = new_id
                    set_flash(f"Demo student {new_student_id.upper()} was added.")
                    st.rerun()

if faculty and edit_tab is not None:
    with edit_tab:
        all_students = list_students(include_inactive=True)
        if not all_students:
            empty_state("There are no student records to edit.")
        else:
            labels = {
                student["id"]: f"{student['student_id']} — {student['name']}"
                + ("" if student["is_active"] else " (inactive)")
                for student in all_students
            }
            ids = [student["id"] for student in all_students]
            edit_id = st.selectbox(
                "Student to edit",
                options=ids,
                format_func=lambda student_id: labels[student_id],
                key="student_edit_select",
            )
            edit_student = get_student(edit_id)
            if edit_student:
                with st.container(border=True):
                    st.subheader("Edit record", icon=":material/edit:")
                    status_badge("Active" if edit_student["is_active"] else "Inactive")
                    with st.form(f"edit_student_form_{edit_id}"):
                        left, right = st.columns(2)
                        with left:
                            edit_student_id = st.text_input("Student ID", value=edit_student["student_id"])
                            edit_name = st.text_input("Full name", value=edit_student["name"])
                            edit_department = st.text_input("Department", value=edit_student["department"])
                        with right:
                            edit_semester = st.number_input(
                                "Semester",
                                min_value=1,
                                max_value=8,
                                value=edit_student["semester"],
                                step=1,
                            )
                            edit_email = st.text_input("Email", value=edit_student["email"])
                        saved = st.form_submit_button("Save changes", icon=":material/save:", type="primary")
                    if saved:
                        try:
                            update_student(
                                edit_id,
                                edit_student_id,
                                edit_name,
                                edit_department,
                                int(edit_semester),
                                edit_email,
                            )
                        except ValidationError as exc:
                            st.error(str(exc), icon=":material/error:")
                        else:
                            set_flash("Student record updated.")
                            st.rerun()

                    if edit_student["is_active"]:
                        if st.button(
                            "Deactivate student",
                            icon=":material/person_off:",
                            key=f"deactivate_student_{edit_id}",
                        ):
                            try:
                                deactivate_student(edit_id)
                            except ValidationError as exc:
                                st.error(str(exc), icon=":material/error:")
                            else:
                                set_flash("Student deactivated. Historical records are preserved.", "warning")
                                st.rerun()
                    else:
                        if st.button(
                            "Reactivate student",
                            icon=":material/person_add:",
                            key=f"reactivate_student_{edit_id}",
                        ):
                            try:
                                reactivate_student(edit_id)
                            except ValidationError as exc:
                                st.error(str(exc), icon=":material/error:")
                            else:
                                set_flash("Student reactivated.")
                                st.rerun()
