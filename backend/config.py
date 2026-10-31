import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="allow")

    APP_NAME: str = "TRUSTLAYER"
    APP_ENV: str = "development"
    DEBUG: bool = True
    
    # Storage Paths
    BASE_DIR: str = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    DATA_DIR: str = os.path.join(BASE_DIR, "data")
    DB_PATH: str = os.path.join(DATA_DIR, "trustlayer.db")
    CHROMA_PATH: str = os.path.join(DATA_DIR, "chroma_db")
    DOCS_DIR: str = os.path.join(DATA_DIR, "uploaded_docs")
    
    # LLM API Keys
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY", "")
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY", "")
    
    # Agent Providers and Models
    AGENT_A_PROVIDER: str = os.getenv("AGENT_A_PROVIDER", "openai")
    AGENT_A_MODEL: str = os.getenv("AGENT_A_MODEL", "gpt-4o-mini")
    
    AGENT_B_PROVIDER: str = os.getenv("AGENT_B_PROVIDER", "gemini")
    AGENT_B_MODEL: str = os.getenv("AGENT_B_MODEL", "gemini-1.5-flash")
    
    AUDITOR_PROVIDER: str = os.getenv("AUDITOR_PROVIDER", "openai")
    AUDITOR_MODEL: str = os.getenv("AUDITOR_MODEL", "gpt-4o-mini")
    
    # Retrieval & Workflow Limits
    RETRIEVAL_TOP_K: int = 3
    RETRY_TOP_K_STEP_1: int = 5
    RETRY_TOP_K_STEP_2: int = 8
    MAX_RETRIES: int = 2
    CHUNK_SIZE: int = 400
    CHUNK_OVERLAP: int = 60
    
    # Verification Decision Thresholds
    MIN_SUPPORTED_RATIO: float = 1.0  # All claims must be supported for automatic release
    CONFIDENCE_THRESHOLD: float = 0.80
    
    # API Costs estimate (USD per 1M tokens)
    COST_PER_M_INPUT: float = 0.150   # gpt-4o-mini / gemini-flash tier
    COST_PER_M_OUTPUT: float = 0.600
    
    # Server configuration
    BACKEND_HOST: str = "127.0.0.1"
    BACKEND_PORT: int = 8000
    STREAMLIT_PORT: int = 8501

settings = Settings()
os.makedirs(settings.DATA_DIR, exist_ok=True)
os.makedirs(settings.DOCS_DIR, exist_ok=True)
os.makedirs(settings.CHROMA_PATH, exist_ok=True)
