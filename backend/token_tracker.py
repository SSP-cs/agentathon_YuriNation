import time
from backend.config import settings

def estimate_tokens(text: str) -> int:
    """Accurately estimate token count without heavy dependencies."""
    if not text:
        return 0
    # Average ~4 characters per token for English text
    words = len(text.split())
    chars = len(text)
    return max(1, int(chars / 4.0))

def calculate_cost(input_tokens: int, output_tokens: int, provider: str = "openai") -> float:
    """Calculate estimated cost in USD based on model provider rates."""
    # Standard cost per million tokens
    cost_in = (input_tokens / 1_000_000.0) * settings.COST_PER_M_INPUT
    cost_out = (output_tokens / 1_000_000.0) * settings.COST_PER_M_OUTPUT
    return round(cost_in + cost_out, 6)

class TokenTracker:
    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_calls = 0
        self.total_cost = 0.0

    def record_call(self, prompt: str, completion: str, latency_ms: float = 0.0, provider: str = "openai") -> dict:
        in_tokens = estimate_tokens(prompt)
        out_tokens = estimate_tokens(completion)
        cost = calculate_cost(in_tokens, out_tokens, provider)
        
        self.total_input_tokens += in_tokens
        self.total_output_tokens += out_tokens
        self.total_calls += 1
        self.total_cost += cost

        return {
            "prompt_tokens": in_tokens,
            "completion_tokens": out_tokens,
            "total_tokens": in_tokens + out_tokens,
            "cost_usd": cost,
            "latency_ms": latency_ms
        }

token_tracker = TokenTracker()

