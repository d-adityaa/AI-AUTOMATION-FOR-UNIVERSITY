"""Database schema, defaults, and idempotent demo seeding tests."""

from __future__ import annotations

from services.database import (
    database_counts,
    get_academic_info,
    get_setting,
    initialize_database,
    set_setting,
    set_settings,
)


def test_seed_is_idempotent(seeded_db):
    first_counts = database_counts(db_path=seeded_db)
    assert first_counts["students"] == 10
    assert first_counts["subjects"] == 10
    assert first_counts["assignments"] == 6
    assert first_counts["notices"] == 7
    assert first_counts["timetable"] == 13
    assert first_counts["attendance"] == 28

    initialize_database(seed=True, db_path=seeded_db)
    second_counts = database_counts(db_path=seeded_db)
    assert second_counts == first_counts


def test_empty_database_has_default_settings_and_no_operational_rows(empty_db):
    counts = database_counts(db_path=empty_db)
    assert counts == {
        "students": 0,
        "subjects": 0,
        "attendance": 0,
        "assignments": 0,
        "notices": 0,
        "timetable": 0,
        "reminders": 0,
    }
    assert get_setting("ai_model", db_path=empty_db) == "gemini-3.5-flash-lite"
    assert get_setting("academic_current_semester", db_path=empty_db) == "3"


def test_settings_round_trip_and_academic_info(empty_db):
    set_setting("ai_model", "gemini-3.6-flash", db_path=empty_db)
    assert get_setting("ai_model", db_path=empty_db) == "gemini-3.6-flash"

    set_settings(
        {
            "academic_current_semester": "4",
            "academic_exam_notice": "DEMO exam notice",
            "academic_office_hours": "DEMO office hours",
            "academic_calendar": "DEMO calendar",
        },
        db_path=empty_db,
    )
    info = get_academic_info(db_path=empty_db)
    assert info["current_semester"] == "4"
    assert info["exam_notice"] == "DEMO exam notice"
    assert info["office_hours"] == "DEMO office hours"
    assert info["calendar_entries"] == "DEMO calendar"
    assert "fictional" in info["label"].lower()
