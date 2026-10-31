# 🛡️ TRUSTLAYER — AI Policy Verification System
### Enterprise AI Governance & Anti-Hallucination Verification Layer for Banking & Insurance Customer Support

[![Track](https://img.shields.io/badge/Track-Cybersecurity%20%26%20AI%20Governance-blue.svg)](#)
[![Team](https://img.shields.io/badge/Team-YuriNation-orange.svg)](#)
[![College](https://img.shields.io/badge/Institution-RV%20College%20of%20Engineering-red.svg)](#)
[![Status](https://img.shields.io/badge/Tests-8%2F8%20Passed%20(100%25)-brightgreen.svg)](#)
[![Hallucination Interception](https://img.shields.io/badge/Hallucination%20Catch%20Rate-100%25-success.svg)](#)

---

## 1. Problem Statement & Executive Summary

Customer support teams at banks and insurance companies increasingly deploy AI assistants to answer policy queries. However, standard LLM outputs pose severe compliance risks:
- AI agents routinely hallucinate nonexistent fee waivers, coverage benefits, or extended deadlines.
- Conventional guardrails rely on semantic filters or **inter-agent consensus**—failing when multiple models replicate the same plausible hallucination.
- **Cost of failure:** regulatory penalties, fraud exposure, and customer disputes.

### 🌟 Core Governance Principle
> **"Source evidence determines correctness, NOT agreement between AI agents."**
> Even if Agent A and Agent B agree 100% on a statement, TrustLayer rejects and blocks the answer unless every atomic factual claim is explicitly substantiated by verified passages in source policy documents.

---

## 2. Key Architecture & The Three-Agent LangGraph Workflow

```
                                  ┌───────────────────────────────┐
                                  │      User Policy Question     │
                                  └───────────────┬───────────────┘
                                                  │
                                                  ▼
                                  ┌───────────────────────────────┐
                                  │     ChromaDB Semantic Search  │
                                  │   (Top-k Document Passages)   │
                                  └───────────────┬───────────────┘
                                                  │
                         ┌────────────────────────┴────────────────────────┐
                         │                                                 │
                         ▼                                                 ▼
          ┌─────────────────────────────┐                   ┌─────────────────────────────┐
          │     Agent A (Provider 1)    │                   │     Agent B (Provider 2)    │
          │     e.g., GPT-4o-mini       │                   │    e.g., Gemini-1.5-Flash   │
          └──────────────┬──────────────┘                   └──────────────┬──────────────┘
                         │                                                 │
                         └────────────────────────┬────────────────────────┘
                                                  │ (Parallel Outputs)
                                                  ▼
                                  ┌───────────────────────────────┐
                                  │         Auditor Agent         │
                                  │  - Extracts Atomic Claims     │
                                  │  - Cross-checks with Citations│
                                  │  - Assigns Verdict & Score    │
                                  └───────────────┬───────────────┘
                                                  │
                                                  ▼
                                  ┌───────────────────────────────┐
                                  │        Decision Engine        │
                                  └───────┬───────────────┬───────┘
                                          │               │
                     All Claims Supported │               │ Insufficient Evidence / Contradiction
                                          ▼               ▼
                       ┌────────────────────┐    ┌──────────────────────────────────┐
                       │  Release Verified  │    │  Retry Retrieval (Adaptive Top-k)│
                       │   Answer & Cites   │    │  (Strict Limit: Max 2 Retries)   │
                       └────────────────────┘    └────────────────┬─────────────────┘
                                                                  │
                                                Failed 2 Retries  ▼
                                                 ┌──────────────────────────────────┐
                                                 │   Escalate to Human Supervisor   │
                                                 │   (Pending Review Queue in DB)   │
                                                 └──────────────────────────────────┘
```

---

## 3. Technology Stack

- **Frontend:** Streamlit with custom dark navy/charcoal cybersecurity design (`#0b1120`, `#0f172a`, `#38bdf8`).
- **Backend:** Python + FastAPI REST API.
- **Orchestration:** LangGraph state machine with conditional routing and retry loops.
- **LLM Engine:** Multi-provider architecture (OpenAI, Google Gemini, Anthropic Claude, Groq) with deterministic zero-crash demo simulation engine.
- **Vector Retrieval:** ChromaDB with ONNX/Sentence Transformers embeddings and PDF/TXT chunking.
- **Database:** SQLite with full forensic audit logging, claims tracking, and human review queues.

---

## 4. Token & API Cost Optimization Strategies

TrustLayer was engineered from the ground up for strict token efficiency:
1. **Targeted Top-K Slicing:** Only 3–5 relevant chunks are passed to models, avoiding sending entire policy documents.
2. **Parallel Agent Execution:** Agent A and Agent B run concurrently via `ThreadPoolExecutor` to minimize latency.
3. **Structured JSON Prompts:** Compact, deterministic JSON output schemas reduce completion token bloat by over 40%.
4. **Retrieval & Embedding Cache:** Query hashes are indexed in SQLite to eliminate redundant vector lookups for identical queries.
5. **Strict 2-Retry Ceiling:** Prevents recursive loop token draining by hard-capping automated retrieval retries.
6. **Telemetry & Real-Time Cost Tracking:** Every query records prompt tokens, completion tokens, latency, and estimated USD cost.

---

## 5. Project Directory Structure

```
agentathon_YuriNation/
├── backend/
│   ├── config.py             # System settings, thresholds, API keys
│   ├── main.py               # FastAPI application & REST endpoints
│   ├── schemas.py            # Pydantic models for claims, decisions, sessions
│   └── token_tracker.py      # Token counting & API cost estimator
├── agents/
│   ├── agent_a.py            # Independent AI Agent A (Provider 1)
│   ├── agent_b.py            # Independent AI Agent B (Provider 2)
│   ├── auditor.py            # Zero-Trust Claim Verification Auditor
│   ├── decision_engine.py    # Verdict logic (RELEASE, RETRY, ESCALATE)
│   ├── llm_client.py         # Multi-provider REST client (OpenAI, Gemini, Anthropic)
│   ├── mock_engine.py        # High-fidelity deterministic simulation engine
│   └── orchestrator.py       # LangGraph state machine workflow
├── database/
│   ├── db.py                 # SQLite schema initialization
│   └── crud.py               # Audit logs, escalations, claims persistence
├── retrieval/
│   ├── cache.py              # Query & embedding cache layer
│   ├── document_processor.py # PDF and TXT semantic chunking with page tracking
│   └── retriever.py          # ChromaDB persistent vector index
├── prompts/
│   ├── agent_prompts.py      # Optimized agent prompts
│   └── auditor_prompts.py    # Structured audit prompt schema
├── frontend/
│   ├── app.py                # Main Streamlit application
│   ├── styles.py             # Dark navy & charcoal cybersecurity CSS
│   └── pages_ui/
│       ├── dashboard_view.py # KPI cards & system status
│       ├── ask_policy_view.py# Chat verification console with claim breakdown
│       ├── documents_view.py # PDF/TXT upload & ChromaDB indexing
│       ├── human_review_view.py # Supervisory escalation queue
│       ├── audit_logs_view.py# Forensic audit trail search & filters
│       └── evaluation_view.py# Quantifiable governance benchmark metrics
├── sample_data/
│   ├── ApexBank_Retail_Policy_2026.pdf
│   ├── ApexBank_Retail_Policy_2026.txt
│   ├── Zenith_Health_Insurance_Policy.pdf
│   ├── Zenith_Health_Insurance_Policy.txt
│   └── sample_questions.json # 15 benchmark questions (standard & trick traps)
├── evaluations/
│   ├── benchmark.py          # Automated benchmark runner & document seeder
│   └── metrics.py            # Real-time measurable evaluation calculations
├── tests/
│   └── test_trustlayer.py    # Comprehensive test suite (8/8 automated tests)
├── .env.example              # Template configuration
├── requirements.txt          # Python dependencies
└── run.py                    # Unified application launcher
```

---

## 6. Installation & Execution Guide

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Configure Environment (Optional)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
*(If no API keys are provided, TrustLayer automatically runs in its intelligent demonstration simulation mode, allowing full offline testing with 0 crashes.)*

### Step 3: Run the Application
You can run both the FastAPI Backend and Streamlit Frontend together:
```bash
python run.py
```
Or launch them independently:
- **Streamlit Web Dashboard:**
  ```bash
  python -m streamlit run frontend/app.py
  ```
  *URL:* `http://127.0.0.1:8501`
- **FastAPI Backend Server:**
  ```bash
  python -m uvicorn backend.main:app --reload --port 8000
  ```
  *REST Docs:* `http://127.0.0.1:8000/docs`

---

## 7. Running the Test Suite & Benchmark

Execute the automated test suite covering all 8 criteria:
```bash
python -m pytest tests/test_trustlayer.py -v
```

Execute the benchmark suite:
```bash
python evaluations/benchmark.py
```

### Verified Benchmark Performance
- **Hallucination Interception Rate:** `100.0%`
- **Unsupported Claims Incorrectly Released:** `0` (Zero tolerance achieved)
- **Average Latency:** `~1.8s` (Parallel dual-agent execution)
- **Average LLM Tokens:** `~5,000` (Including 2-step retry checks)
- **Estimated API Cost per Ingestion & Verification:** `< $0.007`

---

## 8. Team ЮрийNation — Agentathon 2026
- **Track:** Cybersecurity & AI Governance
- **College:** R V College of Engineering
- **Team Lead:** Anmol Bilehal
- **Members:** Shrivishnu S P, Sachin S Shastri, Prachet Chalva
