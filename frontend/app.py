import streamlit as st
import os
import sys

# Ensure root workspace directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from frontend.styles import CUSTOM_CSS
from frontend.pages_ui.dashboard_view import render_dashboard
from frontend.pages_ui.ask_policy_view import render_ask_policy
from frontend.pages_ui.documents_view import render_documents
from frontend.pages_ui.human_review_view import render_human_review
from frontend.pages_ui.audit_logs_view import render_audit_logs
from frontend.pages_ui.evaluation_view import render_evaluations
from retrieval.retriever import retriever
from evaluations.benchmark import seed_sample_documents

# Set Streamlit Page Config
st.set_page_config(
    page_title="TrustLayer — AI Policy Verification System",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply Cyber Theme CSS
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# Auto-seed sample policy documents if index is empty
if retriever.count_chunks() == 0:
    try:
        seed_sample_documents()
    except Exception as e:
        print(f"Auto-seed warning: {e}")

# Header Bar
st.markdown("""
<div class="trustlayer-header">
    <div class="trustlayer-logo">
        <span style="font-size: 32px;">🛡️</span>
        <div>
            <div class="trustlayer-title">TRUSTLAYER</div>
            <div class="trustlayer-subtitle">AI Policy Verification & Governance System • Agentathon 2026 (YuriNation)</div>
        </div>
    </div>
    <div style="display: flex; gap: 12px; align-items: center;">
        <span class="status-badge-active">● ZERO-TRUST PIPELINE ACTIVE</span>
        <span style="background: #1e293b; color: #94a3b8; padding: 6px 12px; border-radius: 20px; font-size: 11px; font-weight: 600; border: 1px solid #334155;">
            RV College of Engineering
        </span>
    </div>
</div>
""", unsafe_allow_html=True)

# Sidebar Navigation
with st.sidebar:
    st.markdown("### 🎛️ Navigation")
    page = st.radio(
        "Select Console:",
        [
            "📊 Dashboard",
            "💬 Ask a Policy Question",
            "📁 Document Management",
            "🧑‍⚖️ Human Review",
            "📜 Audit Logs",
            "📈 Evaluation Metrics"
        ]
    )

    st.markdown("<hr style='border: 1px solid #1e293b; margin: 20px 0;'>", unsafe_allow_html=True)
    st.markdown("##### 🏛️ Governance Model")
    st.caption("""
    - **Dual Independent LLMs**: Parallel generation with no shared hallucination vector.
    - **Zero-Trust Auditor**: Source evidence is the sole arbiter of truth.
    - **Adaptive Retries**: Top-k widening with max 2 retries.
    - **Escalation Gateway**: Unsubstantiated claims never reach customers.
    """)

# Page Router
if page == "📊 Dashboard":
    render_dashboard()
elif page == "💬 Ask a Policy Question":
    render_ask_policy()
elif page == "📁 Document Management":
    render_documents()
elif page == "🧑‍⚖️ Human Review":
    render_human_review()
elif page == "📜 Audit Logs":
    render_audit_logs()
elif page == "📈 Evaluation Metrics":
    render_evaluations()

