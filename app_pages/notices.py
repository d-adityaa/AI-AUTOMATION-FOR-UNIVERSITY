"""Notice board with search, optional AI summaries, and faculty management."""

from __future__ import annotations

from datetime import date

import streamlit as st

from services import notice_service
from services.ai_assistant import AIError, summarize_notice
from utils.config import ai_is_configured
from utils.ui import (
    empty_state,
    faculty_only_notice,
    is_faculty,
    page_header,
    set_flash,
    status_badge,
)
from utils.validation import ValidationError

today = date.today()
page_header(
    "Notices",
    "Current and archived demo notices. All notices are fictional and stored locally.",
    ":material/campaign:",
)

faculty = is_faculty()
if not faculty:
    faculty_only_notice()

tabs = st.tabs(["Notice board", "Add notice", "Manage notices"] if faculty else ["Notice board"])
board_tab = tabs[0]
add_tab = tabs[1] if faculty else None
manage_tab = tabs[2] if faculty else None
ai_summaries: dict[int, str] = st.session_state.setdefault("notice_ai_summaries", {})
ai_available = ai_is_configured()

with board_tab:
    with st.container(border=True):
        st.subheader("Search notices", icon=":material/search:")
        filter_columns = st.columns([2, 1])
        with filter_columns[0]:
            search = st.text_input(
                "Search",
                placeholder="Search title, content, or category",
                key="notice_search",
            )
        with filter_columns[1]:
            category = st.selectbox(
                "Category",
                options=["All"] + list(notice_service.NOTICE_CATEGORIES),
                key="notice_category_filter",
            )
        show_archived = False
        if faculty:
            show_archived = st.toggle(
                "Show expired and inactive notices",
                value=False,
                key="notice_show_archived",
            )

    notices = notice_service.list_notices(
        search=search,
        category=None if category == "All" else category,
        current_only=not show_archived,
        include_inactive=show_archived,
        today=today,
    )
    st.caption(
        f"{len(notices)} notice(s) shown. "
        "Expired notices are hidden in the default current view for all roles."
    )
    if not notices:
        empty_state("No notices match the current search and filters.")
    else:
        for notice in notices:
            with st.container(border=True):
                heading_col, badge_col = st.columns([4, 1])
                with heading_col:
                    st.subheader(notice["title"], icon=":material/campaign:")
                    st.caption(
                        f"{notice['category']} · Published {notice['publish_date']} · "
                        f"Expires {notice['expiry_date'] or 'never'}"
                    )
                with badge_col:
                    status_badge("Active" if notice["is_active"] else "Inactive")
                st.markdown(notice["content"])

                if notice["expiry_date"] and notice["expiry_date"] < today.isoformat():
                    st.badge("Expired", icon=":material/event_busy:", color="red")
                elif notice["expiry_date"] == today.isoformat():
                    st.badge("Expires today", icon=":material/schedule:", color="orange")

                with st.expander("Summarize this notice", icon=":material/summarize:"):
                    if ai_available:
                        if st.button(
                            "Summarize with AI",
                            icon=":material/auto_awesome:",
                            key=f"summarize_notice_{notice['id']}",
                        ):
                            try:
                                with st.spinner("Requesting a short Gemini summary…"):
                                    summary = summarize_notice(notice)
                            except AIError as exc:
                                st.error(str(exc), icon=":material/error:")
                                st.caption("The stored notice text is unchanged; no AI summary was produced.")
                            else:
                                ai_summaries[notice["id"]] = summary
                                st.success("AI summary generated from this notice only.")
                        if notice["id"] in ai_summaries:
                            st.info(ai_summaries[notice["id"]], icon=":material/auto_awesome:")
                        st.caption("AI summaries are optional and can be inaccurate. Verify against the notice text.")
                    else:
                        st.caption(
                            "AI summarization requires GEMINI_API_KEY or Streamlit secrets. "
                            "The fallback below does not use AI."
                        )
                    with st.expander("Show basic extractive summary (not AI)"):
                        st.write(notice_service.basic_extractive_summary(notice["content"]))
                        st.caption("This is only the first few sentences of the stored notice, not an AI summary.")

if faculty and add_tab is not None:
    with add_tab:
        with st.container(border=True):
            st.subheader("Add a notice", icon=":material/add_alert:")
            with st.form("add_notice_form"):
                title = st.text_input("Title", placeholder="DEMO: Mid-semester examination timetable")
                content = st.text_area(
                    "Content",
                    placeholder="Write the fictional notice text here.",
                    height=180,
                )
                category = st.selectbox("Category", options=list(notice_service.NOTICE_CATEGORIES))
                date_columns = st.columns(2)
                with date_columns[0]:
                    publish_date = st.date_input("Publish date", value=today)
                with date_columns[1]:
                    expiry_date = st.date_input("Expiry date (optional)", value=None)
                submitted = st.form_submit_button("Add notice", icon=":material/add_alert:", type="primary")
            if submitted:
                try:
                    notice_service.add_notice(title, content, category, publish_date, expiry_date)
                except ValidationError as exc:
                    st.error(str(exc), icon=":material/error:")
                else:
                    set_flash("Notice added to the local demo notice board.")
                    st.rerun()

if faculty and manage_tab is not None:
    with manage_tab:
        all_notices = notice_service.list_notices(
            current_only=False, include_inactive=True, today=today
        )
        if not all_notices:
            empty_state("There are no notices to manage.")
        else:
            labels = {
                notice["id"]: f"{notice['title']} ({'active' if notice['is_active'] else 'inactive'})"
                for notice in all_notices
            }
            notice_ids = [notice["id"] for notice in all_notices]
            selected_notice_id = st.selectbox(
                "Notice to edit",
                options=notice_ids,
                format_func=lambda notice_id: labels[notice_id],
                key="notice_manage_select",
            )
            notice = notice_service.get_notice(selected_notice_id)
            if notice:
                with st.container(border=True):
                    st.subheader("Edit notice", icon=":material/edit_note:")
                    status_badge("Active" if notice["is_active"] else "Inactive")
                    expiry_default = (
                        date.fromisoformat(notice["expiry_date"]) if notice["expiry_date"] else None
                    )
                    with st.form(f"edit_notice_form_{selected_notice_id}"):
                        edit_title = st.text_input("Title", value=notice["title"])
                        edit_content = st.text_area("Content", value=notice["content"], height=200)
                        edit_category = st.selectbox(
                            "Category",
                            options=list(notice_service.NOTICE_CATEGORIES),
                            index=list(notice_service.NOTICE_CATEGORIES).index(notice["category"]),
                        )
                        date_columns = st.columns(2)
                        with date_columns[0]:
                            edit_publish = st.date_input(
                                "Publish date",
                                value=date.fromisoformat(notice["publish_date"]),
                            )
                        with date_columns[1]:
                            edit_expiry = st.date_input("Expiry date (optional)", value=expiry_default)
                        saved = st.form_submit_button(
                            "Save notice", icon=":material/save:", type="primary"
                        )
                    if saved:
                        try:
                            notice_service.update_notice(
                                selected_notice_id,
                                edit_title,
                                edit_content,
                                edit_category,
                                edit_publish,
                                edit_expiry,
                            )
                        except ValidationError as exc:
                            st.error(str(exc), icon=":material/error:")
                        else:
                            ai_summaries.pop(selected_notice_id, None)
                            set_flash("Notice updated. Any cached AI summary for it was cleared.")
                            st.rerun()

                    if notice["is_active"]:
                        if st.button(
                            "Deactivate notice",
                            icon=":material/visibility_off:",
                            key=f"deactivate_notice_{selected_notice_id}",
                        ):
                            try:
                                notice_service.deactivate_notice(selected_notice_id)
                            except ValidationError as exc:
                                st.error(str(exc), icon=":material/error:")
                            else:
                                set_flash("Notice deactivated.", "warning")
                                st.rerun()
                    else:
                        if st.button(
                            "Reactivate notice",
                            icon=":material/visibility:",
                            key=f"reactivate_notice_{selected_notice_id}",
                        ):
                            try:
                                notice_service.reactivate_notice(selected_notice_id)
                            except ValidationError as exc:
                                st.error(str(exc), icon=":material/error:")
                            else:
                                set_flash("Notice reactivated.")
                                st.rerun()
