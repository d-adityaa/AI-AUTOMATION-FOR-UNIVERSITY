"""Assignment creation, deadline status, and demo submission tests."""

from __future__ import annotations

from datetime import date

import pytest

from services.assignment_service import (
    create_assignment,
    get_assignment,
    list_assignments,
    mark_submitted,
    overdue_assignments,
    student_assignment_stats,
    submission_stats_for_assignment,
    upcoming_deadlines,
)
from utils.validation import ValidationError

REFERENCE_DAY = date(2026, 10, 29)


def test_assignment_statuses_and_submission_flow(sample_records):
    db_path = sample_records["db_path"]
    subject_id = sample_records["subject_id"]
    first_student = sample_records["student_id"]
    second_student = sample_records["second_student_id"]

    future_id = create_assignment(
        "DEMO Future report",
        subject_id,
        "DEMO description for a pending assignment.",
        REFERENCE_DAY,
        REFERENCE_DAY.replace(day=31),
        db_path=db_path,
    )
    late_id = create_assignment(
        "DEMO Late report",
        subject_id,
        "DEMO description for a late assignment.",
        REFERENCE_DAY.replace(day=15),
        REFERENCE_DAY.replace(day=25),
        db_path=db_path,
    )
    overdue_id = create_assignment(
        "DEMO Overdue report",
        subject_id,
        "DEMO description for an overdue assignment.",
        REFERENCE_DAY.replace(day=10),
        REFERENCE_DAY.replace(day=20),
        db_path=db_path,
    )

    pending = get_assignment(future_id, student_db_id=first_student, today=REFERENCE_DAY, db_path=db_path)
    assert pending["status"] == "Pending"
    assert pending["days_until_due"] == 2

    result = mark_submitted(future_id, first_student, submitted_date=REFERENCE_DAY, db_path=db_path)
    assert result["status"] == "Submitted"
    submitted = get_assignment(future_id, student_db_id=first_student, today=REFERENCE_DAY, db_path=db_path)
    assert submitted["status"] == "Submitted"
    assert submitted["submitted_at"].startswith(REFERENCE_DAY.isoformat())

    late_result = mark_submitted(late_id, first_student, submitted_date=REFERENCE_DAY, db_path=db_path)
    assert late_result["status"] == "Late"

    overdue = get_assignment(overdue_id, student_db_id=first_student, today=REFERENCE_DAY, db_path=db_path)
    assert overdue["status"] == "Overdue"
    assert overdue["is_overdue"] is True

    stats = student_assignment_stats(first_student, today=REFERENCE_DAY, db_path=db_path)
    assert stats == {"Pending": 0, "Submitted": 1, "Late": 1, "Overdue": 1, "Total": 3}

    assignment_stats = submission_stats_for_assignment(future_id, today=REFERENCE_DAY, db_path=db_path)
    assert assignment_stats == {"Submitted": 1, "Late": 0, "Pending": 1, "Overdue": 0, "Total": 2}

    assert [item["id"] for item in overdue_assignments(
        student_db_id=first_student, today=REFERENCE_DAY, db_path=db_path
    )] == [overdue_id]
    upcoming_ids = {
        item["id"]
        for item in upcoming_deadlines(
            days=5,
            student_db_id=second_student,
            today=REFERENCE_DAY,
            db_path=db_path,
        )
    }
    assert future_id in upcoming_ids
    assert late_id not in upcoming_ids

    duplicate_statuses = {
        item["id"]: item["status"]
        for item in list_assignments(
            student_db_id=second_student,
            today=REFERENCE_DAY,
            db_path=db_path,
        )
    }
    assert duplicate_statuses[future_id] == "Pending"


def test_duplicate_submission_and_invalid_dates_are_rejected(sample_records):
    db_path = sample_records["db_path"]
    subject_id = sample_records["subject_id"]
    first_student = sample_records["student_id"]

    assignment_id = create_assignment(
        "DEMO Duplicate submission",
        subject_id,
        "DEMO description for submission validation.",
        REFERENCE_DAY,
        REFERENCE_DAY.replace(day=31),
        db_path=db_path,
    )
    mark_submitted(assignment_id, first_student, submitted_date=REFERENCE_DAY, db_path=db_path)
    with pytest.raises(ValidationError, match="already"):
        mark_submitted(assignment_id, first_student, submitted_date=REFERENCE_DAY, db_path=db_path)

    with pytest.raises(ValidationError, match="cannot be earlier"):
        create_assignment(
            "DEMO Invalid dates",
            subject_id,
            "DEMO description for invalid date validation.",
            REFERENCE_DAY,
            REFERENCE_DAY.replace(day=20),
            db_path=db_path,
        )
