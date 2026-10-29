"""Attendance upsert, percentage, and filter tests."""

from __future__ import annotations

from datetime import date

import pytest

from services.attendance_service import (
    attendance_summary,
    get_attendance_map,
    list_attendance,
    list_subjects,
    save_attendance_bulk,
)
from services.student_service import deactivate_student
from utils.validation import ValidationError


def test_attendance_upsert_and_summary_counts_late_as_attended(sample_records):
    db_path = sample_records["db_path"]
    subject_id = sample_records["subject_id"]
    first_student = sample_records["student_id"]
    second_student = sample_records["second_student_id"]

    assert list_subjects(db_path=db_path)[0]["code"] == "TST101"
    saved = save_attendance_bulk(
        date(2026, 10, 1),
        subject_id,
        [(first_student, "Present"), (second_student, "Late")],
        db_path=db_path,
    )
    assert saved == 2
    save_attendance_bulk(
        date(2026, 10, 2),
        subject_id,
        [(first_student, "Present"), (second_student, "Absent")],
        db_path=db_path,
    )
    save_attendance_bulk(
        date(2026, 10, 1),
        subject_id,
        [(second_student, "Absent")],
        db_path=db_path,
    )

    all_records = list_attendance(subject_id=subject_id, db_path=db_path)
    assert len(all_records) == 4

    summary = attendance_summary(student_db_id=second_student, db_path=db_path)
    assert summary["total"] == 2
    assert summary["present"] == 0
    assert summary["late"] == 0
    assert summary["absent"] == 2
    assert summary["percentage"] == 0.0

    day_one = attendance_summary(
        subject_id=subject_id,
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 1),
        db_path=db_path,
    )
    assert day_one["total"] == 2
    assert day_one["percentage"] == 50.0
    assert get_attendance_map(date(2026, 10, 1), subject_id, 2, db_path=db_path) == {
        first_student: "Present",
        second_student: "Absent",
    }


def test_attendance_rejects_invalid_status_and_inactive_student(sample_records):
    db_path = sample_records["db_path"]
    subject_id = sample_records["subject_id"]
    first_student = sample_records["student_id"]
    second_student = sample_records["second_student_id"]

    with pytest.raises(ValidationError, match="Attendance status"):
        save_attendance_bulk(date(2026, 10, 1), subject_id, [(first_student, "Excused")], db_path=db_path)

    deactivate_student(second_student, db_path=db_path)
    with pytest.raises(ValidationError, match="missing or inactive"):
        save_attendance_bulk(date(2026, 10, 1), subject_id, [(second_student, "Present")], db_path=db_path)

    with pytest.raises(ValidationError, match="At least one"):
        save_attendance_bulk(date(2026, 10, 1), subject_id, [], db_path=db_path)
