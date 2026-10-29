"""Assignment creation, submission tracking, and deadline calculations."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from services.database import db_connection
from services.student_service import get_student
from utils.validation import (
    ValidationError,
    parse_date,
    require_text,
    validate_assignment_dates,
    validate_choice,
    validate_semester,
)

ASSIGNMENT_STATUSES = ("Pending", "Submitted", "Late", "Overdue")


def _assignment_dict(row: sqlite3.Row, submission: sqlite3.Row | None, today: date) -> dict[str, Any]:
    due = date.fromisoformat(row["due_date"])
    submitted_at = submission["submitted_at"] if submission else None
    if submission:
        status = submission["status"]
    elif due < today:
        status = "Overdue"
    else:
        status = "Pending"
    return {
        "id": row["id"],
        "title": row["title"],
        "subject_id": row["subject_id"],
        "subject_code": row["subject_code"],
        "subject_name": row["subject_name"],
        "semester": row["semester"],
        "description": row["description"],
        "publish_date": row["publish_date"],
        "due_date": row["due_date"],
        "created_at": row["created_at"],
        "submitted_at": submitted_at,
        "status": status,
        "days_until_due": (due - today).days,
        "is_overdue": status == "Overdue",
    }


def create_assignment(
    title: str,
    subject_id: int,
    description: str,
    publish_date: date | str,
    due_date: date | str,
    *,
    db_path: str | Path | None = None,
) -> int:
    validated_title = require_text(title, "Assignment title", min_length=3, max_length=160)
    validated_description = require_text(
        description, "Description", min_length=3, max_length=4000
    )
    published, due = validate_assignment_dates(publish_date, due_date)
    with db_connection(db_path) as connection:
        subject = connection.execute("SELECT id FROM subjects WHERE id = ?", (int(subject_id),)).fetchone()
        if not subject:
            raise ValidationError("Selected subject was not found.")
        cursor = connection.execute(
            """
            INSERT INTO assignments (title, subject_id, description, publish_date, due_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            (validated_title, int(subject_id), validated_description, published.isoformat(), due.isoformat()),
        )
        return int(cursor.lastrowid)


def get_assignment(
    assignment_id: int,
    *,
    student_db_id: int | None = None,
    today: date | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any] | None:
    reference_day = today or date.today()
    with db_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT a.*, s.code AS subject_code, s.name AS subject_name, s.semester
            FROM assignments a
            JOIN subjects s ON s.id = a.subject_id
            WHERE a.id = ?
            """,
            (int(assignment_id),),
        ).fetchone()
        if not row:
            return None
        submission = None
        if student_db_id is not None:
            submission = connection.execute(
                """
                SELECT * FROM assignment_submissions
                WHERE assignment_id = ? AND student_id = ?
                """,
                (int(assignment_id), int(student_db_id)),
            ).fetchone()
    return _assignment_dict(row, submission, reference_day)


def list_assignments(
    *,
    student_db_id: int | None = None,
    subject_id: int | None = None,
    semester: int | None = None,
    status_filter: str | None = None,
    today: date | None = None,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    reference_day = today or date.today()
    clauses: list[str] = []
    parameters: list[Any] = []
    if subject_id is not None:
        clauses.append("a.subject_id = ?")
        parameters.append(int(subject_id))
    if semester is not None:
        clauses.append("s.semester = ?")
        parameters.append(validate_semester(semester))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with db_connection(db_path) as connection:
        rows = connection.execute(
            f"""
            SELECT a.*, s.code AS subject_code, s.name AS subject_name, s.semester
            FROM assignments a
            JOIN subjects s ON s.id = a.subject_id
            {where}
            ORDER BY a.due_date, a.title
            """,
            parameters,
        ).fetchall()
        submissions: dict[int, sqlite3.Row] = {}
        if student_db_id is not None:
            submission_rows = connection.execute(
                "SELECT * FROM assignment_submissions WHERE student_id = ?",
                (int(student_db_id),),
            ).fetchall()
            submissions = {row["assignment_id"]: row for row in submission_rows}

    assignments = [
        _assignment_dict(row, submissions.get(row["id"]), reference_day)
        for row in rows
    ]
    if status_filter:
        if status_filter == "All":
            return assignments
        validated_status = validate_choice(status_filter, ASSIGNMENT_STATUSES, "Assignment status")
        assignments = [item for item in assignments if item["status"] == validated_status]
    return assignments


def mark_submitted(
    assignment_id: int,
    student_db_id: int,
    *,
    submitted_date: date | str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    assignment = get_assignment(assignment_id, db_path=db_path)
    if assignment is None:
        raise ValidationError("Assignment was not found.")
    student = get_student(student_db_id, db_path=db_path)
    if student is None or not student["is_active"]:
        raise ValidationError("Selected student was not found or is inactive.")

    submitted_day = parse_date(submitted_date or date.today(), "Submission date")
    due_day = date.fromisoformat(assignment["due_date"])
    status = "Late" if submitted_day > due_day else "Submitted"
    timestamp = (
        f"{submitted_day.isoformat()} {datetime.now().strftime('%H:%M:%S')}"
    )
    try:
        with db_connection(db_path) as connection:
            connection.execute(
                """
                INSERT INTO assignment_submissions (assignment_id, student_id, submitted_at, status)
                VALUES (?, ?, ?, ?)
                """,
                (int(assignment_id), int(student_db_id), timestamp, status),
            )
    except sqlite3.IntegrityError as exc:
        raise ValidationError("This demo student has already marked the assignment as submitted.") from exc
    return {
        "assignment_id": int(assignment_id),
        "student_id": int(student_db_id),
        "submitted_at": timestamp,
        "status": status,
    }


def student_assignment_stats(
    student_db_id: int,
    *,
    semester: int | None = None,
    today: date | None = None,
    db_path: str | Path | None = None,
) -> dict[str, int]:
    assignments = list_assignments(
        student_db_id=student_db_id,
        semester=semester,
        today=today,
        db_path=db_path,
    )
    counts = {"Pending": 0, "Submitted": 0, "Late": 0, "Overdue": 0, "Total": len(assignments)}
    for assignment in assignments:
        counts[assignment["status"]] += 1
    return counts


def pending_count(
    student_db_id: int,
    *,
    semester: int | None = None,
    today: date | None = None,
    db_path: str | Path | None = None,
) -> int:
    return len(
        list_assignments(
            student_db_id=student_db_id,
            semester=semester,
            status_filter="Pending",
            today=today,
            db_path=db_path,
        )
    )


def upcoming_deadlines(
    *,
    days: int = 7,
    student_db_id: int | None = None,
    semester: int | None = None,
    today: date | None = None,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    reference_day = today or date.today()
    horizon = reference_day + timedelta(days=max(0, int(days)))
    assignments = list_assignments(
        student_db_id=student_db_id,
        semester=semester,
        today=reference_day,
        db_path=db_path,
    )
    results = []
    for assignment in assignments:
        due = date.fromisoformat(assignment["due_date"])
        if reference_day <= due <= horizon:
            if student_db_id is not None and assignment["submitted_at"]:
                continue
            results.append(assignment)
    return results


def overdue_assignments(
    *,
    student_db_id: int | None = None,
    semester: int | None = None,
    today: date | None = None,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    return list_assignments(
        student_db_id=student_db_id,
        semester=semester,
        status_filter="Overdue",
        today=today,
        db_path=db_path,
    )


def submission_stats_for_assignment(
    assignment_id: int,
    *,
    today: date | None = None,
    db_path: str | Path | None = None,
) -> dict[str, int]:
    reference_day = today or date.today()
    assignment = get_assignment(assignment_id, today=reference_day, db_path=db_path)
    if assignment is None:
        raise ValidationError("Assignment was not found.")
    with db_connection(db_path) as connection:
        student_rows = connection.execute(
            "SELECT id FROM students WHERE is_active = 1 AND semester = ?",
            (assignment["semester"],),
        ).fetchall()
        submission_rows = connection.execute(
            "SELECT student_id, status FROM assignment_submissions WHERE assignment_id = ?",
            (int(assignment_id),),
        ).fetchall()
    submissions = {row["student_id"]: row["status"] for row in submission_rows}
    due = date.fromisoformat(assignment["due_date"])
    counts = {"Submitted": 0, "Late": 0, "Pending": 0, "Overdue": 0}
    for student in student_rows:
        status = submissions.get(student["id"])
        if status:
            counts[status] += 1
        elif due < reference_day:
            counts["Overdue"] += 1
        else:
            counts["Pending"] += 1
    counts["Total"] = len(student_rows)
    return counts
