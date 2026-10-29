"""Student CRUD and search operations."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from services.database import db_connection
from utils.validation import (
    ValidationError,
    require_text,
    validate_email,
    validate_semester,
    validate_student_id,
)


def _student_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "student_id": row["student_id"],
        "name": row["name"],
        "department": row["department"],
        "semester": row["semester"],
        "email": row["email"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
    }


def add_student(
    student_id: str,
    name: str,
    department: str,
    semester: int,
    email: str,
    *,
    db_path: str | Path | None = None,
) -> int:
    validated_id = validate_student_id(student_id)
    validated_name = require_text(name, "Name", min_length=2, max_length=100)
    validated_department = require_text(department, "Department", min_length=2, max_length=100)
    validated_semester = validate_semester(semester)
    validated_email = validate_email(email)
    try:
        with db_connection(db_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO students (student_id, name, department, semester, email)
                VALUES (?, ?, ?, ?, ?)
                """,
                (validated_id, validated_name, validated_department, validated_semester, validated_email),
            )
            return int(cursor.lastrowid)
    except sqlite3.IntegrityError as exc:
        if "students.student_id" in str(exc):
            raise ValidationError(f"Student ID {validated_id} already exists.") from exc
        raise ValidationError("The student record violates a database constraint.") from exc


def update_student(
    student_db_id: int,
    student_id: str,
    name: str,
    department: str,
    semester: int,
    email: str,
    *,
    db_path: str | Path | None = None,
) -> None:
    validated_id = validate_student_id(student_id)
    validated_name = require_text(name, "Name", min_length=2, max_length=100)
    validated_department = require_text(department, "Department", min_length=2, max_length=100)
    validated_semester = validate_semester(semester)
    validated_email = validate_email(email)
    try:
        with db_connection(db_path) as connection:
            cursor = connection.execute(
                """
                UPDATE students
                SET student_id = ?, name = ?, department = ?, semester = ?, email = ?
                WHERE id = ?
                """,
                (
                    validated_id,
                    validated_name,
                    validated_department,
                    validated_semester,
                    validated_email,
                    int(student_db_id),
                ),
            )
            if cursor.rowcount == 0:
                raise ValidationError("Student record not found.")
    except sqlite3.IntegrityError as exc:
        if "students.student_id" in str(exc):
            raise ValidationError(f"Student ID {validated_id} already exists.") from exc
        raise ValidationError("The student record violates a database constraint.") from exc


def set_student_active(student_db_id: int, active: bool, *, db_path: str | Path | None = None) -> None:
    with db_connection(db_path) as connection:
        cursor = connection.execute(
            "UPDATE students SET is_active = ? WHERE id = ?",
            (1 if active else 0, int(student_db_id)),
        )
        if cursor.rowcount == 0:
            raise ValidationError("Student record not found.")


def deactivate_student(student_db_id: int, *, db_path: str | Path | None = None) -> None:
    set_student_active(student_db_id, False, db_path=db_path)


def reactivate_student(student_db_id: int, *, db_path: str | Path | None = None) -> None:
    set_student_active(student_db_id, True, db_path=db_path)


def get_student(student_db_id: int, *, db_path: str | Path | None = None) -> dict[str, Any] | None:
    with db_connection(db_path) as connection:
        row = connection.execute("SELECT * FROM students WHERE id = ?", (int(student_db_id),)).fetchone()
    return _student_dict(row) if row else None


def get_student_by_student_id(student_id: str, *, db_path: str | Path | None = None) -> dict[str, Any] | None:
    validated_id = validate_student_id(student_id)
    with db_connection(db_path) as connection:
        row = connection.execute("SELECT * FROM students WHERE student_id = ?", (validated_id,)).fetchone()
    return _student_dict(row) if row else None


def list_students(
    *,
    search: str = "",
    department: str | None = None,
    semester: int | None = None,
    include_inactive: bool = False,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    parameters: list[Any] = []
    if not include_inactive:
        clauses.append("is_active = 1")
    if department:
        clauses.append("department = ?")
        parameters.append(department)
    if semester is not None:
        clauses.append("semester = ?")
        parameters.append(validate_semester(semester))
    if search and search.strip():
        term = f"%{search.strip()}%"
        clauses.append("(student_id LIKE ? OR name LIKE ? OR email LIKE ? OR department LIKE ?)")
        parameters.extend([term, term, term, term])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"SELECT * FROM students {where} ORDER BY student_id"
    with db_connection(db_path) as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [_student_dict(row) for row in rows]


def list_departments(*, db_path: str | Path | None = None) -> list[str]:
    with db_connection(db_path) as connection:
        rows = connection.execute(
            "SELECT DISTINCT department FROM students ORDER BY department"
        ).fetchall()
    return [row["department"] for row in rows]


def count_students(*, active_only: bool = True, db_path: str | Path | None = None) -> int:
    where = "WHERE is_active = 1" if active_only else ""
    with db_connection(db_path) as connection:
        row = connection.execute(f"SELECT COUNT(*) AS count FROM students {where}").fetchone()
    return int(row["count"])
