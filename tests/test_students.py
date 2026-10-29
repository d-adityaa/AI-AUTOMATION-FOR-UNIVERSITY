"""Student CRUD, validation, filtering, and active-state tests."""

from __future__ import annotations

import pytest

from services.student_service import (
    add_student,
    count_students,
    deactivate_student,
    get_student,
    get_student_by_student_id,
    list_departments,
    list_students,
    reactivate_student,
    update_student,
)
from utils.validation import ValidationError


def test_add_get_update_and_filter_student(empty_db):
    student_db_id = add_student(
        "stu100",
        "Demo Learner",
        "Computer Science",
        3,
        "DEMO.LEARNER@example.edu",
        db_path=empty_db,
    )
    student = get_student(student_db_id, db_path=empty_db)
    assert student is not None
    assert student["student_id"] == "STU100"
    assert student["email"] == "demo.learner@example.edu"
    assert get_student_by_student_id("stu100", db_path=empty_db)["id"] == student_db_id

    update_student(
        student_db_id,
        "STU100",
        "Updated Learner",
        "Information Technology",
        4,
        "updated@example.edu",
        db_path=empty_db,
    )
    updated = get_student(student_db_id, db_path=empty_db)
    assert updated["name"] == "Updated Learner"
    assert updated["department"] == "Information Technology"
    assert updated["semester"] == 4

    assert len(list_students(search="Updated", db_path=empty_db)) == 1
    assert len(list_students(department="Information Technology", db_path=empty_db)) == 1
    assert len(list_students(semester=3, db_path=empty_db)) == 0
    assert list_departments(db_path=empty_db) == ["Information Technology"]


def test_duplicate_student_id_is_rejected(empty_db):
    add_student("STU200", "First Learner", "Science", 2, "first@example.edu", db_path=empty_db)
    with pytest.raises(ValidationError, match="already exists"):
        add_student("stu200", "Second Learner", "Science", 2, "second@example.edu", db_path=empty_db)


@pytest.mark.parametrize(
    ("student_id", "email"),
    [
        ("", "valid@example.edu"),
        ("X", "valid@example.edu"),
        ("STU 300", "valid@example.edu"),
        ("STU300", "not-an-email"),
    ],
)
def test_invalid_student_input_is_rejected(empty_db, student_id, email):
    with pytest.raises(ValidationError):
        add_student(student_id, "Invalid Learner", "Science", 2, email, db_path=empty_db)


def test_deactivate_and_reactivate_student(empty_db):
    student_db_id = add_student(
        "STU400", "Toggle Learner", "Science", 2, "toggle@example.edu", db_path=empty_db
    )
    deactivate_student(student_db_id, db_path=empty_db)
    assert get_student(student_db_id, db_path=empty_db)["is_active"] is False
    assert list_students(db_path=empty_db) == []
    assert len(list_students(include_inactive=True, db_path=empty_db)) == 1
    assert count_students(active_only=True, db_path=empty_db) == 0
    assert count_students(active_only=False, db_path=empty_db) == 1

    reactivate_student(student_db_id, db_path=empty_db)
    assert get_student(student_db_id, db_path=empty_db)["is_active"] is True
    assert count_students(active_only=True, db_path=empty_db) == 1
