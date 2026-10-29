"""Weekly timetable management and conflict validation."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from services.database import db_connection
from utils.validation import (
    ValidationError,
    require_text,
    validate_semester,
    validate_time_range,
    validate_weekday,
)

WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _entry_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "weekday": row["weekday"],
        "weekday_name": WEEKDAY_NAMES[row["weekday"]],
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "subject_id": row["subject_id"],
        "subject_code": row["subject_code"],
        "subject_name": row["subject_name"],
        "room": row["room"],
        "faculty_name": row["faculty_name"],
        "semester": row["semester"],
    }


def _check_conflict(
    connection: Any,
    weekday: int,
    start_time: str,
    end_time: str,
    semester: int,
    room: str,
    faculty_name: str,
    exclude_id: int | None = None,
) -> None:
    parameters: list[Any] = [
        weekday,
        end_time,
        start_time,
        semester,
        room.lower(),
        faculty_name.lower(),
    ]
    exclude_clause = ""
    if exclude_id is not None:
        exclude_clause = "AND t.id <> ?"
        parameters.append(int(exclude_id))
    conflict = connection.execute(
        f"""
        SELECT t.*, s.code AS subject_code
        FROM timetable t
        JOIN subjects s ON s.id = t.subject_id
        WHERE t.weekday = ?
          AND t.start_time < ?
          AND t.end_time > ?
          AND (
              t.semester = ?
              OR LOWER(t.room) = ?
              OR LOWER(t.faculty_name) = ?
          )
          {exclude_clause}
        LIMIT 1
        """,
        parameters,
    ).fetchone()
    if conflict:
        raise ValidationError(
            "Timetable conflict: this time overlaps an existing entry for the same semester, "
            f"room, or faculty member ({WEEKDAY_NAMES[conflict['weekday']]} "
            f"{conflict['start_time']}-{conflict['end_time']}, {conflict['subject_code']})."
        )


def add_entry(
    weekday: int,
    start_time: str,
    end_time: str,
    subject_id: int,
    room: str,
    faculty_name: str,
    semester: int,
    *,
    db_path: str | Path | None = None,
) -> int:
    validated_weekday = validate_weekday(weekday)
    validated_start, validated_end = validate_time_range(start_time, end_time)
    validated_room = require_text(room, "Room", min_length=1, max_length=50)
    validated_faculty = require_text(faculty_name, "Faculty name", min_length=2, max_length=100)
    validated_semester = validate_semester(semester)
    with db_connection(db_path) as connection:
        if not connection.execute("SELECT id FROM subjects WHERE id = ?", (int(subject_id),)).fetchone():
            raise ValidationError("Selected subject was not found.")
        _check_conflict(
            connection,
            validated_weekday,
            validated_start,
            validated_end,
            validated_semester,
            validated_room,
            validated_faculty,
        )
        cursor = connection.execute(
            """
            INSERT INTO timetable (weekday, start_time, end_time, subject_id, room, faculty_name, semester)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                validated_weekday,
                validated_start,
                validated_end,
                int(subject_id),
                validated_room,
                validated_faculty,
                validated_semester,
            ),
        )
        return int(cursor.lastrowid)


def update_entry(
    entry_id: int,
    weekday: int,
    start_time: str,
    end_time: str,
    subject_id: int,
    room: str,
    faculty_name: str,
    semester: int,
    *,
    db_path: str | Path | None = None,
) -> None:
    validated_weekday = validate_weekday(weekday)
    validated_start, validated_end = validate_time_range(start_time, end_time)
    validated_room = require_text(room, "Room", min_length=1, max_length=50)
    validated_faculty = require_text(faculty_name, "Faculty name", min_length=2, max_length=100)
    validated_semester = validate_semester(semester)
    with db_connection(db_path) as connection:
        if not connection.execute("SELECT id FROM subjects WHERE id = ?", (int(subject_id),)).fetchone():
            raise ValidationError("Selected subject was not found.")
        _check_conflict(
            connection,
            validated_weekday,
            validated_start,
            validated_end,
            validated_semester,
            validated_room,
            validated_faculty,
            exclude_id=int(entry_id),
        )
        cursor = connection.execute(
            """
            UPDATE timetable
            SET weekday = ?, start_time = ?, end_time = ?, subject_id = ?,
                room = ?, faculty_name = ?, semester = ?
            WHERE id = ?
            """,
            (
                validated_weekday,
                validated_start,
                validated_end,
                int(subject_id),
                validated_room,
                validated_faculty,
                validated_semester,
                int(entry_id),
            ),
        )
        if cursor.rowcount == 0:
            raise ValidationError("Timetable entry was not found.")


def delete_entry(entry_id: int, *, db_path: str | Path | None = None) -> None:
    with db_connection(db_path) as connection:
        cursor = connection.execute("DELETE FROM timetable WHERE id = ?", (int(entry_id),))
        if cursor.rowcount == 0:
            raise ValidationError("Timetable entry was not found.")


def get_entry(entry_id: int, *, db_path: str | Path | None = None) -> dict[str, Any] | None:
    with db_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT t.*, s.code AS subject_code, s.name AS subject_name
            FROM timetable t
            JOIN subjects s ON s.id = t.subject_id
            WHERE t.id = ?
            """,
            (int(entry_id),),
        ).fetchone()
    return _entry_dict(row) if row else None


def list_entries(
    *,
    semester: int | None = None,
    subject_id: int | None = None,
    weekday: int | None = None,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    parameters: list[Any] = []
    if semester is not None:
        clauses.append("t.semester = ?")
        parameters.append(validate_semester(semester))
    if subject_id is not None:
        clauses.append("t.subject_id = ?")
        parameters.append(int(subject_id))
    if weekday is not None:
        clauses.append("t.weekday = ?")
        parameters.append(validate_weekday(weekday))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with db_connection(db_path) as connection:
        rows = connection.execute(
            f"""
            SELECT t.*, s.code AS subject_code, s.name AS subject_name
            FROM timetable t
            JOIN subjects s ON s.id = t.subject_id
            {where}
            ORDER BY t.weekday, t.start_time
            """,
            parameters,
        ).fetchall()
    return [_entry_dict(row) for row in rows]


def today_entries(
    day: date | None = None, *, db_path: str | Path | None = None
) -> list[dict[str, Any]]:
    reference_day = day or date.today()
    return list_entries(weekday=reference_day.weekday(), db_path=db_path)


def count_today_entries(day: date | None = None, *, db_path: str | Path | None = None) -> int:
    return len(today_entries(day, db_path=db_path))
