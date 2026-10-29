"""College notice board operations and notice search."""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from services.database import db_connection
from utils.validation import (
    ValidationError,
    require_text,
    validate_choice,
    validate_notice_dates,
)

NOTICE_CATEGORIES = ("Academic", "Examination", "Event", "Holiday", "General")


def _notice_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "content": row["content"],
        "category": row["category"],
        "publish_date": row["publish_date"],
        "expiry_date": row["expiry_date"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
    }


def add_notice(
    title: str,
    content: str,
    category: str,
    publish_date: date | str,
    expiry_date: date | str | None = None,
    *,
    db_path: str | Path | None = None,
) -> int:
    validated_title = require_text(title, "Notice title", min_length=3, max_length=180)
    validated_content = require_text(content, "Notice content", min_length=5, max_length=8000)
    validated_category = validate_choice(category, NOTICE_CATEGORIES, "Notice category")
    published, expiry = validate_notice_dates(publish_date, expiry_date)
    with db_connection(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO notices (title, content, category, publish_date, expiry_date, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (
                validated_title,
                validated_content,
                validated_category,
                published.isoformat(),
                expiry.isoformat() if expiry else None,
            ),
        )
        return int(cursor.lastrowid)


def update_notice(
    notice_id: int,
    title: str,
    content: str,
    category: str,
    publish_date: date | str,
    expiry_date: date | str | None = None,
    *,
    db_path: str | Path | None = None,
) -> None:
    validated_title = require_text(title, "Notice title", min_length=3, max_length=180)
    validated_content = require_text(content, "Notice content", min_length=5, max_length=8000)
    validated_category = validate_choice(category, NOTICE_CATEGORIES, "Notice category")
    published, expiry = validate_notice_dates(publish_date, expiry_date)
    with db_connection(db_path) as connection:
        cursor = connection.execute(
            """
            UPDATE notices
            SET title = ?, content = ?, category = ?, publish_date = ?, expiry_date = ?
            WHERE id = ?
            """,
            (
                validated_title,
                validated_content,
                validated_category,
                published.isoformat(),
                expiry.isoformat() if expiry else None,
                int(notice_id),
            ),
        )
        if cursor.rowcount == 0:
            raise ValidationError("Notice was not found.")


def set_notice_active(notice_id: int, active: bool, *, db_path: str | Path | None = None) -> None:
    with db_connection(db_path) as connection:
        cursor = connection.execute(
            "UPDATE notices SET is_active = ? WHERE id = ?",
            (1 if active else 0, int(notice_id)),
        )
        if cursor.rowcount == 0:
            raise ValidationError("Notice was not found.")


def deactivate_notice(notice_id: int, *, db_path: str | Path | None = None) -> None:
    set_notice_active(notice_id, False, db_path=db_path)


def reactivate_notice(notice_id: int, *, db_path: str | Path | None = None) -> None:
    set_notice_active(notice_id, True, db_path=db_path)


def get_notice(notice_id: int, *, db_path: str | Path | None = None) -> dict[str, Any] | None:
    with db_connection(db_path) as connection:
        row = connection.execute("SELECT * FROM notices WHERE id = ?", (int(notice_id),)).fetchone()
    return _notice_dict(row) if row else None


def list_notices(
    *,
    search: str = "",
    category: str | None = None,
    current_only: bool = True,
    include_inactive: bool = False,
    today: date | None = None,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    reference_day = today or date.today()
    clauses: list[str] = []
    parameters: list[Any] = []
    if not include_inactive:
        clauses.append("is_active = 1")
    if current_only:
        clauses.append("publish_date <= ?")
        parameters.append(reference_day.isoformat())
        clauses.append("(expiry_date IS NULL OR expiry_date >= ?)")
        parameters.append(reference_day.isoformat())
    if category:
        clauses.append("category = ?")
        parameters.append(validate_choice(category, NOTICE_CATEGORIES, "Notice category"))
    if search and search.strip():
        term = f"%{search.strip()}%"
        clauses.append("(title LIKE ? OR content LIKE ? OR category LIKE ?)")
        parameters.extend([term, term, term])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with db_connection(db_path) as connection:
        rows = connection.execute(
            f"""
            SELECT * FROM notices
            {where}
            ORDER BY publish_date DESC, id DESC
            """,
            parameters,
        ).fetchall()
    return [_notice_dict(row) for row in rows]


def recent_notices(
    limit: int = 4,
    *,
    today: date | None = None,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    notices = list_notices(today=today, db_path=db_path)
    return notices[: max(0, int(limit))]


def expiring_notices(
    *, days: int = 7, today: date | None = None, db_path: str | Path | None = None
) -> list[dict[str, Any]]:
    reference_day = today or date.today()
    horizon = reference_day + timedelta(days=max(0, int(days)))
    notices = list_notices(today=reference_day, db_path=db_path)
    results = []
    for notice in notices:
        if not notice["expiry_date"]:
            continue
        expiry = date.fromisoformat(notice["expiry_date"])
        if reference_day <= expiry <= horizon:
            results.append(notice)
    return results


def count_current_notices(*, today: date | None = None, db_path: str | Path | None = None) -> int:
    return len(list_notices(today=today, db_path=db_path))


def basic_extractive_summary(content: str, max_sentences: int = 3, max_chars: int = 600) -> str:
    """Return a clearly non-AI extractive summary: the first few sentences."""
    cleaned = re.sub(r"\s+", " ", str(content or "")).strip()
    if not cleaned:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    summary = " ".join(sentences[: max(1, int(max_sentences))]).strip()
    if len(summary) > max_chars:
        summary = summary[: max_chars - 1].rstrip() + "…"
    return summary
