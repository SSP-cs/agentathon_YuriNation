"""Configuration management for TrustLayer."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()

# Operational Flags
MOCK_LLM = os.getenv("MOCK_LLM", "0").lower() in ("1", "true", "yes")
USE_CACHE = os.getenv("CACHE", "1").lower() in ("1", "true", "yes")

# Storage Paths
CHROMA_PATH = str(ROOT_DIR / "chroma_db")
COLLECTION_NAME = "nova_policies"
SQLITE_DB_PATH = str(ROOT_DIR / "audit.db")
CACHE_DIR = str(ROOT_DIR / ".cache")
POLICIES_DIR = str(ROOT_DIR / "data" / "policies")

# Decision and Retrieval Thresholds
MIN_SIM = float(os.getenv("MIN_SIM", "0.35"))
SUPPORT_THRESHOLD = float(os.getenv("SUPPORT_THRESHOLD", "0.85"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")

# Default Models (will be refined dynamically if possible)
DEFAULT_MODEL_A = os.getenv("ANSWER_MODEL_A", "gpt-4o-mini")
# Agent B can run on a different vendor via any OpenAI-compatible endpoint (e.g. Gemini, Groq, OpenRouter, Ollama)
AGENT_B_BASE_URL = os.getenv("AGENT_B_BASE_URL", "")
AGENT_B_API_KEY = os.getenv("AGENT_B_API_KEY", "")
AGENT_B_EXTERNAL = bool(AGENT_B_BASE_URL and AGENT_B_API_KEY)
DEFAULT_MODEL_B = os.getenv("ANSWER_MODEL_B", "gpt-4.1-mini")
DEFAULT_AUDITOR = os.getenv("AUDITOR_MODEL", "gpt-4o")

def resolve_models():
    """Detect available models via client.models.list() and pick sensible defaults."""
    model_a = DEFAULT_MODEL_A
    model_b = DEFAULT_MODEL_B
    auditor = DEFAULT_AUDITOR

    if MOCK_LLM or not OPENAI_API_KEY or OPENAI_API_KEY.startswith("your_"):
        return model_a, model_b, auditor

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        models_data = client.models.list().data
        available_ids = {m.id for m in models_data}

        # Candidate choices
        # For auditor: prefer gpt-4o, gpt-4-turbo, gpt-4, or fallback to gpt-4o-mini
        if auditor not in available_ids:
            for cand in ["gpt-4o", "gpt-4o-2024-08-06", "gpt-4-turbo", "gpt-4", "gpt-4o-mini"]:
                if cand in available_ids:
                    auditor = cand
                    break

        # For Agent A: cost-efficient chat model
        if model_a not in available_ids:
            for cand in ["gpt-4o-mini", "gpt-3.5-turbo", "gpt-4o"]:
                if cand in available_ids:
                    model_a = cand
                    break

        # For Agent B: another cost-efficient chat model or gpt-4o-mini
        if not AGENT_B_EXTERNAL and (model_b not in available_ids or model_b == model_a):
            for cand in ["gpt-4.1-mini", "gpt-4.1-nano", "gpt-4o", "gpt-4.1", "gpt-3.5-turbo"]:
                if cand in available_ids and cand != model_a:
                    model_b = cand
                    break
            else:
                model_b = model_a

    except Exception as e:
        # Fall back to defaults on error
        pass

    return model_a, model_b, auditor

ANSWER_MODEL_A, ANSWER_MODEL_B, AUDITOR_MODEL = resolve_models()

