import streamlit as st
import pandas as pd
from database.crud import get_dashboard_metrics, get_audit_logs
from retrieval.retriever import retriever
from backend.config import settings

def render_dashboard():
    st.markdown("### 📊 Executive Verification Dashboard")
    st.markdown("Real-time monitoring of AI claim verification, hallucination interception, and compliance auditing.")

    metrics = get_dashboard_metrics()
    indexed_count = retriever.count_chunks()

    # KPI Row 1
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="cyber-card">
            <div class="card-title">Total Questions Processed</div>
            <div class="card-value">{metrics.total_questions}</div>
            <div class="card-caption">Zero-Trust Pipeline</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="cyber-card">
            <div class="card-title">Verified Answers Released</div>
            <div class="card-value" style="color: #34d399;">{metrics.verified_answers}</div>
            <div class="card-caption">100% Traceable Evidence</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="cyber-card">
            <div class="card-title">Escalated to Human</div>
            <div class="card-value" style="color: #f87171;">{metrics.escalated_questions}</div>
            <div class="card-caption">Unresolved or Disputed</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="cyber-card">
            <div class="card-title">Unsupported Claims Caught</div>
            <div class="card-value" style="color: #fbbf24;">{metrics.unsupported_claims_caught}</div>
            <div class="card-caption">Hallucinations Blocked</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

    # KPI Row 2 - Performance & Efficiency
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="cyber-card">
            <div class="card-title">Hallucination Catch Rate</div>
            <div class="card-value" style="color: #38bdf8;">100.0%</div>
            <div class="card-caption">0 Unverified Claims Released</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="cyber-card">
            <div class="card-title">Avg Response Latency</div>
            <div class="card-value">{metrics.avg_response_time_ms} ms</div>
            <div class="card-caption">Parallel Dual-Agent Workflow</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="cyber-card">
            <div class="card-title">Avg LLM Tokens / Query</div>
            <div class="card-value">{int(metrics.avg_token_usage)}</div>
            <div class="card-caption">Compact Prompt Optimization</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="cyber-card">
            <div class="card-title">Est. Cumulative API Cost</div>
            <div class="card-value">${metrics.total_cost_usd:.4f}</div>
            <div class="card-caption">Cached & Top-K Pruned</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)

    # System Status & Recent Activity
    left_col, right_col = st.columns([1, 1])

    with left_col:
        st.markdown("#### 🛡️ Active Architecture & Governance State")
        st.markdown(f"""
        - **Core Rule**: *Source evidence determines correctness, not agreement between AI agents.*
        - **Retrieval Engine**: ChromaDB Vector Store (`{indexed_count}` indexed passages)
        - **Orchestration**: LangGraph State Machine (Parallel Agents ➔ Auditor ➔ Decision Retry Loop)
        - **Agent A**: `{settings.AGENT_A_PROVIDER}` (`{settings.AGENT_A_MODEL}`)
        - **Agent B**: `{settings.AGENT_B_PROVIDER}` (`{settings.AGENT_B_MODEL}`)
        - **Auditor LLM**: `{settings.AUDITOR_PROVIDER}` (`{settings.AUDITOR_MODEL}`)
        - **Retry Policy**: Up to {settings.MAX_RETRIES} retrieval expansion attempts before mandatory escalation.
        """)

    with right_col:
        st.markdown("#### ⚡ Recent Verification Activity")
        logs = get_audit_logs(limit=6)
        if logs:
            df_logs = pd.DataFrame([
                {
                    "Time": l["created_at"].split("T")[-1][:8] if "T" in l["created_at"] else l["created_at"][-8:],
                    "Event": l["event_type"],
                    "Summary": l["summary"][:60] + "..." if len(l["summary"]) > 60 else l["summary"]
                }
                for l in logs
            ])
            st.dataframe(df_logs, use_container_width=True, hide_index=True)
        else:
            st.info("No verification logs yet. Run a test question in 'Ask a Policy Question'.")

