"""Allowlisted, typed, read-only tools available to the AI assistant."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable

from services import assignment_service, attendance_service, notice_service, timetable_service
from services.student_service import get_student_by_student_id
from utils.validation import ValidationError, parse_date, validate_semester


class ToolError(ValidationError):
    """Raised when an AI tool is unknown or receives invalid arguments."""


def _serialize_assignment(assignment: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": assignment["title"],
        "subject": f"{assignment['subject_code']} — {assignment['subject_name']}",
        "publish_date": assignment["publish_date"],
        "due_date": assignment["due_date"],
        "status": assignment["status"],
        "days_until_due": assignment["days_until_due"],
    }


def tool_list_due_assignments(
    start_date: str,
    end_date: str,
    student_db_id: int | None = None,
    semester: int | None = None,
    *,
    db_path: str | Path | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Return assignments whose due date falls between two ISO dates."""
    start = parse_date(start_date, "Start date")
    end = parse_date(end_date, "End date")
    if end < start:
        raise ToolError("End date cannot be earlier than start date.")
    reference_day = today or date.today()
    validated_semester = validate_semester(semester) if semester is not None else None
    assignments = assignment_service.list_assignments(
        student_db_id=student_db_id,
        semester=validated_semester,
        today=reference_day,
        db_path=db_path,
    )
    results = []
    for assignment in assignments:
        due = date.fromisoformat(assignment["due_date"])
        if start <= due <= end:
            if student_db_id is not None and assignment["submitted_at"]:
                continue
            results.append(_serialize_assignment(assignment))
    return {
        "tool": "list_due_assignments",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "records": results,
        "message": f"Found {len(results)} assignment(s) due between {start.isoformat()} and {end.isoformat()}.",
    }


def tool_list_overdue_assignments(
    student_db_id: int | None = None,
    semester: int | None = None,
    *,
    db_path: str | Path | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Return assignments that are past their due date and not submitted."""
    reference_day = today or date.today()
    validated_semester = validate_semester(semester) if semester is not None else None
    assignments = assignment_service.overdue_assignments(
        student_db_id=student_db_id,
        semester=validated_semester,
        today=reference_day,
        db_path=db_path,
    )
    records = [_serialize_assignment(item) for item in assignments]
    return {
        "tool": "list_overdue_assignments",
        "records": records,
        "message": f"Found {len(records)} overdue assignment(s).",
    }


def tool_get_attendance_summary(
    student_id: str,
    *,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return attendance totals and percentage for a public student ID."""
    student = get_student_by_student_id(student_id, db_path=db_path)
    if student is None:
        return {
            "tool": "get_attendance_summary",
            "student_id": str(student_id).upper(),
            "records": [],
            "message": f"No active or inactive student with ID {str(student_id).upper()} exists in the local database.",
        }
    summary = attendance_service.attendance_summary(student_db_id=student["id"], db_path=db_path)
    return {
        "tool": "get_attendance_summary",
        "student_id": student["student_id"],
        "student_name": student["name"],
        "semester": student["semester"],
        "present": summary["present"],
        "late": summary["late"],
        "absent": summary["absent"],
        "total": summary["total"],
        "percentage": summary["percentage"],
        "records": [],
        "message": (
            f"{student['student_id']} has {summary['percentage']}% attendance "
            f"across {summary['total']} stored record(s)."
        ),
    }


def tool_get_timetable_for_day(
    day: str | None = None,
    semester: int | None = None,
    *,
    db_path: str | Path | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Return timetable entries for a date (default today), optionally for a semester."""
    reference_day = parse_date(day, "Timetable date") if day else (today or date.today())
    validated_semester = validate_semester(semester) if semester is not None else None
    entries = timetable_service.list_entries(
        semester=validated_semester,
        weekday=reference_day.weekday(),
        db_path=db_path,
    )
    records = [
        {
            "weekday": entry["weekday_name"],
            "start_time": entry["start_time"],
            "end_time": entry["end_time"],
            "subject": f"{entry['subject_code']} — {entry['subject_name']}",
            "room": entry["room"],
            "faculty": entry["faculty_name"],
            "semester": entry["semester"],
        }
        for entry in entries
    ]
    return {
        "tool": "get_timetable_for_day",
        "day": reference_day.isoformat(),
        "semester": validated_semester,
        "records": records,
        "message": f"Found {len(records)} timetable entr{'y' if len(records) == 1 else 'ies'} for {reference_day.isoformat()}.",
    }


def tool_list_current_notices(
    category: str | None = None,
    limit: int = 5,
    *,
    db_path: str | Path | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Return current notices, optionally filtered by category."""
    validated_category = category if category else None
    if validated_category and validated_category not in notice_service.NOTICE_CATEGORIES:
        raise ToolError(f"Category must be one of: {', '.join(notice_service.NOTICE_CATEGORIES)}.")
    try:
        limit_value = max(1, min(20, int(limit)))
    except (TypeError, ValueError) as exc:
        raise ToolError("Limit must be a whole number.") from exc
    notices = notice_service.list_notices(
        category=validated_category,
        today=today or date.today(),
        db_path=db_path,
    )[:limit_value]
    records = [
        {
            "id": notice["id"],
            "title": notice["title"],
            "category": notice["category"],
            "publish_date": notice["publish_date"],
            "expiry_date": notice["expiry_date"],
            "content": notice["content"],
        }
        for notice in notices
    ]
    return {
        "tool": "list_current_notices",
        "category": validated_category,
        "records": records,
        "message": f"Found {len(records)} current notice(s).",
    }


def tool_get_assignment_submission_stats(
    assignment_id: int,
    *,
    db_path: str | Path | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Return aggregate submission counts for one assignment."""
    try:
        identifier = int(assignment_id)
    except (TypeError, ValueError) as exc:
        raise ToolError("Assignment ID must be a whole number.") from exc
    stats = assignment_service.submission_stats_for_assignment(
        identifier, today=today, db_path=db_path
    )
    return {
        "tool": "get_assignment_submission_stats",
        "assignment_id": identifier,
        "counts": stats,
        "records": [],
        "message": f"Submission counts: {stats}.",
    }


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    func: Callable[..., dict[str, Any]]


ALLOWED_TOOLS: dict[str, ToolSpec] = {
    spec.name: spec
    for spec in (
        ToolSpec(
            "list_due_assignments",
            "List assignments due between two ISO dates.",
            tool_list_due_assignments,
        ),
        ToolSpec(
            "list_overdue_assignments",
            "List past-due, unsubmitted assignments.",
            tool_list_overdue_assignments,
        ),
        ToolSpec(
            "get_attendance_summary",
            "Read attendance totals for one public student ID.",
            tool_get_attendance_summary,
        ),
        ToolSpec(
            "get_timetable_for_day",
            "Read the timetable for one date and optional semester.",
            tool_get_timetable_for_day,
        ),
        ToolSpec(
            "list_current_notices",
            "Read current notice-board records.",
            tool_list_current_notices,
        ),
        ToolSpec(
            "get_assignment_submission_stats",
            "Read aggregate submission counts for an assignment.",
            tool_get_assignment_submission_stats,
        ),
    )
}


def call_tool(name: str, **kwargs: Any) -> dict[str, Any]:
    """Dispatch a validated read-only tool call by allowlisted name."""
    if name not in ALLOWED_TOOLS:
        raise ToolError(f"Tool {name!r} is not allowlisted.")
    spec = ALLOWED_TOOLS[name]
    try:
        signature = inspect.signature(spec.func)
        signature.bind(**kwargs)
    except TypeError as exc:
        raise ToolError(f"Invalid arguments for tool {name!r}.") from exc
    return spec.func(**kwargs)
