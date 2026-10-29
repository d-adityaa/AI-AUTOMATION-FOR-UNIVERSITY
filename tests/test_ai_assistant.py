"""AI routing, database grounding, fallback, and safe tool-list tests."""

from __future__ import annotations

from datetime import date

from services import ai_assistant
from services.assignment_service import create_assignment
from services.attendance_service import save_attendance_bulk
from services.notice_service import add_notice
from services.timetable_service import add_entry
from services.ai_assistant import (
    AIError,
    allowed_tool_names,
    answer_question,
    test_ai_connection as check_ai_connection,
)

REFERENCE_DAY = date(2026, 10, 29)


def test_assignment_and_attendance_answers_are_database_grounded(sample_records):
    db_path = sample_records["db_path"]
    subject_id = sample_records["subject_id"]
    student_id = sample_records["student_id"]
    create_assignment(
        "DEMO AI assignment",
        subject_id,
        "DEMO assignment used by the assistant route test.",
        REFERENCE_DAY,
        REFERENCE_DAY.replace(day=31),
        db_path=db_path,
    )
    save_attendance_bulk(
        REFERENCE_DAY,
        subject_id,
        [(student_id, "Present")],
        db_path=db_path,
    )
    save_attendance_bulk(
        REFERENCE_DAY.replace(day=28),
        subject_id,
        [(student_id, "Absent")],
        db_path=db_path,
    )

    assignment_result = answer_question(
        "What assignments are due this week?",
        student_db_id=student_id,
        today=REFERENCE_DAY,
        api_key="",
        db_path=db_path,
    )
    assert assignment_result["mode"] == "database"
    assert assignment_result["tool"] == "list_due_assignments"
    assert "DEMO AI assignment" in assignment_result["answer"]

    attendance_result = answer_question(
        "What is the attendance percentage for TST001?",
        today=REFERENCE_DAY,
        api_key="",
        db_path=db_path,
    )
    assert attendance_result["tool"] == "get_attendance_summary"
    assert "50.0%" in attendance_result["answer"]
    assert "Present: 1" in attendance_result["answer"]


def test_timetable_and_notice_routes(sample_records):
    db_path = sample_records["db_path"]
    subject_id = sample_records["subject_id"]
    add_entry(
        REFERENCE_DAY.weekday(),
        "12:00",
        "13:00",
        subject_id,
        "AI-Lab",
        "Dr. Assistant",
        2,
        db_path=db_path,
    )
    add_notice(
        "DEMO AI examination notice",
        "DEMO examination notice used by the assistant test.",
        "Examination",
        REFERENCE_DAY,
        REFERENCE_DAY.replace(day=31),
        db_path=db_path,
    )

    timetable_result = answer_question(
        "Show today's timetable for semester 2",
        today=REFERENCE_DAY,
        api_key="",
        db_path=db_path,
    )
    assert timetable_result["tool"] == "get_timetable_for_day"
    assert "semester 2" in timetable_result["answer"]
    assert "AI-Lab" in timetable_result["answer"]

    notice_result = answer_question(
        "Show the latest examination notice",
        today=REFERENCE_DAY,
        api_key="",
        db_path=db_path,
    )
    assert notice_result["tool"] == "list_current_notices"
    assert "DEMO AI examination notice" in notice_result["answer"]


def test_unknown_question_returns_help_without_calling_ai(sample_records, monkeypatch):
    called = False

    def fail_if_called(**kwargs):
        nonlocal called
        called = True
        raise AssertionError("Gemini should not be called for an unsupported question")

    monkeypatch.setattr(ai_assistant, "_generate_text", fail_if_called)
    result = answer_question(
        "Tell me a joke",
        api_key="fake-key",
        db_path=sample_records["db_path"],
    )
    assert result["tool"] is None
    assert result["mode"] == "database"
    assert called is False


def test_ai_phrasing_and_fallback(sample_records, monkeypatch):
    db_path = sample_records["db_path"]
    subject_id = sample_records["subject_id"]
    create_assignment(
        "DEMO AI fallback assignment",
        subject_id,
        "DEMO assignment used by AI fallback tests.",
        REFERENCE_DAY,
        REFERENCE_DAY.replace(day=31),
        db_path=db_path,
    )

    monkeypatch.setattr(
        ai_assistant,
        "_generate_text",
        lambda **kwargs: "Grounded mock answer from Gemini.",
    )
    ai_result = answer_question(
        "What assignments are due this week?",
        today=REFERENCE_DAY,
        api_key="fake-key",
        db_path=db_path,
    )
    assert ai_result["mode"] == "ai"
    assert ai_result["answer"] == "Grounded mock answer from Gemini."

    def raise_quota_error(**kwargs):
        raise AIError("Gemini quota or rate limit reached.")

    monkeypatch.setattr(ai_assistant, "_generate_text", raise_quota_error)
    fallback = answer_question(
        "What assignments are due this week?",
        today=REFERENCE_DAY,
        api_key="fake-key",
        db_path=db_path,
    )
    assert fallback["mode"] == "ai_failed"
    assert "DEMO AI fallback assignment" in fallback["answer"]
    assert "quota" in fallback["error"]


def test_no_key_and_connection_test_without_key(sample_records, monkeypatch):
    monkeypatch.setattr(ai_assistant, "get_gemini_api_key", lambda: None)
    result = answer_question(
        "What assignments are due this week?",
        today=REFERENCE_DAY,
        db_path=sample_records["db_path"],
    )
    assert result["mode"] == "database"
    assert result["error"] is None

    success, message = check_ai_connection(api_key=None, db_path=sample_records["db_path"])
    assert success is False
    assert "No Gemini API key" in message


def test_tool_allowlist_has_only_read_tools():
    names = allowed_tool_names()
    assert names == sorted(
        [
            "get_assignment_submission_stats",
            "get_attendance_summary",
            "get_timetable_for_day",
            "list_current_notices",
            "list_due_assignments",
            "list_overdue_assignments",
        ]
    )
