"""LLM calling layer with disk caching, tenacity retries, JSON validation, and deterministic mock mode."""

import os
import json
import sqlite3
import hashlib
import time
from typing import Type, TypeVar, Optional, List, Dict, Any
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import OpenAI, RateLimitError, APIConnectionError, APITimeoutError, InternalServerError

from trustlayer.config import (
    OPENAI_API_KEY,
    MOCK_LLM,
    USE_CACHE,
    CACHE_DIR,
    EMBED_MODEL,
    ANSWER_MODEL_A,
    ANSWER_MODEL_B,
    AUDITOR_MODEL,
    AGENT_B_BASE_URL,
    AGENT_B_API_KEY,
    AGENT_B_EXTERNAL,
)

T = TypeVar("T", bound=BaseModel)

# Ensure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_DB_PATH = os.path.join(CACHE_DIR, "llm_cache.db")

def _init_cache_db():
    """Initialize the SQLite cache database for LLM and embedding calls."""
    with sqlite3.connect(CACHE_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                cache_key TEXT PRIMARY KEY,
                response_text TEXT,
                model TEXT,
                created_at REAL
            )
        """)
        conn.commit()

_init_cache_db()

def _get_cache(key: str) -> Optional[str]:
    if not USE_CACHE:
        return None
    try:
        with sqlite3.connect(CACHE_DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("SELECT response_text FROM cache WHERE cache_key = ?", (key,))
            row = cur.fetchone()
            if row:
                return row[0]
    except Exception:
        pass
    return None

def _set_cache(key: str, value: str, model: str):
    if not USE_CACHE:
        return
    try:
        with sqlite3.connect(CACHE_DB_PATH) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (cache_key, response_text, model, created_at) VALUES (?, ?, ?, ?)",
                (key, value, model, time.time())
            )
            conn.commit()
    except Exception:
        pass

def get_openai_client(provider: str = "default") -> OpenAI:
    """Return an OpenAI client; provider "b" uses the Agent B endpoint if configured."""
    if provider == "b" and AGENT_B_EXTERNAL:
        return OpenAI(api_key=AGENT_B_API_KEY, base_url=AGENT_B_BASE_URL)
    return OpenAI(api_key=OPENAI_API_KEY or "mock-key")

@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1.5, min=2, max=10),
    retry=retry_if_exception_type((RateLimitError, APIConnectionError, APITimeoutError, InternalServerError)),
    reraise=True,
)
def _call_chat_completion_raw(
    client: OpenAI,
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
    response_format: Optional[Dict[str, Any]] = None,
) -> str:
    """Execute chat completion with retry logic."""
    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if response_format:
        kwargs["response_format"] = response_format

    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""

def call_llm(
    messages: List[Dict[str, str]],
    model: str,
    temperature: float = 0.2,
    json_mode: bool = False,
    provider: str = "default",
) -> str:
    """Call LLM with caching and retry, returning string content."""
    prompt_str = json.dumps(messages, sort_keys=True)
    cache_key = hashlib.sha256(f"{model}:{prompt_str}:{temperature}:{json_mode}:{provider}".encode("utf-8")).hexdigest()

    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    if MOCK_LLM:
        mock_response = _generate_mock_completion(messages, model, json_mode)
        _set_cache(cache_key, mock_response, model)
        return mock_response

    client = get_openai_client(provider)
    resp_format = {"type": "json_object"} if json_mode else None
    result = _call_chat_completion_raw(client, model, messages, temperature, resp_format)
    _set_cache(cache_key, result, model)
    return result

def call_llm_structured(
    messages: List[Dict[str, str]],
    model: str,
    schema: Type[T],
    temperature: float = 0.1,
    provider: str = "default",
) -> T:
    """Call LLM enforcing strict Pydantic JSON structure using native parse with fallback and repair retry."""
    prompt_str = json.dumps(messages, sort_keys=True)
    schema_name = schema.__name__
    cache_key = hashlib.sha256(f"{model}:{prompt_str}:{temperature}:{schema_name}:{provider}".encode("utf-8")).hexdigest()

    cached = _get_cache(cache_key)
    if cached is not None:
        try:
            return schema.model_validate_json(cached)
        except Exception:
            pass

    if MOCK_LLM:
        mock_obj = _generate_mock_structured(messages, schema)
        _set_cache(cache_key, mock_obj.model_dump_json(), model)
        return mock_obj

    client = get_openai_client(provider)

    # Attempt 1: Native OpenAI beta parse
    try:
        completion = client.beta.chat.completions.parse(
            model=model,
            messages=messages,
            response_format=schema,
            temperature=temperature
        )
        parsed = completion.choices[0].message.parsed
        if parsed is not None:
            _set_cache(cache_key, parsed.model_dump_json(), model)
            return parsed
    except Exception:
        pass

    # Attempt 2: json_object format with schema instruction
    schema_instructions = f"\nYou MUST output a valid JSON instance strictly matching this schema:\n{json.dumps(schema.model_json_schema())}"
    augmented_messages = list(messages)
    augmented_messages[-1] = {
        "role": augmented_messages[-1]["role"],
        "content": augmented_messages[-1]["content"] + schema_instructions
    }

    raw_text = call_llm(augmented_messages, model, temperature=temperature, json_mode=True, provider=provider)
    try:
        parsed = schema.model_validate_json(raw_text)
        _set_cache(cache_key, parsed.model_dump_json(), model)
        return parsed
    except Exception as first_err:
        # Attempt 3: Repair prompt retry
        repair_messages = [
            {"role": "system", "content": "You are a JSON repair assistant. Fix the JSON so that it represents a valid instance of the required schema, NOT the schema definition itself. Return only the valid JSON instance."},
            {"role": "user", "content": f"Failed raw response:\n{raw_text}\n\nTarget Schema:\n{json.dumps(schema.model_json_schema())}\n\nError:\n{str(first_err)}\n\nPlease output the repaired JSON instance only."}
        ]
        repaired_text = call_llm(repair_messages, model, temperature=0.0, json_mode=True, provider=provider)
        parsed = schema.model_validate_json(repaired_text)
        _set_cache(cache_key, parsed.model_dump_json(), model)
        return parsed

def get_embedding(text: str, model: str = EMBED_MODEL) -> List[float]:
    """Retrieve text embedding with caching and mock support."""
    cache_key = hashlib.sha256(f"embed:{model}:{text}".encode("utf-8")).hexdigest()
    cached = _get_cache(cache_key)
    if cached is not None:
        try:
            return json.loads(cached)
        except Exception:
            pass

    if MOCK_LLM or not OPENAI_API_KEY or OPENAI_API_KEY.startswith("your_"):
        # Deterministic pseudo-embedding of dim 1536
        vec = _generate_mock_embedding(text)
        _set_cache(cache_key, json.dumps(vec), model)
        return vec

    client = get_openai_client()
    resp = client.embeddings.create(input=[text], model=model)
    vec = resp.data[0].embedding
    _set_cache(cache_key, json.dumps(vec), model)
    return vec

# ==================== Deterministic Mock Generators ====================

def _generate_mock_embedding(text: str, dim: int = 1536) -> List[float]:
    """Generate a deterministic normalized vector for mock embeddings."""
    h = hashlib.sha256(text.encode("utf-8")).digest()
    vals = [((h[i % len(h)] / 255.0) - 0.5) for i in range(dim)]
    norm = sum(v * v for v in vals) ** 0.5 or 1.0
    return [v / norm for v in vals]

def _generate_mock_completion(messages: List[Dict[str, str]], model: str, json_mode: bool) -> str:
    """Deterministic mock plain/json response."""
    user_content = " ".join(m.get("content", "") for m in messages if m.get("role") == "user")
    lower = user_content.lower()

    if json_mode:
        return json.dumps({
            "answer": "According to Nova Bank policy [S1], savings accounts require a monthly average balance of INR 10,000 in metro areas.",
            "used_evidence_ids": ["S1"]
        })

    if "savings" in lower:
        return "According to Nova Bank policy [S1], Nova Classic Savings Account requires a Monthly Average Balance (MAB) of INR 10,000 in metro and urban branches. Non-maintenance fees are INR 250 plus GST if the shortfall exceeds 50% [S1]."
    elif "credit card" in lower or "titanium" in lower:
        return "Nova Titanium Credit Card has an annual fee of INR 1,500 plus GST, waived if annual retail spend exceeds INR 1,50,000 [S2]. The APR is 42% per annum [S2]."
    elif "loan" in lower:
        return "Nova Express Personal Loan offers amounts between INR 50,000 and INR 25,00,000 with tenures from 12 to 60 months. Foreclosure is subject to a 6-month lock-in period [S3]."
    elif "upi" in lower:
        return "The standard daily UPI transfer limit is INR 1,00,000 with a cap of 20 outbound transactions per 24 hours [S4]."
    elif "health" in lower or "cataract" in lower:
        return "Under Nova Shield Health Suraksha, cataract surgery has a 24-month waiting period and is capped at INR 35,000 per eye [S5]."
    elif "motor" in lower or "depreciation" in lower:
        return "Under Nova Shield Motor Comprehensive Policy, compulsory deductible is INR 1,000 for engines up to 1500cc and INR 2,000 for larger engines [S6]. Zero depreciation add-on is capped at 2 claims per policy year [S6]."
    else:
        return "Based on the provided policy documents, the requested information cannot be verified directly in the available records."

def _generate_mock_structured(messages: List[Dict[str, str]], schema: Type[T]) -> T:
    """Generate deterministic schema-conforming mock responses."""
    user_content = " ".join(m.get("content", "") for m in messages if m.get("role") == "user")
    lower = user_content.lower()
    schema_name = schema.__name__

    if schema_name == "PlannerOutput":
        # Extract keywords to form sub-queries
        sub_queries = [
            f"{user_content[:60]} terms",
            f"{user_content[:60]} limits and eligibility"
        ]
        return schema(
            sub_queries=sub_queries,
            required_facts=["Applicable policy rule", "Specific fees or limits in INR", "Exclusions or waiting periods"]
        )

    elif schema_name == "AuditorOutput":
        # Check if question is a known trick/unsupported topic
        is_unsupported = any(k in lower for k in [
            "cryptocurrency", "bitcoin", "home loan", "term life", "gold loan",
            "fixed deposit interest rate for 10 years", "foreign exchange card free atm in usa"
        ])
        is_contradicted = any(k in lower for k in [
            "zero balance account with no penalty", "cataract surgery is covered on day 1",
            "foreclosure has no lock-in period at nova bank", "upi limit is 10 lakh for normal p2p"
        ])

        if is_unsupported:
            claims_a = [
                {
                    "claim": "Nova Bank provides specific services for this query.",
                    "verdict": "UNSUPPORTED",
                    "evidence_id": None,
                    "quote": None,
                    "reasoning": "No mention of this product or service in retrieved policy evidence."
                }
            ]
            claims_b = [
                {
                    "claim": "The queried product is governed under special guidelines.",
                    "verdict": "UNSUPPORTED",
                    "evidence_id": None,
                    "quote": None,
                    "reasoning": "Document corpus does not cover this facility."
                }
            ]
            return schema(
                claims_a=claims_a,
                claims_b=claims_b,
                support_score_a=0.0,
                support_score_b=0.0,
                agreement="AGREE",
                conflicting_facts=[],
                reasoning="Both drafts refer to topics absent from the source documents."
            )

        elif is_contradicted:
            claims_a = [
                {
                    "claim": "The user premise is supported by the policy.",
                    "verdict": "CONTRADICTED",
                    "evidence_id": "S1",
                    "quote": "Mandatory 6-month lock-in period applies.",
                    "reasoning": "Policy explicitly contradicts the claimed zero waiting period or unlimited threshold."
                }
            ]
            claims_b = [
                {
                    "claim": "The claimed threshold is accurate.",
                    "verdict": "CONTRADICTED",
                    "evidence_id": "S1",
                    "quote": "Ceiling is strictly capped.",
                    "reasoning": "Source text states contrary requirements."
                }
            ]
            return schema(
                claims_a=claims_a,
                claims_b=claims_b,
                support_score_a=0.0,
                support_score_b=0.0,
                agreement="AGREE",
                conflicting_facts=["Contradicts policy waiting periods/limits"],
                reasoning="Claims directly contradict verified policy clauses."
            )
        else:
            # Normal supported case
            claims_a = [
                {
                    "claim": "Nova policy defines specific limits and fees for the service.",
                    "verdict": "SUPPORTED",
                    "evidence_id": "S1",
                    "quote": "Requires a Monthly Average Balance (MAB) of INR 10,000 in metro and urban branches.",
                    "reasoning": "Direct verbatim match in policy documentation."
                },
                {
                    "claim": "Non-maintenance or applicable charges are specified in INR.",
                    "verdict": "SUPPORTED",
                    "evidence_id": "S1",
                    "quote": "If the shortfall exceeds 50% of the required balance, the monthly penalty is INR 250 plus 18% GST.",
                    "reasoning": "Explicitly confirmed by chunk S1."
                }
            ]
            claims_b = [
                {
                    "claim": "Nova policy mandates required balances and documented fee scales.",
                    "verdict": "SUPPORTED",
                    "evidence_id": "S1",
                    "quote": "Requires a Monthly Average Balance (MAB) of INR 10,000 in metro and urban branches.",
                    "reasoning": "Directly substantiated by source."
                }
            ]
            return schema(
                claims_a=claims_a,
                claims_b=claims_b,
                support_score_a=1.0,
                support_score_b=1.0,
                agreement="AGREE",
                conflicting_facts=[],
                reasoning="Both agent drafts are completely supported by the retrieved policy evidence."
            )

    elif schema_name == "AnswerOutput":
        return schema(answer=_generate_mock_completion(messages, "mock", False), used_evidence_ids=["S1"])

    # Fallback default
    return schema()

