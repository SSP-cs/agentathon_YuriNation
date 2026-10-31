import streamlit as st
import json
import os
from backend.config import settings
from agents.orchestrator import run_verification_pipeline
from backend.schemas import ClaimStatus, DecisionVerdict

def render_ask_policy():
    st.markdown("### 💬 Ask a Policy Question")
    st.markdown("Enter a customer support policy inquiry. TrustLayer executes two independent AI agents in parallel, extracts atomic factual claims, verifies each claim against source policy documents, and blocks hallucinations.")

    # Load preset sample questions for quick testing
    sample_file = os.path.join(settings.BASE_DIR, "sample_data", "sample_questions.json")
    preset_questions = []
    if os.path.exists(sample_file):
        with open(sample_file, "r", encoding="utf-8") as f:
            preset_questions = json.load(f)

    st.markdown("##### 🧪 Quick Test Presets (Standard vs Hallucination Traps)")
    selected_preset = st.selectbox(
        "Choose a sample query or type custom below:",
        options=["-- Select a test scenario --"] + [f"[{q['type']}] {q['question']}" for q in preset_questions]
    )

    default_text = ""
    if selected_preset != "-- Select a test scenario --":
        # Extract the question part
        default_text = selected_preset.split("] ", 1)[-1]

    # Input form
    with st.form("ask_form"):
        user_question = st.text_area(
            "Customer Policy Question:",
            value=default_text,
            height=85,
            placeholder="e.g., Does ApexBank charge fees for outbound international wire transfers?"
        )
        col_btn, col_mode = st.columns([1, 2])
        with col_btn:
            submit_btn = st.form_submit_button("🛡️ Verify & Answer", use_container_width=True)
        with col_mode:
            force_simulation = st.checkbox("Force Deterministic Benchmark Mode (Demonstration)", value=True)

    if submit_btn and user_question.strip():
        with st.spinner("Executing Zero-Trust Verification Pipeline (Parallel Agents ➔ Auditor ➔ Evidence Alignment)..."):
            res = run_verification_pipeline(
                question=user_question.strip(),
                category="Policy",
                force_mock=force_simulation
            )

        st.session_state["last_verification_result"] = res

    # Display results if available
    res = st.session_state.get("last_verification_result")
    if res:
        st.markdown("<hr style='border: 1px solid #1e293b; margin: 24px 0;'>", unsafe_allow_html=True)
        
        # Verdict Banner
        if res.status == "VERIFIED_RELEASED":
            st.markdown(f"""
            <div class="verified-answer-box">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 700; color: #10b981; font-size: 16px;">
                        ✅ VERIFIED & APPROVED FOR RELEASE
                    </span>
                    <span class="badge-supported">Audit Confidence: {res.auditor.overall_confidence:.2f}</span>
                </div>
                <div style="margin-top: 10px; font-size: 14px; line-height: 1.6; color: #f1f5f9;">
                    {res.final_answer}
                </div>
                <div style="margin-top: 10px; font-size: 12px; color: #6ee7b7;">
                    Retries required: {res.decision.retry_count} | All {res.auditor.total_claims} claim(s) supported by source evidence.
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="escalation-box">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 700; color: #ef4444; font-size: 16px;">
                        ⚠️ UNRESOLVED: ESCALATED TO HUMAN SUPERVISOR
                    </span>
                    <span class="badge-unsupported">Status: ESCALATED (Retries: {res.decision.retry_count}/{settings.MAX_RETRIES})</span>
                </div>
                <div style="margin-top: 10px; font-size: 13px; color: #fca5a5;">
                    <b>Auditor Finding:</b> {res.auditor.auditor_explanation}
                </div>
                <div style="margin-top: 8px; font-size: 12px; color: #cbd5e1;">
                    Answer withheld to protect customer from AI hallucination. View and resolve in the <b>Human Review</b> panel.
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Tabs for details
        tab_claims, tab_agents, tab_evidence, tab_retries = st.tabs([
            "🔍 Claim-Level Verification",
            "🤖 Dual Agent Outputs (Parallel)",
            "📄 Retrieved Source Evidence",
            "🔄 Retry & Audit Trail"
        ])

        with tab_claims:
            st.markdown("##### Atomic Claim Verification Matrix")
            st.caption("Core Governance Principle: Source evidence determines correctness, NOT agreement between agents.")
            
            for c in res.auditor.claims:
                status_badge = "badge-supported"
                if c.status == ClaimStatus.UNSUPPORTED:
                    status_badge = "badge-unsupported"
                elif c.status == ClaimStatus.CONTRADICTED:
                    status_badge = "badge-contradicted"
                elif c.status == ClaimStatus.INSUFFICIENT_EVIDENCE:
                    status_badge = "badge-retry"

                with st.container():
                    st.markdown(f"""
                    <div style="background: #0d1527; border: 1px solid #1e293b; border-radius: 8px; padding: 14px; margin-bottom: 10px;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
                            <span style="font-weight: 600; color: #38bdf8; font-family: monospace;">{c.claim_id} ({c.source_agent})</span>
                            <span class="{status_badge}">{c.status.value if hasattr(c.status, 'value') else c.status}</span>
                        </div>
                        <div style="font-size: 13px; color: #f8fafc; margin-bottom: 8px;">
                            <b>Claim:</b> "{c.text}"
                        </div>
                        <div style="font-size: 12px; color: #94a3b8; background: #0b1120; padding: 8px; border-radius: 4px; border: 1px dashed #334155;">
                            <b>Source Evidence:</b> {c.evidence_text or 'None found in indexed policy context.'}<br>
                            <span style="color: #38bdf8;">Citation: {c.document_name or 'N/A'}, Page {c.page_number or 'N/A'}</span> | 
                            <span>Confidence: {c.confidence_score:.2f}</span>
                        </div>
                        <div style="font-size: 12px; color: #cbd5e1; margin-top: 6px;">
                            <b>Auditor Reasoning:</b> {c.reasoning}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        with tab_agents:
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"""
                <div class="agent-box">
                    <div class="agent-title">
                        <span>Agent A ({res.agent_a.provider})</span>
                        <span style="color: #94a3b8; font-size: 11px;">{res.agent_a.latency_ms} ms</span>
                    </div>
                    <div style="font-size: 11px; color: #64748b; margin-bottom: 8px;">Model: {res.agent_a.model_name}</div>
                    <div style="font-size: 13px; line-height: 1.5; color: #e2e8f0;">{res.agent_a.answer}</div>
                </div>
                """, unsafe_allow_html=True)
            with col_b:
                st.markdown(f"""
                <div class="agent-box">
                    <div class="agent-title">
                        <span>Agent B ({res.agent_b.provider})</span>
                        <span style="color: #94a3b8; font-size: 11px;">{res.agent_b.latency_ms} ms</span>
                    </div>
                    <div style="font-size: 11px; color: #64748b; margin-bottom: 8px;">Model: {res.agent_b.model_name}</div>
                    <div style="font-size: 13px; line-height: 1.5; color: #e2e8f0;">{res.agent_b.answer}</div>
                </div>
                """, unsafe_allow_html=True)

        with tab_evidence:
            st.markdown(f"##### Retrieved Policy Passages ({len(res.evidence)} chunks used)")
            for idx, ch in enumerate(res.evidence):
                with st.expander(f"Chunk {idx+1}: {ch.document_name} (Page {ch.page_number}) - Similarity Score: {ch.score:.4f}", expanded=(idx==0)):
                    st.markdown(f"```text\n{ch.text}\n```")

        with tab_retries:
            st.markdown("##### Decision Engine Lifecycle & Telemetry")
            st.json({
                "session_id": res.session_id,
                "final_verdict": res.decision.verdict.value if hasattr(res.decision.verdict, 'value') else res.decision.verdict,
                "decision_reason": res.decision.reason,
                "retry_count": res.decision.retry_count,
                "retry_history": res.retry_history,
                "total_tokens": res.total_tokens,
                "estimated_cost_usd": f"${res.estimated_cost_usd:.6f}",
                "total_latency_ms": f"{res.total_latency_ms} ms"
            })

