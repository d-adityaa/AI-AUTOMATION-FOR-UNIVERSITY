"""SQLite persistence layer, schema creation, and idempotent demo seeding."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from utils.config import (
    DEFAULT_AI_MODEL,
    DEFAULT_AI_PROVIDER,
    DEMO_DATA_LABEL,
    get_db_path,
)
from utils.validation import require_text

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    semester INTEGER NOT NULL CHECK (semester BETWEEN 1 AND 8),
    email TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    semester INTEGER NOT NULL CHECK (semester BETWEEN 1 AND 8)
);

CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE RESTRICT,
    attendance_date TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('Present', 'Absent', 'Late')),
    recorded_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (student_id, subject_id, attendance_date)
);

CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(attendance_date);
CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance(student_id);

CREATE TABLE IF NOT EXISTS assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE RESTRICT,
    description TEXT NOT NULL DEFAULT '',
    publish_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (due_date >= publish_date)
);

CREATE INDEX IF NOT EXISTS idx_assignments_due ON assignments(due_date);

CREATE TABLE IF NOT EXISTS assignment_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id INTEGER NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    submitted_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('Submitted', 'Late')),
    UNIQUE (assignment_id, student_id)
);

CREATE TABLE IF NOT EXISTS notices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('Academic', 'Examination', 'Event', 'Holiday', 'General')),
    publish_date TEXT NOT NULL,
    expiry_date TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (expiry_date IS NULL OR expiry_date >= publish_date)
);

CREATE INDEX IF NOT EXISTS idx_notices_publish ON notices(publish_date);

CREATE TABLE IF NOT EXISTS timetable (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE RESTRICT,
    room TEXT NOT NULL,
    faculty_name TEXT NOT NULL,
    semester INTEGER NOT NULL CHECK (semester BETWEEN 1 AND 8),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (start_time < end_time)
);

CREATE INDEX IF NOT EXISTS idx_timetable_group ON timetable(weekday, semester, start_time);

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reminder_type TEXT NOT NULL CHECK (reminder_type IN ('assignment_due', 'assignment_overdue', 'notice_expiring')),
    entity_type TEXT NOT NULL CHECK (entity_type IN ('assignment', 'notice')),
    entity_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    reminder_date TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (reminder_type, entity_type, entity_id, reminder_date)
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

DEFAULT_SETTINGS = {
    "ai_provider": DEFAULT_AI_PROVIDER,
    "ai_model": DEFAULT_AI_MODEL,
    "academic_current_semester": "3",
    "academic_exam_notice": (
        "DEMO: Mid-semester examinations are planned for the first two weeks of next month. "
        "Check the official examination notice on the Notice board."
    ),
    "academic_office_hours": (
        "DEMO: Faculty office hours are Monday-Friday, 10:00-12:00 and 14:00-16:00. "
        "Rooms are listed on the Timetable page."
    ),
    "academic_calendar": (
        "DEMO: Semester 3 project review - week 6\n"
        "DEMO: Mid-semester examinations - weeks 7-8\n"
        "DEMO: AI Automation Lab practical viva - week 9\n"
        "DEMO: Semester 3 end-term examinations - weeks 14-15"
    ),
}


@contextmanager
def db_connection(db_path: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    """Yield a transaction-managed SQLite connection."""
    resolved = Path(db_path) if db_path is not None else get_db_path()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(resolved, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(*, seed: bool = True, db_path: str | Path | None = None) -> None:
    """Create all tables, defaults, and optional demo data."""
    with db_connection(db_path) as connection:
        connection.executescript(SCHEMA_SQL)
        for key, value in DEFAULT_SETTINGS.items():
            connection.execute(
                "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
                (key, value),
            )
        if seed:
            seed_demo_data(connection)


def get_setting(key: str, default: str | None = None, *, db_path: str | Path | None = None) -> str | None:
    key = require_text(key, "Setting key", max_length=80)
    with db_connection(db_path) as connection:
        row = connection.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str, *, db_path: str | Path | None = None) -> None:
    key = require_text(key, "Setting key", max_length=80)
    text = require_text(value, "Setting value", max_length=5000)
    with db_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')
            """,
            (key, text),
        )


def set_settings(values: dict[str, str], *, db_path: str | Path | None = None) -> None:
    if not values:
        return
    with db_connection(db_path) as connection:
        for key, value in values.items():
            connection.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')
                """,
                (require_text(key, "Setting key", max_length=80), str(value).strip()),
            )


def get_academic_info(*, db_path: str | Path | None = None) -> dict[str, Any]:
    keys = (
        "academic_current_semester",
        "academic_exam_notice",
        "academic_office_hours",
        "academic_calendar",
    )
    with db_connection(db_path) as connection:
        rows = connection.execute(
            f"SELECT key, value FROM app_settings WHERE key IN ({','.join('?' for _ in keys)})",
            keys,
        ).fetchall()
    values = {row["key"]: row["value"] for row in rows}
    return {
        "current_semester": values.get("academic_current_semester", "3"),
        "exam_notice": values.get("academic_exam_notice", ""),
        "office_hours": values.get("academic_office_hours", ""),
        "calendar_entries": values.get("academic_calendar", ""),
        "label": DEMO_DATA_LABEL,
    }


def _seed_students(connection: sqlite3.Connection) -> None:
    students = [
        ("STU001", "Aarav Sharma", "Computer Science", 3, "aarav.sharma@demo.example.edu"),
        ("STU002", "Meera Patel", "Computer Science", 3, "meera.patel@demo.example.edu"),
        ("STU003", "Rohan Iyer", "Computer Science", 3, "rohan.iyer@demo.example.edu"),
        ("STU004", "Ananya Rao", "Computer Science", 3, "ananya.rao@demo.example.edu"),
        ("STU005", "Kabir Singh", "Computer Science", 2, "kabir.singh@demo.example.edu"),
        ("STU006", "Ishita Nair", "Computer Science", 2, "ishita.nair@demo.example.edu"),
        ("STU007", "Dev Malhotra", "Information Technology", 4, "dev.malhotra@demo.example.edu"),
        ("STU008", "Sara Khan", "Information Technology", 4, "sara.khan@demo.example.edu"),
        ("STU009", "Nikhil Verma", "Computer Science", 1, "nikhil.verma@demo.example.edu"),
        ("STU010", "Priya Menon", "Computer Science", 1, "priya.menon@demo.example.edu"),
    ]
    connection.executemany(
        """
        INSERT OR IGNORE INTO students (student_id, name, department, semester, email)
        VALUES (?, ?, ?, ?, ?)
        """,
        students,
    )


def _seed_subjects(connection: sqlite3.Connection) -> None:
    subjects = [
        ("CS101", "Programming Fundamentals", "Computer Science", 1),
        ("CS102", "Mathematics for Computing", "Computer Science", 1),
        ("CS201", "Data Structures", "Computer Science", 2),
        ("CS202", "Web Technologies", "Computer Science", 2),
        ("CS301", "Database Systems", "Computer Science", 3),
        ("CS302", "Artificial Intelligence", "Computer Science", 3),
        ("CS303", "Operating Systems", "Computer Science", 3),
        ("AL301", "AI Automation Laboratory", "Computer Science", 3),
        ("IT401", "Cloud Computing", "Information Technology", 4),
        ("IT402", "Cyber Security", "Information Technology", 4),
    ]
    connection.executemany(
        "INSERT OR IGNORE INTO subjects (code, name, department, semester) VALUES (?, ?, ?, ?)",
        subjects,
    )


def seed_demo_data(connection: sqlite3.Connection, today: date | None = None) -> bool:
    """Load fictional demo data once. Returns True when data was inserted."""
    existing = connection.execute("SELECT COUNT(*) AS count FROM students").fetchone()["count"]
    if existing:
        return False

    reference_day = today or date.today()
    _seed_students(connection)
    _seed_subjects(connection)

    subject_rows = connection.execute("SELECT id, code FROM subjects").fetchall()
    subject_ids = {row["code"]: row["id"] for row in subject_rows}
    student_rows = connection.execute("SELECT id, student_id, semester FROM students").fetchall()
    student_ids = {row["student_id"]: row["id"] for row in student_rows}
    sem3_students = [row["id"] for row in student_rows if row["semester"] == 3]
    sem2_students = [row["id"] for row in student_rows if row["semester"] == 2]

    assignments = [
        (
            "Normalize a course-enrollment schema",
            subject_ids["CS301"],
            "DEMO: Normalize the supplied enrollment spreadsheet to third normal form and include a short data dictionary.",
            reference_day - timedelta(days=7),
            reference_day + timedelta(days=2),
        ),
        (
            "Build a safe AI campus assistant",
            subject_ids["CS302"],
            "DEMO: Prototype an assistant that uses allowlisted read-only tools and never executes generated code.",
            reference_day - timedelta(days=4),
            reference_day + timedelta(days=6),
        ),
        (
            "Compare CPU scheduling policies",
            subject_ids["CS303"],
            "DEMO: Compare FCFS, SJF, and round robin using the supplied synthetic process table.",
            reference_day - timedelta(days=12),
            reference_day - timedelta(days=2),
        ),
        (
            "Portfolio wireframe review",
            subject_ids["CS202"],
            "DEMO: Submit wireframes for a responsive student services portal and note three accessibility choices.",
            reference_day - timedelta(days=8),
            reference_day - timedelta(days=1),
        ),
        (
            "Cloud security case study",
            subject_ids["IT402"],
            "DEMO: Analyse the fictional cloud incident brief and propose preventive controls.",
            reference_day - timedelta(days=5),
            reference_day + timedelta(days=4),
        ),
        (
            "Stacks and queues practice set",
            subject_ids["CS201"],
            "DEMO: Complete the practice worksheet and explain the complexity of each operation.",
            reference_day - timedelta(days=2),
            reference_day + timedelta(days=10),
        ),
    ]
    assignment_ids: list[int] = []
    for assignment in assignments:
        cursor = connection.execute(
            """
            INSERT INTO assignments (title, subject_id, description, publish_date, due_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                assignment[0],
                assignment[1],
                assignment[2],
                assignment[3].isoformat(),
                assignment[4].isoformat(),
            ),
        )
        assignment_ids.append(int(cursor.lastrowid))

    submissions = [
        (assignment_ids[0], student_ids["STU001"], reference_day - timedelta(days=1), "Submitted"),
        (assignment_ids[0], student_ids["STU002"], reference_day - timedelta(days=1), "Submitted"),
        (assignment_ids[2], student_ids["STU003"], reference_day, "Late"),
        (assignment_ids[2], student_ids["STU002"], reference_day, "Late"),
        (assignment_ids[3], student_ids["STU005"], reference_day - timedelta(days=2), "Submitted"),
    ]
    for assignment_id, student_id, submitted_day, status in submissions:
        connection.execute(
            """
            INSERT OR IGNORE INTO assignment_submissions (assignment_id, student_id, submitted_at, status)
            VALUES (?, ?, ?, ?)
            """,
            (assignment_id, student_id, f"{submitted_day.isoformat()} 10:30:00", status),
        )

    notices = [
        (
            "Mid-semester examination schedule (DEMO)",
            "DEMO: The mid-semester examination timetable for semesters 1-4 is now available at the examination desk. "
            "Students should verify their subject codes and report any clash to the academic office within three days. "
            "Bring a printed hall ticket and a college identity card to every examination.",
            "Examination",
            reference_day - timedelta(days=3),
            reference_day + timedelta(days=10),
        ),
        (
            "AI Automation Lab practical viva (DEMO)",
            "DEMO: Practical vivas for the AI Automation Laboratory will be held next week in Lab 1. "
            "Each team must demonstrate a working prototype, explain its database schema, and show test results. "
            "External API use is optional and must not be required for core functionality.",
            "Academic",
            reference_day - timedelta(days=1),
            reference_day + timedelta(days=5),
        ),
        (
            "Campus tech fest registrations open (DEMO)",
            "DEMO: Student teams may register for the annual campus technology festival. "
            "Project demonstrations, coding relays, and a responsible-AI poster session are planned. "
            "Registration closes at the end of next week.",
            "Event",
            reference_day - timedelta(days=2),
            reference_day + timedelta(days=20),
        ),
        (
            "Library extended hours during exams (DEMO)",
            "DEMO: The central library will remain open until 21:00 on weekdays during the examination period. "
            "Group discussion rooms must be booked at the circulation desk.",
            "General",
            reference_day - timedelta(days=6),
            None,
        ),
        (
            "Semester fee payment window (DEMO)",
            "DEMO: The semester fee payment window is open for all demonstration programmes. "
            "Payments must be completed before the stated deadline to avoid a late fee.",
            "Academic",
            reference_day - timedelta(days=9),
            reference_day + timedelta(days=3),
        ),
        (
            "Scholarship applications close soon (DEMO)",
            "DEMO: Applications for the fictional merit scholarship close tomorrow. "
            "Submit the demonstration form at the student services desk.",
            "Academic",
            reference_day - timedelta(days=5),
            reference_day + timedelta(days=1),
        ),
        (
            "Founders' Day holiday (DEMO)",
            "DEMO: The campus will observe a holiday for Founders' Day. No classes or laboratory sessions will run.",
            "Holiday",
            reference_day - timedelta(days=15),
            reference_day - timedelta(days=2),
        ),
    ]
    for title, content, category, published, expiry in notices:
        connection.execute(
            """
            INSERT INTO notices (title, content, category, publish_date, expiry_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                title,
                content,
                category,
                published.isoformat(),
                expiry.isoformat() if expiry else None,
            ),
        )

    timetable = [
        (0, "09:00", "10:00", subject_ids["CS301"], "A-201", "Dr. Nisha Rao (DEMO)", 3),
        (0, "10:15", "11:15", subject_ids["CS302"], "A-202", "Dr. Vikram Sen (DEMO)", 3),
        (1, "09:00", "10:00", subject_ids["CS303"], "A-203", "Prof. Leena Thomas (DEMO)", 3),
        (2, "09:00", "10:00", subject_ids["CS301"], "A-201", "Dr. Nisha Rao (DEMO)", 3),
        (2, "14:00", "16:00", subject_ids["AL301"], "Lab-1", "Dr. Vikram Sen (DEMO)", 3),
        (3, "09:00", "10:00", subject_ids["CS302"], "A-202", "Dr. Vikram Sen (DEMO)", 3),
        (3, "11:00", "12:00", subject_ids["CS303"], "A-203", "Prof. Leena Thomas (DEMO)", 3),
        (4, "10:00", "11:00", subject_ids["CS301"], "A-201", "Dr. Nisha Rao (DEMO)", 3),
        (0, "09:00", "10:00", subject_ids["CS202"], "B-101", "Prof. Aditya Bose (DEMO)", 2),
        (1, "10:00", "11:00", subject_ids["CS201"], "B-102", "Prof. Aditya Bose (DEMO)", 2),
        (3, "09:00", "10:00", subject_ids["CS201"], "B-102", "Prof. Aditya Bose (DEMO)", 2),
        (2, "11:00", "12:00", subject_ids["IT401"], "C-301", "Dr. Farah Ali (DEMO)", 4),
        (4, "09:00", "10:00", subject_ids["IT402"], "C-302", "Dr. Farah Ali (DEMO)", 4),
    ]
    connection.executemany(
        """
        INSERT INTO timetable (weekday, start_time, end_time, subject_id, room, faculty_name, semester)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        timetable,
    )

    attendance_dates = [reference_day, reference_day - timedelta(days=1), reference_day - timedelta(days=3)]
    status_cycle = ("Present", "Present", "Late", "Absent")
    for date_index, attendance_day in enumerate(attendance_dates):
        for subject_code in ("CS301", "CS302"):
            for student_index, student_id in enumerate(sem3_students):
                status = status_cycle[(student_index + date_index + (0 if subject_code == "CS301" else 1)) % 4]
                connection.execute(
                    """
                    INSERT OR IGNORE INTO attendance (student_id, subject_id, attendance_date, status)
                    VALUES (?, ?, ?, ?)
                    """,
                    (student_id, subject_ids[subject_code], attendance_day.isoformat(), status),
                )
    for date_index, attendance_day in enumerate([reference_day, reference_day - timedelta(days=2)]):
        for student_index, student_id in enumerate(sem2_students):
            status = status_cycle[(student_index + date_index) % 4]
            connection.execute(
                """
                INSERT OR IGNORE INTO attendance (student_id, subject_id, attendance_date, status)
                VALUES (?, ?, ?, ?)
                """,
                (student_id, subject_ids["CS201"], attendance_day.isoformat(), status),
            )

    return True


def database_counts(*, db_path: str | Path | None = None) -> dict[str, int]:
    tables = ("students", "subjects", "attendance", "assignments", "notices", "timetable", "reminders")
    with db_connection(db_path) as connection:
        return {
            table: int(connection.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"])
            for table in tables
        }


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
