import os
import json
import time
import re
import httpx
from typing import Dict, Any, Optional, List
from backend.config import settings
from backend.schemas import ClaimItem, ClaimStatus, AuditorResult, AgentResponse
from backend.token_tracker import token_tracker, estimate_tokens

class LLMClient:
    def __init__(self):
        self.http_client = httpx.Client(timeout=30.0)

    def is_provider_available(self, provider: str) -> bool:
        p = provider.lower()
        if p == "openai":
            return bool(settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.strip())
        elif p == "anthropic":
            return bool(settings.ANTHROPIC_API_KEY and settings.ANTHROPIC_API_KEY.strip())
        elif p == "gemini":
            return bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip())
        elif p == "groq":
            return bool(settings.GROQ_API_KEY and settings.GROQ_API_KEY.strip())
        return False

    def generate_chat(self, provider: str, model: str, system_prompt: str, user_prompt: str, json_mode: bool = False) -> Dict[str, Any]:
        """
        Calls live LLM provider if configured with API key, otherwise returns None
        so the fallback simulator handles it.
        """
        p = provider.lower()
        t0 = time.time()
        
        if not self.is_provider_available(p):
            return None

        try:
            if p == "openai" or p == "groq":
                endpoint = "https://api.openai.com/v1/chat/completions" if p == "openai" else "https://api.groq.com/openai/v1/chat/completions"
                api_key = settings.OPENAI_API_KEY if p == "openai" else settings.GROQ_API_KEY
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.1
                }
                if json_mode and p == "openai":
                    payload["response_format"] = {"type": "json_object"}

                resp = self.http_client.post(endpoint, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    usage = data.get("usage", {})
                    p_tok = usage.get("prompt_tokens", estimate_tokens(user_prompt))
                    c_tok = usage.get("completion_tokens", estimate_tokens(content))
                    latency = round((time.time() - t0) * 1000, 2)
                    token_tracker.record_call(user_prompt, content, latency, provider=p)
                    return {
                        "content": content,
                        "prompt_tokens": p_tok,
                        "completion_tokens": c_tok,
                        "latency_ms": latency,
                        "is_mock": False
                    }
            elif p == "anthropic":
                endpoint = "https://api.anthropic.com/v1/messages"
                headers = {
                    "x-api-key": settings.ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                    "max_tokens": 1000,
                    "temperature": 0.1
                }
                resp = self.http_client.post(endpoint, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    content = "".join([b["text"] for b in data.get("content", []) if b.get("type") == "text"])
                    usage = data.get("usage", {})
                    p_tok = usage.get("input_tokens", estimate_tokens(user_prompt))
                    c_tok = usage.get("output_tokens", estimate_tokens(content))
                    latency = round((time.time() - t0) * 1000, 2)
                    token_tracker.record_call(user_prompt, content, latency, provider=p)
                    return {
                        "content": content,
                        "prompt_tokens": p_tok,
                        "completion_tokens": c_tok,
                        "latency_ms": latency,
                        "is_mock": False
                    }
            elif p == "gemini":
                # Google Gemini REST
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={settings.GEMINI_API_KEY}"
                payload = {
                    "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
                    "generationConfig": {"temperature": 0.1}
                }
                resp = self.http_client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        content = "".join([p.get("text", "") for p in parts])
                        p_tok = estimate_tokens(user_prompt)
                        c_tok = estimate_tokens(content)
                        latency = round((time.time() - t0) * 1000, 2)
                        token_tracker.record_call(user_prompt, content, latency, provider=p)
                        return {
                            "content": content,
                            "prompt_tokens": p_tok,
                            "completion_tokens": c_tok,
                            "latency_ms": latency,
                            "is_mock": False
                        }
        except Exception as e:
            print(f"Error calling {provider} API: {e}. Falling back to simulation mode.")
        
        return None

llm_client = LLMClient()

