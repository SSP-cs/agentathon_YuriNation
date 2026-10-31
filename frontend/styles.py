CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* Global app styling */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color: #e2e8f0;
}

.stApp {
    background-color: #0b1120;
    color: #e2e8f0;
}

/* Sidebar styling */
[data-testid="stSidebar"] {
    background-color: #0f172a !important;
    border-right: 1px solid #1e293b;
}

/* Header bar */
.trustlayer-header {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 20px 28px;
    margin-bottom: 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
}

.trustlayer-logo {
    display: flex;
    align-items: center;
    gap: 14px;
}

.trustlayer-title {
    font-size: 24px;
    font-weight: 800;
    letter-spacing: 1.5px;
    color: #ffffff;
    margin: 0;
}

.trustlayer-subtitle {
    font-size: 12px;
    color: #94a3b8;
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 1px;
}

.status-badge-active {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(16, 185, 129, 0.15);
    color: #10b981;
    border: 1px solid rgba(16, 185, 129, 0.3);
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
}

/* Metric card */
.cyber-card {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 18px 20px;
    transition: all 0.2s ease;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
}

.cyber-card:hover {
    border-color: #38bdf8;
    box-shadow: 0 4px 16px rgba(56, 189, 248, 0.15);
}

.card-title {
    font-size: 12px;
    font-weight: 600;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}

.card-value {
    font-size: 28px;
    font-weight: 700;
    color: #ffffff;
    margin-top: 6px;
    font-family: 'JetBrains Mono', monospace;
}

.card-caption {
    font-size: 11px;
    color: #64748b;
    margin-top: 4px;
}

/* Claim badges */
.badge-supported {
    background: rgba(16, 185, 129, 0.15);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.4);
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    display: inline-block;
}

.badge-unsupported {
    background: rgba(239, 68, 68, 0.15);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.4);
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    display: inline-block;
}

.badge-contradicted {
    background: rgba(220, 38, 38, 0.25);
    color: #fca5a5;
    border: 1px solid rgba(220, 38, 38, 0.6);
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
    display: inline-block;
}

.badge-retry {
    background: rgba(245, 158, 11, 0.15);
    color: #fbbf24;
    border: 1px solid rgba(245, 158, 11, 0.4);
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    display: inline-block;
}

/* Agent Answer Comparison Box */
.agent-box {
    background: #0d1527;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
}

.agent-title {
    font-size: 13px;
    font-weight: 700;
    color: #38bdf8;
    margin-bottom: 8px;
    display: flex;
    justify-content: space-between;
}

.verified-answer-box {
    background: rgba(16, 185, 129, 0.08);
    border: 1px solid rgba(16, 185, 129, 0.4);
    border-left: 4px solid #10b981;
    border-radius: 8px;
    padding: 18px 22px;
    margin-top: 14px;
    margin-bottom: 14px;
}

.escalation-box {
    background: rgba(239, 68, 68, 0.08);
    border: 1px solid rgba(239, 68, 68, 0.4);
    border-left: 4px solid #ef4444;
    border-radius: 8px;
    padding: 18px 22px;
    margin-top: 14px;
    margin-bottom: 14px;
}

/* Citations & Evidence */
.citation-tag {
    background: #1e293b;
    color: #38bdf8;
    border: 1px solid #334155;
    padding: 2px 7px;
    border-radius: 4px;
    font-size: 11px;
    font-family: 'JetBrains Mono', monospace;
}

/* Streamlit button custom */
div.stButton > button {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: 600;
    font-size: 13px;
    transition: background-color 0.2s;
}

div.stButton > button:hover {
    background-color: #1d4ed8;
    border: none;
    color: #ffffff;
}
</style>
"""

