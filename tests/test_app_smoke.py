"""End-to-end Streamlit smoke tests for every registered page."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_all_pages_render_without_exceptions(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SMART_UNI_DB_PATH", str(tmp_path / "app_smoke.db"))
    APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(APP_PATH, default_timeout=45)
    app.run()
    assert app.exception == []
    assert [title.value for title in app.title] == ["Dashboard"]

    pages_and_titles = [
        ("app_pages/students.py", "Students"),
        ("app_pages/attendance.py", "Attendance"),
        ("app_pages/assignments.py", "Assignments"),
        ("app_pages/notices.py", "Notices"),
        ("app_pages/timetable.py", "Timetable"),
        ("app_pages/ai_assistant.py", "AI assistant"),
        ("app_pages/settings.py", "Settings"),
    ]
    for page_path, expected_title in pages_and_titles:
        app.switch_page(page_path)
        app.run()
        assert app.exception == [], f"{page_path} raised: {[exc.message for exc in app.exception]}"
        assert expected_title in [title.value for title in app.title]

    app.session_state["demo_role"] = "Student"
    app.run()
    app.switch_page("app_pages/dashboard.py")
    app.run()
    assert app.exception == []
    for page_path, expected_title in pages_and_titles:
        app.switch_page(page_path)
        app.run()
        assert app.exception == [], (
            f"{page_path} raised in Student demo mode: "
            f"{[exc.message for exc in app.exception]}"
        )
        assert expected_title in [title.value for title in app.title]

