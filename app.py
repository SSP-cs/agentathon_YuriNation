"""TrustLayer dashboard: verify AI policy answers claim by claim."""
import sys, re, json, html
from pathlib import Path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from trustlayer.config import (ANSWER_MODEL_A, ANSWER_MODEL_B, AUDITOR_MODEL, EMBED_MODEL,
                               MOCK_LLM, MIN_SIM, SUPPORT_THRESHOLD, MAX_RETRIES)
from trustlayer.graph import run_trustlayer
from trustlayer.audit_db import get_runs, get_run_details
from trustlayer.retrieval import get_collection

st.set_page_config(page_title="TrustLayer", page_icon="🛡️", layout="wide", initial_sidebar_state="expanded")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Manrope:wght@400;500;600;700&display=swap');
:root{--bg:#0B1020;--sf:#121A30;--sf2:#18223F;--ln:#26325A;--tx:#E6E9F5;--mu:#8D97B8;--ok:#3DDC97;--wn:#FFB454;--bd:#FF6B7A;--ac:#7C8CFF}
html,body,[class*="css"],.stApp{font-family:'Manrope',system-ui,sans-serif}
.stApp{background:radial-gradient(1200px 500px at 85% -10%,#1A2550 0%,transparent 60%),var(--bg)}
.block-container{padding-top:1.6rem;max-width:1280px}
header[data-testid="stHeader"]{background:transparent}
h1,h2,h3,h4{font-family:'Fraunces',Georgia,serif!important;letter-spacing:-.01em}
.hero{display:flex;justify-content:space-between;align-items:flex-end;gap:2rem;margin-bottom:1.2rem}
.hero h1{font-size:3rem;margin:0;line-height:1}
.hero p{color:var(--mu);margin:.5rem 0 0;font-size:1.05rem;max-width:620px}
.pills{display:flex;gap:.5rem;flex-wrap:wrap;justify-content:flex-end}
.pill{border:1px solid var(--ln);background:var(--sf);color:var(--mu);padding:.3rem .75rem;border-radius:999px;font-size:.8rem}
.pill b{color:var(--tx);font-weight:600}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;background:var(--ok)}
.dot.m{background:var(--wn)}
.steps{display:flex;align-items:center;gap:.4rem;margin:.4rem 0 1.4rem;flex-wrap:wrap}
.step{flex:1;min-width:120px;background:var(--sf);border:1px solid var(--ln);border-radius:12px;padding:.65rem .85rem}
.step small{display:block;color:var(--mu);font-size:.72rem}
.step span{font-weight:600;font-size:.92rem}
.step.done{border-color:#3A4B8A;background:var(--sf2)}
.step.ok{border-color:var(--ok)}.step.ok span{color:var(--ok)}
.step.bad{border-color:var(--bd)}.step.bad span{color:var(--bd)}
.step.warn{border-color:var(--wn)}
.arrow{color:var(--ln);font-size:1.1rem}
.verdict{display:flex;gap:1.6rem;align-items:center;background:var(--sf);border:1px solid var(--ln);border-radius:20px;padding:1.4rem 1.8rem;margin-bottom:1rem}
.verdict.ok{border-color:#1E7A57;box-shadow:0 0 0 1px #1E7A5755,0 20px 50px -30px var(--ok)}
.verdict.bad{border-color:#9B3A47;box-shadow:0 0 0 1px #9B3A4755,0 20px 50px -30px var(--bd)}
.ring{position:relative;width:112px;height:112px;flex:none}
.ring svg{transform:rotate(-90deg)}
.ring div{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:'Fraunces',serif;font-size:1.7rem;font-weight:700}
.ring small{font:500 .65rem 'Manrope';color:var(--mu)}
.verdict h2{margin:0;font-size:1.7rem}
.verdict .sub{color:var(--mu);margin:.25rem 0 .8rem}
.stats{display:flex;gap:1.6rem;flex-wrap:wrap}
.stats div{font-size:.78rem;color:var(--mu)}.stats b{display:block;color:var(--tx);font-size:1.05rem}
.card{background:var(--sf);border:1px solid var(--ln);border-radius:16px;padding:1.1rem 1.3rem;height:100%}
.card h4{margin:0 0 .5rem;font-size:1.05rem}
.card .body{color:#CBD2EA;line-height:1.6;font-size:.93rem;white-space:pre-wrap}
.bar{height:6px;border-radius:6px;background:#0B1020;margin:.7rem 0 .2rem;overflow:hidden}
.bar i{display:block;height:100%;background:var(--ac)}
.cite{background:#26325A;color:#B9C3FF;border-radius:6px;padding:0 .35rem;font-size:.78rem;font-weight:600}
.claim{border-radius:12px;padding:.7rem .95rem;margin-bottom:.55rem;background:var(--sf);border:1px solid var(--ln);border-left-width:4px}
.claim.s{border-left-color:var(--ok)}.claim.u{border-left-color:var(--wn)}.claim.c{border-left-color:var(--bd)}
.claim .t{font-weight:600;font-size:.92rem}.claim .q{color:var(--mu);font-size:.82rem;margin-top:.25rem}
.tag{font-size:.7rem;font-weight:700;padding:.1rem .5rem;border-radius:6px;margin-right:.5rem}
.s .tag{background:#12382B;color:var(--ok)}.u .tag{background:#3B2D10;color:var(--wn)}.c .tag{background:#40161D;color:var(--bd)}
.split{display:flex;height:10px;border-radius:8px;overflow:hidden;margin:.3rem 0 1rem;background:#0B1020}
.kpi{background:var(--sf);border:1px solid var(--ln);border-radius:16px;padding:1rem 1.2rem}
.kpi small{color:var(--mu);font-size:.78rem}.kpi b{display:block;font-family:'Fraunces',serif;font-size:1.9rem;margin:.1rem 0}
.kpi i{font-style:normal;font-size:.78rem;color:var(--mu)}
.ev{border-left:2px solid var(--ln);padding:.2rem 0 .5rem .9rem;margin-left:.3rem;font-size:.86rem;color:#CBD2EA}
.ev b{color:var(--ac)}.ev small{color:var(--mu);display:block}
.stButton>button{border-radius:12px;border:1px solid var(--ln);background:var(--sf);color:var(--tx);font-weight:600;text-align:left}
.stButton>button:hover{border-color:var(--ac);color:#fff}
.stButton>button[kind="primary"]{background:var(--ac);border-color:var(--ac);color:#0B1020;text-align:center}
.stTextArea textarea{background:var(--sf);border:1px solid var(--ln);border-radius:14px}
.stTabs [data-baseweb="tab-list"]{gap:.4rem;border-bottom:1px solid var(--ln)}
.stTabs [data-baseweb="tab"]{padding:.6rem 1rem;border-radius:10px 10px 0 0}
section[data-testid="stSidebar"]{background:#0E1530;border-right:1px solid var(--ln)}
.mrow{display:flex;justify-content:space-between;font-size:.82rem;padding:.25rem 0;color:var(--mu)}.mrow b{color:var(--tx);font-weight:600}
@media(max-width:800px){.verdict{flex-direction:column;align-items:flex-start}.hero{flex-direction:column;align-items:flex-start}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

def H(s):  # collapse HTML so markdown never treats it as a code block
    return "".join(l.strip() for l in s.splitlines())
def esc(x): return html.escape(str(x or ""))
def cites(t): return re.sub(r"\[(S\d+)\]", r'<span class="cite">\1</span>', esc(t))
def kpi(label, value, note=""): return f'<div class="kpi"><small>{label}</small><b>{value}</b><i>{note}</i></div>'
def chart_style(fig, h=340):
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=h,
                      font=dict(family="Manrope", color="#CBD2EA"), margin=dict(l=10, r=10, t=40, b=10),
                      legend=dict(orientation="h", y=1.15, x=0), yaxis=dict(gridcolor="#26325A"))
    return fig

try: chunks = get_collection().count()
except Exception: chunks = "n/a"

with st.sidebar:
    st.markdown("### TrustLayer")
    st.caption("Dual-agent answer verification")
    st.markdown("**Team YuriNation** · RVCE")
    st.divider()
    st.markdown("##### Release rules")
    support_thresh = st.slider("Support needed to release", 0.50, 1.00, SUPPORT_THRESHOLD, 0.05, help="Share of claims that must be supported by the documents")
    min_sim_thresh = st.slider("Minimum evidence match", 0.10, 0.80, MIN_SIM, 0.05, help="Below this, the system reports no evidence")
    max_retries_val = st.slider("Retries before escalating", 0, 4, MAX_RETRIES, 1, help="Each retry searches wider")
    st.divider()
    st.markdown("##### Models")
    st.markdown(H(f'<div class="mrow">Agent A<b>{esc(ANSWER_MODEL_A)}</b></div><div class="mrow">Agent B<b>{esc(ANSWER_MODEL_B)}</b></div><div class="mrow">Auditor<b>{esc(AUDITOR_MODEL)}</b></div><div class="mrow">Embeddings<b>{esc(EMBED_MODEL)}</b></div>'), unsafe_allow_html=True)
    if ANSWER_MODEL_A == ANSWER_MODEL_B:
        st.warning("Agent A and B use the same model. Set ANSWER_MODEL_B to a different one.")

mode = '<span class="dot m"></span><b>Mock mode</b>' if MOCK_LLM else '<span class="dot"></span><b>Live</b> OpenAI'
st.markdown(H(f'<div class="hero"><div><h1>TrustLayer</h1><p>Every AI answer is checked claim by claim against your policy documents before a customer sees it.</p></div><div class="pills"><span class="pill">{mode}</span><span class="pill"><b>{chunks}</b> policy chunks indexed</span></div></div>'), unsafe_allow_html=True)

tab_run, tab_audit, tab_eval = st.tabs(["Verify a question", "Audit log", "Benchmark"])

SAMPLES = [
    ("Savings balance and fee", "What is the Monthly Average Balance (MAB) for a Nova Classic Savings Account and what is the fee for non-maintenance?"),
    ("Credit card annual fee", "What is the annual fee for the Nova Titanium Credit Card, and under what condition is it waived?"),
    ("Loan foreclosure", "Can I foreclose my Nova Express Personal Loan after 8 months, and what is the penalty?"),
    ("Cataract waiting period", "What is the waiting period for cataract surgery under Nova Shield Health Suraksha, and what is the sub-limit?"),
    ("UPI daily limits", "What is the standard daily UPI transaction limit for P2P and what is the limit for hospital payments?"),
    ("Trap: free lounge access", "Can I open a Zero Balance Nova Savings Account with unlimited free international lounge visits and 0 penalty?"),
    ("Trap: crypto desk", "I want to convert my Bitcoin into INR using Nova Bank's crypto desk with 0% tax."),
    ("Trap: tyre cover", "Nova Shield Motor Policy provides 100% replacement cover on tyres and rubber parts without zero depreciation add-on, right?"),
]
def set_q(t): st.session_state["q"] = t

def pipeline(res=None):
    if res is None:
        cls = ["", "", "", "", ""]; last = "Decide"; sub = ["Split question", "Search policies", "Two drafts", "Check claims", "Release or escalate"]
    else:
        ok = res.status == "VERIFIED"
        cls = ["done", "done warn" if res.retry_count else "done", "done", "done", "done ok" if ok else "done bad"]
        last = "Released" if ok else "Escalated"
        sub = ["Split question", f"{res.retry_count} retr{'y' if res.retry_count == 1 else 'ies'}" if res.retry_count else "Searched once", "A and B drafted", f"{len(res.claims)} claims checked", "Safe to send" if ok else "Human review"]
    names = ["Plan", "Retrieve", "Draft", "Audit", last]
    return H('<div class="steps">' + '<span class="arrow">›</span>'.join(f'<div class="step {c}"><span>{n}</span><small>{s}</small></div>' for n, c, s in zip(names, cls, sub)) + '</div>')

with tab_run:
    st.markdown("##### Try a question")
    for row in (SAMPLES[:4], SAMPLES[4:]):
        cols = st.columns(4)
        for i, (lab, full) in enumerate(row):
            cols[i].button(lab, key=f"s_{lab}", on_click=set_q, args=(full,), use_container_width=True)
    q = st.text_area("Your question", key="q", placeholder="e.g. What is the fee for bouncing an EMI on a personal loan?", height=90, label_visibility="collapsed")
    if st.button("Verify answer", type="primary") and q.strip():
        with st.spinner("Agents are drafting, then the auditor checks every claim…"):
            st.session_state["res"] = run_trustlayer(question=q.strip(), support_threshold=support_thresh, min_sim=min_sim_thresh, max_retries=max_retries_val)
    res = st.session_state.get("res")
    st.markdown(pipeline(res), unsafe_allow_html=True)

    if res is None:
        st.info("Pick a sample or type a question. Trap questions contain false premises, so you can watch the system refuse to go along with them.")
    else:
        ok = res.status == "VERIFIED"
        score = max(res.support_score_a, res.support_score_b)
        col = "#3DDC97" if ok else "#FF6B7A"
        circ = 263.9
        reason = (res.handoff_package.reason_code if res.handoff_package else "LOW_SUPPORT").replace("_", " ").lower()
        title = "Verified, safe to release" if ok else "Escalated, needs a human"
        sub = "Every claim in the answer is backed by a policy document." if ok else f"Reason: {reason}. The system will not send an unverified answer."
        st.markdown(H(f'''<div class="verdict {'ok' if ok else 'bad'}"><div class="ring"><svg width="112" height="112"><circle cx="56" cy="56" r="42" fill="none" stroke="#0B1020" stroke-width="10"/><circle cx="56" cy="56" r="42" fill="none" stroke="{col}" stroke-width="10" stroke-linecap="round" stroke-dasharray="{circ*score:.1f} {circ}"/></svg><div>{score*100:.0f}%<small>supported</small></div></div>
        <div><h2>{title}</h2><div class="sub">{esc(sub)}</div><div class="stats"><div>Agent A<b>{res.support_score_a*100:.0f}%</b></div><div>Agent B<b>{res.support_score_b*100:.0f}%</b></div><div>Agreement<b>{res.agreement.replace("_"," ").title()}</b></div><div>Retries<b>{res.retry_count}</b></div><div>Time<b>{res.latency_ms/1000:.1f}s</b></div></div></div></div>'''), unsafe_allow_html=True)

        if ok:
            st.markdown(f'<div class="card"><h4>Answer for the customer</h4><div class="body">{cites(res.final_answer)}</div></div>', unsafe_allow_html=True)
        else:
            hp = res.handoff_package
            conf = "".join(f"<li>{esc(c)}</li>" for c in (hp.conflicts if hp else []))
            st.markdown(H(f'<div class="card"><h4>Handoff for the human reviewer</h4><div class="body">{esc(hp.message if hp else "")}</div>{"<ul>"+conf+"</ul>" if conf else ""}</div>'), unsafe_allow_html=True)

        st.markdown("##### Independent drafts")
        ca, cb = st.columns(2)
        for c, nm, ans, sc in ((ca, "Agent A · direct", res.answer_a, res.support_score_a), (cb, "Agent B · step by step", res.answer_b, res.support_score_b)):
            c.markdown(H(f'<div class="card"><h4>{nm}</h4><div class="body">{cites(ans) if ans else "No draft returned."}</div><div class="bar"><i style="width:{sc*100:.0f}%"></i></div><small style="color:var(--mu)">{sc*100:.0f}% of claims supported</small></div>'), unsafe_allow_html=True)

        st.markdown("##### What the auditor found")
        n = {k: sum(1 for c in res.claims if c.verdict == k) for k in ("SUPPORTED", "UNSUPPORTED", "CONTRADICTED")}
        tot = max(len(res.claims), 1)
        st.markdown(H(f'<div class="split"><i style="width:{n["SUPPORTED"]/tot*100}%;background:var(--ok)"></i><i style="width:{n["UNSUPPORTED"]/tot*100}%;background:var(--wn)"></i><i style="width:{n["CONTRADICTED"]/tot*100}%;background:var(--bd)"></i></div>'), unsafe_allow_html=True)
        st.caption(f"{n['SUPPORTED']} supported · {n['UNSUPPORTED']} unsupported · {n['CONTRADICTED']} contradicted")
        view = st.radio("Show", ["All", "Flagged only"], horizontal=True, label_visibility="collapsed")
        for c in res.claims:
            if view != "All" and c.verdict == "SUPPORTED": continue
            k = {"SUPPORTED": "s", "UNSUPPORTED": "u", "CONTRADICTED": "c"}[c.verdict]
            q_ = f'“{esc(c.quote)}” · {esc(c.evidence_id)}' if c.quote else esc(c.reasoning)
            st.markdown(H(f'<div class="claim {k}"><div class="t"><span class="tag">{c.verdict.title()}</span>{esc(c.claim)}</div><div class="q">{q_}</div></div>'), unsafe_allow_html=True)
        with st.expander("Source passages retrieved"):
            for ch in res.evidence_chunks:
                st.markdown(f'**{ch.id}** · `{ch.source}` › {ch.section} · match {ch.score:.2f}')
                st.caption(ch.content)

with tab_audit:
    runs = get_runs(limit=200)
    if not runs:
        st.info("No runs yet. Verify a question and it will be logged here.")
    else:
        df = pd.DataFrame(runs)
        v = (df.status == "VERIFIED").mean()
        k = st.columns(4)
        for c, (a, b, d) in zip(k, [("Runs logged", len(df), "in the audit database"), ("Verified", f"{v*100:.0f}%", "released with citations"), ("Escalated", f"{(1-v)*100:.0f}%", "sent to a human"), ("Average time", f"{df.latency_ms.mean()/1000:.1f}s", "per question")]):
            c.markdown(kpi(a, b, d), unsafe_allow_html=True)
        st.write("")
        f = st.radio("Filter", ["All", "VERIFIED", "ESCALATED"], horizontal=True, label_visibility="collapsed")
        d2 = df if f == "All" else df[df.status == f]
        cols = [c for c in ["created_at", "question", "status", "agreement", "support_score_a", "support_score_b", "retry_count", "latency_ms", "run_id"] if c in d2.columns]
        st.dataframe(d2[cols], use_container_width=True, hide_index=True)
        rid = st.selectbox("Inspect a run", d2.run_id.tolist()) if len(d2) else None
        det = get_run_details(rid) if rid else None
        if det:
            l, r = st.columns(2)
            l.markdown("##### Timeline")
            for ev in det.get("events", []):
                l.markdown(H(f'<div class="ev"><b>{esc(ev["node"]).title()}</b>{esc(ev["message"])[:240]}<small>{esc(ev["timestamp"])}</small></div>'), unsafe_allow_html=True)
            r.markdown("##### Claims checked")
            for cl in det.get("claims", []):
                kk = {"SUPPORTED": "s", "UNSUPPORTED": "u", "CONTRADICTED": "c"}.get(cl["verdict"], "u")
                r.markdown(H(f'<div class="claim {kk}"><div class="t"><span class="tag">{cl["verdict"].title()}</span>{esc(cl["claim_text"])}</div></div>'), unsafe_allow_html=True)

with tab_eval:
    rp = ROOT / "eval" / "results.json"
    if not rp.exists():
        st.info("Run `python eval/run_eval.py` to generate the benchmark.")
    else:
        data = json.loads(rp.read_text(encoding="utf-8")); S = data["summary"]; R = data["results"]
        st.markdown(f"Baseline single-agent RAG vs TrustLayer on **{S['total_questions']} questions**: {S['answerable_count']} answerable and {S['trick_count']} with false premises or missing topics.")
        k = st.columns(5)
        for c, (a, b, d) in zip(k, [("Hallucination rate", f"{S['trustlayer_hallucination_rate']*100:.1f}%", f"baseline {S['baseline_hallucination_rate']*100:.1f}%"), ("Trap questions handled", f"{S['trustlayer_trick_caught_rate']*100:.0f}%", f"baseline {S['baseline_trick_caught_rate']*100:.0f}%"), ("Unsupported claims released", S["unsupported_claims_released"], "in this run"), ("Sent to a human", f"{S['escalation_rate']*100:.0f}%", "of all questions"), ("Cost of checking", f"{S['trustlayer_avg_llm_calls']:.1f} calls", f"{S['trustlayer_avg_latency_ms']/1000:.1f}s vs {S['baseline_avg_latency_ms']/1000:.1f}s")]):
            c.markdown(kpi(a, b, d), unsafe_allow_html=True)
        if "answerable_correct_trustlayer" in S:
            k2 = st.columns(4)
            for c, (x, y, z) in zip(k2, [("Answerable, answered correctly", f"{S['answerable_correct_trustlayer']*100:.0f}%", f"naive {S['answerable_correct_baseline']*100:.0f}% · strict {S['answerable_correct_strict']*100:.0f}%"), ("Answerable, sent to a human", f"{S['answerable_wrongly_escalated']*100:.0f}%", "the cost of caution"), ("Strict-prompt baseline hallucinations", f"{S['strict_hallucination_rate']*100:.1f}%", "told to abstain"), ("Strict baseline, traps handled", f"{S['strict_trick_caught_rate']*100:.0f}%", "fair comparison")]):
                c.markdown(kpi(x, y, z), unsafe_allow_html=True)
            st.markdown("##### Hallucinated answers by question category")
            st.dataframe(pd.DataFrame(S["by_category"]).T.rename(columns={"n": "Questions", "baseline": "Naive", "strict": "Strict prompt", "trustlayer": "TrustLayer"}), use_container_width=True)
        st.write("")
        g1, g2 = st.columns(2)
        f1 = go.Figure([go.Bar(name="Baseline RAG", x=["Hallucination rate", "Trap questions handled"], y=[S["baseline_hallucination_rate"]*100, S["baseline_trick_caught_rate"]*100], marker_color="#5B6794"),
                        go.Bar(name="TrustLayer", x=["Hallucination rate", "Trap questions handled"], y=[S["trustlayer_hallucination_rate"]*100, S["trustlayer_trick_caught_rate"]*100], marker_color="#7C8CFF")])
        f1.update_layout(barmode="group", title="Quality (%)"); g1.plotly_chart(chart_style(f1), use_container_width=True)
        f2 = go.Figure([go.Bar(name="Baseline RAG", x=["Seconds per answer", "LLM calls"], y=[S["baseline_avg_latency_ms"]/1000, S["baseline_avg_llm_calls"]], marker_color="#5B6794"),
                        go.Bar(name="TrustLayer", x=["Seconds per answer", "LLM calls"], y=[S["trustlayer_avg_latency_ms"]/1000, S["trustlayer_avg_llm_calls"]], marker_color="#FFB454")])
        f2.update_layout(barmode="group", title="Price of verification"); g2.plotly_chart(chart_style(f2), use_container_width=True)
        st.caption("TrustLayer trades extra time and API calls for answers you can audit. Numbers are as measured in the last evaluation run.")
        rows = [{"#": r["id"], "Type": r["type"], "Question": r["question"], "Baseline": r["baseline"]["label"], "TrustLayer": r["trustlayer"]["label"], "Outcome": r["trustlayer"]["status"]} for r in R]
        dfe = pd.DataFrame(rows)
        t = st.radio("Questions", ["All", "answerable", "trick"], horizontal=True, label_visibility="collapsed")
        st.dataframe(dfe if t == "All" else dfe[dfe.Type == t], use_container_width=True, hide_index=True)
        pick = st.selectbox("Compare answers for question", [f"{r['id']}. {r['question'][:90]}" for r in R])
        r0 = R[int(pick.split(".")[0]) - 1]
        a, b = st.columns(2)
        a.markdown(H(f'<div class="card"><h4>Baseline · {r0["baseline"]["label"].replace("_"," ").title()}</h4><div class="body">{esc(r0["baseline"]["answer"])}</div></div>'), unsafe_allow_html=True)
        b.markdown(H(f'<div class="card"><h4>TrustLayer · {r0["trustlayer"]["status"].title()}</h4><div class="body">{cites(r0["trustlayer"]["answer"] or r0["trustlayer"].get("handoff_message"))}</div></div>'), unsafe_allow_html=True)
