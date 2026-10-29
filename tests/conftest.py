"""Shared pytest fixtures using isolated temporary SQLite databases."""

from __future__ import annotations

from pathlib import Path

import pytest

from services.database import db_connection, initialize_database


@pytest.fixture
def empty_db(tmp_path: Path) -> Path:
    path = tmp_path / "empty_university.db"
    initialize_database(seed=False, db_path=path)
    return path


@pytest.fixture
def seeded_db(tmp_path: Path) -> Path:
    path = tmp_path / "seeded_university.db"
    initialize_database(seed=True, db_path=path)
    return path


@pytest.fixture
def sample_records(empty_db: Path) -> dict[str, object]:
    with db_connection(empty_db) as connection:
        subject_cursor = connection.execute(
            """
            INSERT INTO subjects (code, name, department, semester)
            VALUES ('TST101', 'Testing Fundamentals', 'Computer Science', 2)
            """
        )
        subject_id = int(subject_cursor.lastrowid)
        student_cursor = connection.execute(
            """
            INSERT INTO students (student_id, name, department, semester, email)
            VALUES ('TST001', 'Test Student', 'Computer Science', 2, 'test.student@demo.example.edu')
            """
        )
        student_id = int(student_cursor.lastrowid)
        second_student_cursor = connection.execute(
            """
            INSERT INTO students (student_id, name, department, semester, email)
            VALUES ('TST002', 'Second Student', 'Information Technology', 2, 'second.student@demo.example.edu')
            """
        )
        second_student_id = int(second_student_cursor.lastrowid)
    return {
        "db_path": empty_db,
        "subject_id": subject_id,
        "student_id": student_id,
        "second_student_id": second_student_id,
    }
