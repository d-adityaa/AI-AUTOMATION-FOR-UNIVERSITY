"""Reusable validation helpers for forms, services, and AI tools."""

from __future__ import annotations

import re
from datetime import date, datetime, time
from typing import Any

STUDENT_ID_PATTERN = re.compile(r"^[A-Z0-9-]{3,20}$")
EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class ValidationError(ValueError):
    """Raised when user input or service arguments are invalid."""


def require_text(value: Any, field: str, *, min_length: int = 1, max_length: int = 500) -> str:
    text = str(value or "").strip()
    if len(text) < min_length:
        raise ValidationError(f"{field} is required.")
    if len(text) > max_length:
        raise ValidationError(f"{field} must be {max_length} characters or fewer.")
    return text


def optional_text(value: Any, field: str, *, max_length: int = 2000) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) > max_length:
        raise ValidationError(f"{field} must be {max_length} characters or fewer.")
    return text


def validate_student_id(value: Any) -> str:
    student_id = require_text(value, "Student ID", min_length=3, max_length=20).upper()
    if not STUDENT_ID_PATTERN.fullmatch(student_id):
        raise ValidationError("Student ID must be 3-20 letters, digits, or hyphens (for example STU001).")
    return student_id


def validate_email(value: Any) -> str:
    email = require_text(value, "Email", min_length=5, max_length=120).lower()
    if not EMAIL_PATTERN.fullmatch(email):
        raise ValidationError("Enter a valid email address, for example student@demo.example.edu.")
    return email


def validate_semester(value: Any) -> int:
    try:
        semester = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Semester must be a whole number from 1 to 8.") from exc
    if semester < 1 or semester > 8:
        raise ValidationError("Semester must be between 1 and 8.")
    return semester


def validate_weekday(value: Any) -> int:
    try:
        weekday = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Weekday must be a number from 0 (Monday) to 6 (Sunday).") from exc
    if weekday < 0 or weekday > 6:
        raise ValidationError("Weekday must be between 0 (Monday) and 6 (Sunday).")
    return weekday


def parse_date(value: Any, field: str = "Date", *, required: bool = True) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value in (None, ""):
        if required:
            raise ValidationError(f"{field} is required.")
        return None
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise ValidationError(f"{field} must use YYYY-MM-DD format.") from exc


def parse_time(value: Any, field: str = "Time") -> str:
    if isinstance(value, datetime):
        value = value.time()
    if isinstance(value, time):
        return value.strftime("%H:%M")
    raw = str(value or "").strip()
    if not TIME_PATTERN.fullmatch(raw):
        raise ValidationError(f"{field} must use HH:MM format (24-hour clock).")
    return raw


def validate_time_range(start: Any, end: Any) -> tuple[str, str]:
    start_text = parse_time(start, "Start time")
    end_text = parse_time(end, "End time")
    if start_text >= end_text:
        raise ValidationError("End time must be later than start time.")
    return start_text, end_text


def validate_assignment_dates(publish_date: Any, due_date: Any) -> tuple[date, date]:
    published = parse_date(publish_date, "Publish date")
    due = parse_date(due_date, "Due date")
    if due < published:
        raise ValidationError("Due date cannot be earlier than the publish date.")
    return published, due


def validate_notice_dates(publish_date: Any, expiry_date: Any = None) -> tuple[date, date | None]:
    published = parse_date(publish_date, "Publish date")
    expiry = parse_date(expiry_date, "Expiry date", required=False)
    if expiry is not None and expiry < published:
        raise ValidationError("Expiry date cannot be earlier than the publish date.")
    return published, expiry


def validate_choice(value: Any, allowed: tuple[str, ...] | list[str], field: str) -> str:
    text = str(value or "").strip()
    if text not in allowed:
        raise ValidationError(f"{field} must be one of: {', '.join(allowed)}.")
    return text


def parse_positive_int(value: Any, field: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be a whole number.") from exc
    if number <= 0:
        raise ValidationError(f"{field} must be greater than zero.")
    return number
