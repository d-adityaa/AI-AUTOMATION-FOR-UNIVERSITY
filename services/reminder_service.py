"""Date-based in-app reminder generation with same-day deduplication."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from services.database import db_connection
from utils.validation import parse_date


def _insert_reminder(
    connection: Any,
    reminder_type: str,
    entity_type: str,
    entity_id: int,
    message: str,
    reminder_date: date,
) -> bool:
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO reminders
            (reminder_type, entity_type, entity_id, message, reminder_date)
        VALUES (?, ?, ?, ?, ?)
        """,
        (reminder_type, entity_type, int(entity_id), message, reminder_date.isoformat()),
    )
    return cursor.rowcount > 0


def generate_reminders(
    *,
    today: date | str | None = None,
    horizon_days: int = 7,
    db_path: str | Path | None = None,
) -> int:
    """Create reminders for due/overdue assignments and expiring notices.

    The UNIQUE constraint on (type, entity, date) makes repeated app reruns safe.
    """
    reference_day = parse_date(today or date.today(), "Reminder date")
    horizon = reference_day + timedelta(days=max(0, int(horizon_days)))
    inserted = 0
    with db_connection(db_path) as connection:
        due_assignments = connection.execute(
            """
            SELECT a.id, a.title, a.due_date, s.code AS subject_code
            FROM assignments a
            JOIN subjects s ON s.id = a.subject_id
            WHERE a.due_date >= ? AND a.due_date <= ?
            ORDER BY a.due_date
            """,
            (reference_day.isoformat(), horizon.isoformat()),
        ).fetchall()
        for assignment in due_assignments:
            due = date.fromisoformat(assignment["due_date"])
            days_left = (due - reference_day).days
            when = "today" if days_left == 0 else f"in {days_left} day(s)"
            message = (
                f"Assignment due {when}: {assignment['title']} "
                f"({assignment['subject_code']}) — due {assignment['due_date']}."
            )
            if _insert_reminder(
                connection,
                "assignment_due",
                "assignment",
                assignment["id"],
                message,
                reference_day,
            ):
                inserted += 1

        overdue_assignments = connection.execute(
            """
            SELECT a.id, a.title, a.due_date, s.code AS subject_code
            FROM assignments a
            JOIN subjects s ON s.id = a.subject_id
            WHERE a.due_date < ?
            ORDER BY a.due_date
            """,
            (reference_day.isoformat(),),
        ).fetchall()
        for assignment in overdue_assignments:
            message = (
                f"Overdue assignment: {assignment['title']} "
                f"({assignment['subject_code']}) was due {assignment['due_date']}."
            )
            if _insert_reminder(
                connection,
                "assignment_overdue",
                "assignment",
                assignment["id"],
                message,
                reference_day,
            ):
                inserted += 1

        expiring = connection.execute(
            """
            SELECT id, title, expiry_date
            FROM notices
            WHERE is_active = 1
              AND publish_date <= ?
              AND expiry_date IS NOT NULL
              AND expiry_date >= ?
              AND expiry_date <= ?
            ORDER BY expiry_date
            """,
            (reference_day.isoformat(), reference_day.isoformat(), horizon.isoformat()),
        ).fetchall()
        for notice in expiring:
            expiry = date.fromisoformat(notice["expiry_date"])
            days_left = (expiry - reference_day).days
            when = "today" if days_left == 0 else f"in {days_left} day(s)"
            message = f"Notice expires {when}: {notice['title']} — expires {notice['expiry_date']}."
            if _insert_reminder(
                connection,
                "notice_expiring",
                "notice",
                notice["id"],
                message,
                reference_day,
            ):
                inserted += 1
    return inserted


def list_reminders(
    *,
    reminder_date: date | str | None = None,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    parameters: list[Any] = []
    where = ""
    if reminder_date is not None:
        where = "WHERE reminder_date = ?"
        parameters.append(parse_date(reminder_date, "Reminder date").isoformat())
    with db_connection(db_path) as connection:
        rows = connection.execute(
            f"""
            SELECT * FROM reminders
            {where}
            ORDER BY
                CASE reminder_type
                    WHEN 'assignment_overdue' THEN 0
                    WHEN 'assignment_due' THEN 1
                    ELSE 2
                END,
                entity_id
            """,
            parameters,
        ).fetchall()
    return [
        {
            "id": row["id"],
            "reminder_type": row["reminder_type"],
            "entity_type": row["entity_type"],
            "entity_id": row["entity_id"],
            "message": row["message"],
            "reminder_date": row["reminder_date"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def reminder_counts(
    *,
    reminder_date: date | str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, int]:
    reminders = list_reminders(reminder_date=reminder_date or date.today(), db_path=db_path)
    counts = {"assignment_due": 0, "assignment_overdue": 0, "notice_expiring": 0, "Total": len(reminders)}
    for reminder in reminders:
        counts[reminder["reminder_type"]] += 1
    return counts
