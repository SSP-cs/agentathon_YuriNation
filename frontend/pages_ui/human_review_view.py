import streamlit as st
import json
from database.crud import get_pending_escalations, record_escalation_review
from backend.schemas import ClaimStatus

def render_human_review():
    st.markdown("### 🧑‍⚖️ Human Escalation Review Queue")
    st.markdown("When the decision engine detects unsupported claims, model hallucinations, or policy contradictions that persist after retries, answers are withheld and routed here for compliance review.")

    escalations = get_pending_escalations()

    if not escalations:
        st.success("🎉 No pending escalations in queue. All recent inquiries have either been verified or resolved!")
        return

    st.warning(f"⚠️ **{len(escalations)} case(s) requiring human review**")

    # Select an escalation to inspect
    case_options = [f"Case {e['session_id'][:8]} — {e['question'][:65]}..." for e in escalations]
    selected_idx = st.selectbox("Select an Escalation Case to Inspect:", range(len(case_options)), format_func=lambda i: case_options[i])
    
    current_case = escalations[selected_idx]

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # Case Details Box
    st.markdown(f"""
    <div style="background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <span style="font-size: 14px; font-weight: 700; color: #f87171;">ESCALATION ID: {current_case['session_id']}</span>
            <span class="badge-retry">Retries Attempted: {current_case['retry_count']}</span>
        </div>
        <div style="font-size: 16px; font-weight: 600; color: #ffffff; margin-bottom: 8px;">
            Question: "{current_case['question']}"
        </div>
        <div style="font-size: 13px; color: #cbd5e1; background: #0b1120; padding: 10px; border-radius: 6px; border-left: 3px solid #ef4444;">
            <b>Auditor Flag:</b> {current_case['reason']}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Side-by-side agent comparison
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("##### 🤖 Agent A Proposed Answer")
        st.markdown(f"""
        <div class="agent-box">
            <div style="font-size: 13px; line-height: 1.5;">{current_case['agent_a_answer']}</div>
        </div>
        """, unsafe_allow_html=True)
    with col_b:
        st.markdown("##### 🤖 Agent B Proposed Answer")
        st.markdown(f"""
        <div class="agent-box">
            <div style="font-size: 13px; line-height: 1.5;">{current_case['agent_b_answer']}</div>
        </div>
        """, unsafe_allow_html=True)

    # Claims breakdown
    st.markdown("##### 🚩 Flagged Unsupported or Contradictory Claims")
    claims = current_case.get("claims", [])
    for c in claims:
        status = c.get("status", "UNSUPPORTED")
        badge = "badge-supported" if status == "SUPPORTED" else "badge-contradicted" if status == "CONTRADICTED" else "badge-unsupported"
        st.markdown(f"""
        <div style="background: #0d1527; border: 1px solid #1e293b; border-radius: 6px; padding: 10px 14px; margin-bottom: 8px;">
            <div style="display: flex; justify-content: space-between;">
                <span style="font-weight: 600; font-family: monospace; color: #38bdf8;">{c.get('claim_id')} ({c.get('source_agent')})</span>
                <span class="{badge}">{status}</span>
            </div>
            <div style="font-size: 13px; color: #e2e8f0; margin-top: 4px;">"{c.get('claim_text')}"</div>
            <div style="font-size: 12px; color: #94a3b8; margin-top: 4px;"><b>Audit Note:</b> {c.get('reasoning')}</div>
        </div>
        """, unsafe_allow_html=True)

    # Retry history
    retry_hist = current_case.get("retry_history", [])
    if retry_hist:
        with st.expander("View Automated Retry Execution Log"):
            st.json(retry_hist)

    st.markdown("<hr style='border: 1px solid #1e293b; margin: 20px 0;'>", unsafe_allow_html=True)

    # Reviewer Action Form
    st.markdown("##### ✍️ Supervisor Decision & Audit Sign-Off")
    with st.form("reviewer_form"):
        reviewer_name = st.text_input("Reviewer Name / ID:", value="Senior Compliance Officer")
        reviewer_comments = st.text_area(
            "Reviewer Justification & Audit Notes:",
            placeholder="Explain why this response is approved, rejected, or requires additional evidence documentation..."
        )

        col_app, col_rej, col_req = st.columns(3)
        with col_app:
            approve_btn = st.form_submit_button("✅ Approve Answer", use_container_width=True)
        with col_rej:
            reject_btn = st.form_submit_button("❌ Reject & Block Answer", use_container_width=True)
        with col_req:
            req_btn = st.form_submit_button("📑 Request More Evidence", use_container_width=True)

    if approve_btn:
        record_escalation_review(
            session_id=current_case["session_id"],
            decision="APPROVE",
            notes=reviewer_comments or "Approved with supervisory override.",
            reviewer=reviewer_name
        )
        st.success("Case approved and recorded in audit log.")
        st.rerun()

    if reject_btn:
        record_escalation_review(
            session_id=current_case["session_id"],
            decision="REJECT",
            notes=reviewer_comments or "Rejected due to hallucinated or unsupported claims.",
            reviewer=reviewer_name
        )
        st.error("Case rejected. Answer blocked from reaching customer.")
        st.rerun()

    if req_btn:
        record_escalation_review(
            session_id=current_case["session_id"],
            decision="REQUEST_EVIDENCE",
            notes=reviewer_comments or "Additional policy documentation requested.",
            reviewer=reviewer_name
        )
        st.info("Additional evidence requested. Recorded in audit log.")
        st.rerun()

