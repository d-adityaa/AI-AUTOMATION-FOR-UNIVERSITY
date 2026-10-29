"""Application configuration and environment handling."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=False)

DEFAULT_DB_PATH = BASE_DIR / "data" / "smart_university.db"
DEFAULT_AI_PROVIDER = "Google Gemini"
DEFAULT_AI_MODEL = "gemini-3.5-flash-lite"
SUPPORTED_AI_MODELS = (
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
)
AI_REQUEST_TIMEOUT_SECONDS = 30
AI_TEST_TIMEOUT_SECONDS = 15
DEMO_DATA_LABEL = "DEMO data: all records are fictional and for classroom use only."


def get_db_path() -> Path:
    """Return the active SQLite database path."""
    configured = os.getenv("SMART_UNI_DB_PATH", "").strip()
    return Path(configured) if configured else DEFAULT_DB_PATH


def get_gemini_api_key() -> str | None:
    """Read the Gemini key from the environment, then Streamlit secrets.

    The value is never displayed or logged by the application.
    """
    environment_key = os.getenv("GEMINI_API_KEY", "").strip()
    if environment_key:
        return environment_key

    try:
        import streamlit as st

        try:
            secret_value = st.secrets.get("GEMINI_API_KEY", "")
        except Exception:
            secret_value = ""
        secret_value = str(secret_value).strip()
        return secret_value or None
    except Exception:
        return None


def ai_is_configured() -> bool:
    return get_gemini_api_key() is not None
