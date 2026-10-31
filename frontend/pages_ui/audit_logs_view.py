import streamlit as st
import pandas as pd
from database.crud import get_audit_logs

def render_audit_logs():
    st.markdown("### 📜 Tamper-Evident Audit Trail")
    st.markdown("Immutable record of all retrieval executions, parallel agent outputs, claim extractions, auditor verdicts, automated retries, and human supervisory decisions.")

    col_search, col_filter, col_limit = st.columns([2, 1, 1])
    with col_search:
        search_query = st.text_input("🔍 Search Logs by Keyword / Session ID:", placeholder="e.g. overdraft, wire, CLM-001...")
    with col_filter:
        event_filter = st.selectbox(
            "Filter Event Type:",
            ["ALL", "VERIFICATION_COMPLETED", "RETRIEVAL_EXECUTED", "AGENTS_GENERATED", "AUDITOR_EVALUATED", "HUMAN_REVIEW_DECIDED", "DOCUMENT_INDEXED"]
        )
    with col_limit:
        log_limit = st.selectbox("Max Rows:", [25, 50, 100, 200], index=1)

    logs = get_audit_logs(limit=log_limit, search=search_query or None, event_type=event_filter)

    st.markdown(f"**Showing {len(logs)} audit events:**")

    if not logs:
        st.info("No matching audit logs found.")
        return

    # Render as interactive expandable list with cyber cards
    for l in logs:
        badge_color = "#38bdf8"
        if "COMPLETED" in l["event_type"]:
            badge_color = "#10b981"
        elif "HUMAN" in l["event_type"]:
            badge_color = "#fbbf24"
        elif "DELETED" in l["event_type"] or "FAILED" in l["event_type"]:
            badge_color = "#ef4444"

        with st.expander(f"[{l['created_at'][:19]}] {l['event_type']} — {l['summary'][:80]}", expanded=False):
            st.markdown(f"""
            - **Event ID**: `{l['id']}`
            - **Session ID**: `{l['session_id'] or 'System-Level'}`
            - **Timestamp**: `{l['created_at']}`
            - **Summary**: {l['summary']}
            """)
            if l.get("details"):
                st.markdown("**Structured Event Payload:**")
                st.json(l["details"])

