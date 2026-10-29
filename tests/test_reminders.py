"""Same-day reminder generation and deduplication tests."""

from __future__ import annotations

from datetime import date

from services.assignment_service import create_assignment
from services.notice_service import add_notice, deactivate_notice
from services.reminder_service import generate_reminders, list_reminders, reminder_counts

REFERENCE_DAY = date(2026, 10, 29)


def test_reminders_are_generated_and_deduplicated(sample_records):
    db_path = sample_records["db_path"]
    subject_id = sample_records["subject_id"]

    create_assignment(
        "DEMO Due soon",
        subject_id,
        "DEMO assignment due soon.",
        REFERENCE_DAY,
        REFERENCE_DAY.replace(day=31),
        db_path=db_path,
    )
    create_assignment(
        "DEMO Overdue",
        subject_id,
        "DEMO overdue assignment.",
        REFERENCE_DAY.replace(day=1),
        REFERENCE_DAY.replace(day=20),
        db_path=db_path,
    )
    expiring_notice_id = add_notice(
        "DEMO Expiring notice",
        "DEMO notice that expires soon.",
        "Academic",
        REFERENCE_DAY.replace(day=28),
        REFERENCE_DAY.replace(day=31),
        db_path=db_path,
    )
    inactive_notice_id = add_notice(
        "DEMO Inactive notice",
        "DEMO inactive notice should not create a reminder.",
        "General",
        REFERENCE_DAY.replace(day=28),
        REFERENCE_DAY.replace(day=31),
        db_path=db_path,
    )
    deactivate_notice(inactive_notice_id, db_path=db_path)

    assert generate_reminders(today=REFERENCE_DAY, db_path=db_path) == 3
    assert generate_reminders(today=REFERENCE_DAY, db_path=db_path) == 0

    reminders = list_reminders(reminder_date=REFERENCE_DAY, db_path=db_path)
    assert len(reminders) == 3
    assert {reminder["reminder_type"] for reminder in reminders} == {
        "assignment_due",
        "assignment_overdue",
        "notice_expiring",
    }
    notice_reminders = [
        reminder for reminder in reminders if reminder["entity_type"] == "notice"
    ]
    assert [reminder["entity_id"] for reminder in notice_reminders] == [expiring_notice_id]

    counts = reminder_counts(reminder_date=REFERENCE_DAY, db_path=db_path)
    assert counts == {
        "assignment_due": 1,
        "assignment_overdue": 1,
        "notice_expiring": 1,
        "Total": 3,
    }


def test_reminder_date_filter(sample_records):
    db_path = sample_records["db_path"]
    subject_id = sample_records["subject_id"]
    create_assignment(
        "DEMO Due reminder",
        subject_id,
        "DEMO assignment for a reminder date filter.",
        REFERENCE_DAY,
        REFERENCE_DAY.replace(day=31),
        db_path=db_path,
    )
    generate_reminders(today=REFERENCE_DAY, db_path=db_path)
    assert len(list_reminders(reminder_date=REFERENCE_DAY, db_path=db_path)) == 1
    assert list_reminders(reminder_date=REFERENCE_DAY.replace(day=30), db_path=db_path) == []
