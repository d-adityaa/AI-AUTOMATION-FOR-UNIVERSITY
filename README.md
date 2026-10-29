# Smart University Automation System

A local college-workflow prototype built with **Streamlit**, **SQLite**, **pandas**, and optional **Google Gemini**. It manages fictional demo students, attendance, assignments, notices, timetables, and in-app reminders in one dashboard.

All operational records are fictional **DEMO** data. This is a classroom project, not a production university system.

## What works

- **Dashboard**: live counts, today's attendance summary, pending work, upcoming deadlines, today's timetable, recent notices, generated reminders, and working page links.
- **Students**: search/filter, add, edit, activate/deactivate, and view attendance and assignment details.
- **Attendance**: faculty data-editor entry with Present/Absent/Late, safe updates for the same date/subject, filtered history, percentage analytics, and CSV export.
- **Assignments**: create assignments, filter by subject/status, calculate Pending/Submitted/Late/Overdue from stored dates, view submission counts, and record a demo student submission flag.
- **Notices**: search, category filters, current/expired views, add/edit, activate/deactivate, optional Gemini summaries, and a clearly labelled non-AI extractive fallback.
- **Timetable**: weekly grid, add/edit/delete entries, semester filtering, room/faculty/time conflict checks, and editable demo academic information.
- **AI assistant**: database-grounded answers about assignments, attendance, timetable, and notices, with visible tool/source evidence and honest database fallback.
- **Settings**: AI model allowlist, live Gemini connection test, key-status guidance, local database counts, and limitations.

Every record action is persisted in SQLite. Reminders are generated inside the app and deduplicated per day; no external messages are sent.

## Tech stack

- Python 3.11
- Streamlit 1.57+ (installed environment used for development and testing)
- SQLite through the Python standard library
- pandas
- python-dotenv
- google-genai (optional AI features)
- pytest

## Quick start on Windows

From the project folder in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open the URL printed by Streamlit, usually `http://localhost:8501`.

If port 8501 is already in use:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8502
```

The database is created automatically at `data/smart_university.db` and seeded once with fictional demo data. Dates in the sample records are relative to the day the database is first created.

## Demo roles

The sidebar role selector has **Faculty** and **Student** modes:

- **Faculty** can add/edit/deactivate records and access management forms.
- **Student** shows read-only views and student submission actions for the selected demo student.

This is a demonstration control only. There is **no authentication, identity verification, password system, or real authorization**. Do not treat it as a security boundary.

## Optional Gemini setup

The app works without any API key. In database-only mode, the assistant routes questions to SQLite and writes deterministic answers.

To enable optional AI phrasing and notice summaries, create `.env` from the example:

```powershell
Copy-Item .env.example .env
```

Then set:

```text
GEMINI_API_KEY=your_key_here
```

Alternatively, add the key to `.streamlit/secrets.toml`:

```toml
GEMINI_API_KEY = "your_key_here"
```

Never commit `.env` or `.streamlit/secrets.toml`. The key is read from configuration and is never displayed, logged, or stored in the database.

The allowlisted models are:

- `gemini-3.5-flash-lite` (default)
- `gemini-3.8-flash`
- `gemini-3.6-flash`
- `gemini-2.5-flash-lite`
- `gemini-2.5-flash`

Model availability and free-tier quotas can change. The app does not claim unlimited Gemini access. Use **Settings → Test Gemini connection** to make one small live request and see the real result.

### AI safety and grounding

- The assistant uses explicit intent routing plus an allowlisted, typed, read-only tool registry.
- It never executes generated SQL, Python, shell commands, `eval`, or `exec`.
- It never exposes API credentials.
- If Gemini is unavailable, errors, or hits quota, the app labels the failure and returns the database-grounded answer instead of fabricating an AI response.
- AI answers can still be phrased incorrectly; verify important details against the stored records.

## Testing

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Verified result in this workspace:

```text
26 passed
```

Test coverage includes:

- schema creation and idempotent demo seeding
- settings persistence
- student CRUD, validation, search, and active-state changes
- attendance upsert, percentages, and inactive-student rejection
- assignment statuses, submissions, deadlines, and submission counts
- notice filters, management, and extractive fallback
- timetable conflict detection and CRUD
- reminder generation and same-day deduplication
- AI DB routing, mocked Gemini phrasing, and failure fallback
- Streamlit smoke tests for every page in both Faculty and Student demo modes

No live Gemini request was made during automated tests, so no test claims a real provider response. The live connection test is intentionally user-triggered in Settings.

## Project structure

```text
.
├── app.py                     # Streamlit entry point and navigation
├── app_pages/
│   ├── dashboard.py
│   ├── students.py
│   ├── attendance.py
│   ├── assignments.py
│   ├── notices.py
│   ├── timetable.py
│   ├── ai_assistant.py
│   └── settings.py
├── services/
│   ├── database.py            # Schema, transactions, seeding, settings
│   ├── student_service.py
│   ├── attendance_service.py
│   ├── assignment_service.py
│   ├── notice_service.py
│   ├── timetable_service.py
│   ├── reminder_service.py
│   ├── ai_tools.py            # Allowlisted read-only tools
│   └── ai_assistant.py        # Intent router, Gemini layer, fallbacks
├── utils/
│   ├── config.py
│   ├── validation.py
│   └── ui.py
├── tests/
├── data/                      # Local database, ignored by git
├── .streamlit/config.toml     # Light university theme
├── .env.example
├── requirements.txt
└── README.md
```

## Data model

SQLite tables:

- `students`
- `subjects`
- `attendance` (Present, Absent, Late)
- `assignments`
- `assignment_submissions` (Submitted, Late)
- `notices`
- `timetable`
- `reminders`
- `app_settings`

Attendance percentage is calculated as:

```text
(Present + Late) / total recorded attendance × 100
```

Assignments display one of `Pending`, `Submitted`, `Late`, or `Overdue`. Demo submission records a timestamped flag only; there is no file upload.

## Reset the demo database

Close the app, then from PowerShell:

```powershell
Remove-Item .\data\smart_university.db*
```

Start the app again to recreate and reseed the database.

To use a different database path, set in `.env`:

```text
SMART_UNI_DB_PATH=data/my_demo.db
```

## Honest limitations

- No real authentication, authorization, or multi-user concurrency design.
- All records are fictional and should remain fictional.
- Assignment submission is a flag only; no document storage or upload.
- Reminders are in-app only; no email, SMS, WhatsApp, or push integration.
- AI features require a key, network access, provider quota, and a supported model.
- AI can phrase results incorrectly even when grounded; source records are shown for verification.
- Streamlit and SQLite are used as a local classroom prototype, not a production deployment.
- Live Gemini behavior could not be verified without an API key in this environment.

## Troubleshooting

- **Python compatibility**: use Python 3.11 or 3.12 if the default Python version causes dependency issues.
- **Port conflict**: pass `--server.port 8502` or another free port.
- **Gemini 401/403**: check the key and that the Generative Language API is enabled.
- **Gemini 429**: wait for quota reset or choose a lighter supported model.
- **Gemini 404/model error**: choose another model from the Settings allowlist.
- **No AI summary**: confirm the key is detected and use Settings → Test Gemini connection.
- **Database locked**: close duplicate Streamlit processes, then retry.
- **Unexpected seed data**: remember sample dates are generated relative to the first initialization day.
