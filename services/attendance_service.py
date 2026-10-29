"""Attendance recording, filtering, and percentage calculations."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Iterable

from services.database import db_connection
from utils.validation import (
    ValidationError,
    parse_date,
    validate_choice,
    validate_semester,
)

ATTENDANCE_STATUSES = ("Present", "Absent", "Late")


def list_subjects(*, semester: int | None = None, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    parameters: list[Any] = []
    where = ""
    if semester is not None:
        where = "WHERE semester = ?"
        parameters.append(validate_semester(semester))
    with db_connection(db_path) as connection:
        rows = connection.execute(
            f"SELECT * FROM subjects {where} ORDER BY semester, code",
            parameters,
        ).fetchall()
    return [
        {
            "id": row["id"],
            "code": row["code"],
            "name": row["name"],
            "department": row["department"],
            "semester": row["semester"],
        }
        for row in rows
    ]


def get_subject(subject_id: int, *, db_path: str | Path | None = None) -> dict[str, Any] | None:
    with db_connection(db_path) as connection:
        row = connection.execute("SELECT * FROM subjects WHERE id = ?", (int(subject_id),)).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "code": row["code"],
        "name": row["name"],
        "department": row["department"],
        "semester": row["semester"],
    }


def students_for_semester(semester: int, *, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    validated_semester = validate_semester(semester)
    with db_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, student_id, name, semester
            FROM students
            WHERE is_active = 1 AND semester = ?
            ORDER BY student_id
            """,
            (validated_semester,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "student_id": row["student_id"],
            "name": row["name"],
            "semester": row["semester"],
        }
        for row in rows
    ]


def save_attendance_bulk(
    attendance_date: date | str,
    subject_id: int,
    records: Iterable[tuple[int, str]],
    *,
    db_path: str | Path | None = None,
) -> int:
    """Insert or explicitly update attendance for a date and subject."""
    parsed_date = parse_date(attendance_date, "Attendance date")
    records_list = list(records)
    if not records_list:
        raise ValidationError("At least one attendance record is required.")
    if get_subject(subject_id, db_path=db_path) is None:
        raise ValidationError("Selected subject was not found.")

    validated: list[tuple[int, str]] = []
    for student_db_id, status in records_list:
        try:
            student_id = int(student_db_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError("Each attendance record needs a valid student.") from exc
        validated.append((student_id, validate_choice(status, ATTENDANCE_STATUSES, "Attendance status")))

    with db_connection(db_path) as connection:
        student_rows = connection.execute(
            f"SELECT id, is_active FROM students WHERE id IN ({','.join('?' for _ in validated)})",
            [student_id for student_id, _ in validated],
        ).fetchall()
        active_ids = {row["id"] for row in student_rows if row["is_active"]}
        missing = [student_id for student_id, _ in validated if student_id not in active_ids]
        if missing:
            raise ValidationError("One or more selected students are missing or inactive.")

        for student_db_id, status in validated:
            connection.execute(
                """
                INSERT INTO attendance (student_id, subject_id, attendance_date, status)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(student_id, subject_id, attendance_date)
                DO UPDATE SET status = excluded.status, recorded_at = datetime('now')
                """,
                (student_db_id, int(subject_id), parsed_date.isoformat(), status),
            )
    return len(validated)


def get_attendance_map(
    attendance_date: date | str,
    subject_id: int,
    semester: int,
    *,
    db_path: str | Path | None = None,
) -> dict[int, str]:
    parsed_date = parse_date(attendance_date, "Attendance date")
    with db_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT a.student_id, a.status
            FROM attendance a
            JOIN students s ON s.id = a.student_id
            WHERE a.attendance_date = ? AND a.subject_id = ? AND s.semester = ?
            """,
            (parsed_date.isoformat(), int(subject_id), validate_semester(semester)),
        ).fetchall()
    return {row["student_id"]: row["status"] for row in rows}


def list_attendance(
    *,
    student_db_id: int | None = None,
    subject_id: int | None = None,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    parameters: list[Any] = []
    if student_db_id is not None:
        clauses.append("a.student_id = ?")
        parameters.append(int(student_db_id))
    if subject_id is not None:
        clauses.append("a.subject_id = ?")
        parameters.append(int(subject_id))
    if start_date is not None:
        clauses.append("a.attendance_date >= ?")
        parameters.append(parse_date(start_date, "Start date").isoformat())
    if end_date is not None:
        clauses.append("a.attendance_date <= ?")
        parameters.append(parse_date(end_date, "End date").isoformat())
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"""
        SELECT a.id, a.attendance_date, a.status, a.recorded_at,
               s.student_id, s.name AS student_name, s.semester,
               sub.code AS subject_code, sub.name AS subject_name, sub.id AS subject_id
        FROM attendance a
        JOIN students s ON s.id = a.student_id
        JOIN subjects sub ON sub.id = a.subject_id
        {where}
        ORDER BY a.attendance_date DESC, s.student_id, sub.code
    """
    with db_connection(db_path) as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [
        {
            "id": row["id"],
            "attendance_date": row["attendance_date"],
            "status": row["status"],
            "recorded_at": row["recorded_at"],
            "student_id": row["student_id"],
            "student_name": row["student_name"],
            "semester": row["semester"],
            "subject_code": row["subject_code"],
            "subject_name": row["subject_name"],
            "subject_id": row["subject_id"],
        }
        for row in rows
    ]


def attendance_summary(
    *,
    student_db_id: int | None = None,
    subject_id: int | None = None,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    records = list_attendance(
        student_db_id=student_db_id,
        subject_id=subject_id,
        start_date=start_date,
        end_date=end_date,
        db_path=db_path,
    )
    present = sum(1 for record in records if record["status"] == "Present")
    late = sum(1 for record in records if record["status"] == "Late")
    absent = sum(1 for record in records if record["status"] == "Absent")
    total = len(records)
    attended = present + late
    percentage = round((attended / total) * 100, 1) if total else 0.0
    return {
        "present": present,
        "late": late,
        "absent": absent,
        "total": total,
        "attended": attended,
        "percentage": percentage,
        "records": records,
    }


def today_summary(
    attendance_date: date | str | None = None,
    *,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    parsed_date = parse_date(attendance_date or date.today(), "Attendance date")
    records = list_attendance(start_date=parsed_date, end_date=parsed_date, db_path=db_path)
    present = sum(1 for record in records if record["status"] == "Present")
    late = sum(1 for record in records if record["status"] == "Late")
    absent = sum(1 for record in records if record["status"] == "Absent")
    total = len(records)
    percentage = round(((present + late) / total) * 100, 1) if total else 0.0
    return {
        "date": parsed_date.isoformat(),
        "present": present,
        "late": late,
        "absent": absent,
        "total": total,
        "percentage": percentage,
    }
