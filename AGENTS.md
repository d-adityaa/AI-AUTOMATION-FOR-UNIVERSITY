# Agent instructions

## Project

Smart University Automation System: a local Streamlit + SQLite classroom prototype for fictional university workflows. Use Python 3.11 and the existing `.venv`.

All demo records must remain clearly fictional. Never present the app as production authentication, a real notification system, or a real file-upload system.

## Commands

Run from the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m compileall -q app.py app_pages services utils
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Use the full interpreter path; do not rely on a globally activated environment. Install dependencies only from `requirements.txt`.

## Architecture

- `app.py`: page config, database initialization, `st.navigation` registration.
- `app_pages/`: one Streamlit page per module. Register any new page in `app.py`.
- `services/`: business logic and SQLite access.
- `utils/`: configuration, validation, and shared UI/session helpers.
- `tests/`: pytest with isolated temporary databases.
- Use `app_pages/`, not Streamlit's legacy `pages/` directory.

Data flow:

```text
Streamlit page -> service function -> db_connection() -> SQLite
```

Do not put SQL in page modules when a service function is appropriate. If adding a new service operation, add it to `services/`, validate inputs, and test it.

## Data and validation

- Default DB: `data/smart_university.db`; override with `SMART_UNI_DB_PATH`.
- Always access SQLite through `services.database.db_connection`.
- Keep dates stored as ISO `YYYY-MM-DD`; keep timetable times as `HH:MM`.
- Attendance statuses are `Present`, `Absent`, `Late`; attendance percentage counts only `Present` and `Late` as attended.
- Assignment statuses are `Pending`, `Submitted`, `Late`, `Overdue`.
- Notice categories are fixed in `notice_service.NOTICE_CATEGORIES`.
- Demo seeding is idempotent and must only run when the database has no students.
- Preserve historical records when deactivating students, notices, or timetable entries where possible.

## AI invariants

- AI is optional. Core features must work without `GEMINI_API_KEY`.
- Read the key only through `utils.config.get_gemini_api_key`; never display, log, persist, or commit it.
- Only allow models listed in `utils.config.SUPPORTED_AI_MODELS`.
- Keep AI access limited to the allowlisted, typed, read-only functions in `services/ai_tools.py`.
- Never execute generated SQL, Python, shell commands, `eval`, or `exec`.
- Never invent attendance, deadlines, timetable entries, policy, or notices.
- On AI failure, return a clearly labelled database-grounded fallback; never fake a success message.
- Do not claim that email, SMS, WhatsApp, or push notifications were sent.
- Do not make live network calls automatically in tests.

## UI conventions

- User-facing text is English and concise.
- Label demonstration roles and fictional data honestly.
- The sidebar role selector is not authentication; do not describe it as real authorization.
- Every visible button must perform a real action or navigate. Avoid decorative controls.
- Use native Streamlit components and the existing light theme in `.streamlit/config.toml`.
- Use Material icon shortcodes that exist in the installed Streamlit version.
- Show empty states instead of failing when filters return no rows.

## Testing

- Use the fixtures in `tests/conftest.py`; never point tests at the real `data/smart_university.db`.
- Pass an explicit `db_path` to service calls in unit tests.
- Mock `services.ai_assistant._generate_text` for AI-success and AI-failure tests.
- Keep `tests/test_app_smoke.py` covering every registered page in both demo roles.
- Before finishing, run compileall and pytest. Report observed results only; do not claim live Gemini success without a real request.

## Current decisions

- Streamlit page directory is `app_pages/`.
- Default Gemini model: `gemini-3.5-flash-lite`.
- Assignment submission is a demo flag/timestamp, with no upload.
- Reminders are in-app rows deduplicated per day by a unique constraint.
- Timetable conflict detection checks semester, room, and faculty overlap.
