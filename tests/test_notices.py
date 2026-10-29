"""Notice board filtering, management, and extractive fallback tests."""

from __future__ import annotations

from datetime import date

import pytest

from services.notice_service import (
    add_notice,
    basic_extractive_summary,
    deactivate_notice,
    get_notice,
    list_notices,
    reactivate_notice,
    update_notice,
)
from utils.validation import ValidationError

REFERENCE_DAY = date(2026, 10, 29)


def test_notice_current_expired_search_and_management(empty_db):
    current_id = add_notice(
        "DEMO Examination notice",
        "DEMO: The examination schedule is available. Bring a hall ticket.",
        "Examination",
        REFERENCE_DAY.replace(day=27),
        REFERENCE_DAY.replace(day=31),
        db_path=empty_db,
    )
    expired_id = add_notice(
        "DEMO Expired holiday",
        "DEMO: This holiday notice has already expired.",
        "Holiday",
        REFERENCE_DAY.replace(day=1),
        REFERENCE_DAY.replace(day=15),
        db_path=empty_db,
    )

    current = list_notices(today=REFERENCE_DAY, db_path=empty_db)
    assert [notice["id"] for notice in current] == [current_id]
    assert list_notices(search="hall ticket", today=REFERENCE_DAY, db_path=empty_db)[0]["id"] == current_id
    assert list_notices(category="Holiday", today=REFERENCE_DAY, db_path=empty_db) == []

    everything = list_notices(current_only=False, today=REFERENCE_DAY, db_path=empty_db)
    assert {notice["id"] for notice in everything} == {current_id, expired_id}

    update_notice(
        current_id,
        "DEMO Updated examination notice",
        "DEMO: Updated examination content with a new room.",
        "Academic",
        REFERENCE_DAY.replace(day=28),
        None,
        db_path=empty_db,
    )
    updated = get_notice(current_id, db_path=empty_db)
    assert updated["title"] == "DEMO Updated examination notice"
    assert updated["category"] == "Academic"
    assert updated["expiry_date"] is None

    deactivate_notice(current_id, db_path=empty_db)
    assert get_notice(current_id, db_path=empty_db)["is_active"] is False
    remaining = list_notices(current_only=False, today=REFERENCE_DAY, db_path=empty_db)
    assert [notice["id"] for notice in remaining] == [expired_id]
    assert len(
        list_notices(
            current_only=False,
            include_inactive=True,
            today=REFERENCE_DAY,
            db_path=empty_db,
        )
    ) == 2

    reactivate_notice(current_id, db_path=empty_db)
    assert get_notice(current_id, db_path=empty_db)["is_active"] is True


def test_notice_validation_and_extractive_summary(empty_db):
    with pytest.raises(ValidationError, match="category"):
        add_notice("DEMO Invalid category", "DEMO content", "Unknown", REFERENCE_DAY, db_path=empty_db)

    with pytest.raises(ValidationError, match="Expiry date"):
        add_notice(
            "DEMO Invalid expiry",
            "DEMO content",
            "General",
            REFERENCE_DAY,
            REFERENCE_DAY.replace(day=1),
            db_path=empty_db,
        )

    summary = basic_extractive_summary(
        "First sentence. Second sentence. Third sentence. Fourth sentence.",
        max_sentences=2,
    )
    assert summary == "First sentence. Second sentence."
    assert basic_extractive_summary("   ") == ""
