"""Timetable conflict detection and CRUD tests."""

from __future__ import annotations

import pytest

from services.timetable_service import (
    add_entry,
    delete_entry,
    get_entry,
    list_entries,
    update_entry,
)
from utils.validation import ValidationError


def test_timetable_add_update_delete_and_conflicts(sample_records):
    db_path = sample_records["db_path"]
    subject_id = sample_records["subject_id"]

    entry_id = add_entry(
        0,
        "09:00",
        "10:00",
        subject_id,
        "A-101",
        "Dr. Test Faculty",
        2,
        db_path=db_path,
    )
    assert len(list_entries(semester=2, db_path=db_path)) == 1
    entry = get_entry(entry_id, db_path=db_path)
    assert entry["weekday_name"] == "Monday"
    assert entry["subject_code"] == "TST101"

    with pytest.raises(ValidationError, match="conflict"):
        add_entry(
            0,
            "09:30",
            "10:30",
            subject_id,
            "B-202",
            "Prof. Other Faculty",
            2,
            db_path=db_path,
        )

    with pytest.raises(ValidationError, match="conflict"):
        add_entry(
            0,
            "09:15",
            "09:45",
            subject_id,
            "a-101",
            "Prof. Other Faculty",
            4,
            db_path=db_path,
        )

    with pytest.raises(ValidationError, match="conflict"):
        add_entry(
            0,
            "09:50",
            "10:10",
            subject_id,
            "C-303",
            "dr. test faculty",
            5,
            db_path=db_path,
        )

    adjacent_id = add_entry(
        0,
        "10:00",
        "11:00",
        subject_id,
        "A-101",
        "Dr. Test Faculty",
        2,
        db_path=db_path,
    )
    assert get_entry(adjacent_id, db_path=db_path)["start_time"] == "10:00"

    update_entry(
        entry_id,
        0,
        "08:00",
        "09:00",
        subject_id,
        "A-101",
        "Dr. Test Faculty",
        2,
        db_path=db_path,
    )
    assert get_entry(entry_id, db_path=db_path)["start_time"] == "08:00"
    assert len(list_entries(weekday=0, db_path=db_path)) == 2

    delete_entry(adjacent_id, db_path=db_path)
    assert get_entry(adjacent_id, db_path=db_path) is None

    with pytest.raises(ValidationError, match="later"):
        add_entry(
            1,
            "11:00",
            "11:00",
            subject_id,
            "A-101",
            "Dr. Test Faculty",
            2,
            db_path=db_path,
        )
