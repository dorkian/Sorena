import time

import litellm
from dotenv import load_dotenv

from sorena.config import PROVIDER_CHAIN, RATE_LIMITS_RPM
from sorena.ratelimit import RateLimiter
from sorena.telemetry import log_call

load_dotenv()

_rate_limiter = RateLimiter(RATE_LIMITS_RPM)


def chat(
    messages: list[dict],
    tools: list[dict] | None = None,
    tool_choice: str | None = None,
) -> str:
    for model in PROVIDER_CHAIN:
        if not _rate_limiter.allow(model):
            print(f"[router] {model} locally rate-limited, skipping")
            continue
        try:
            start = time.monotonic()
            response = litellm.completion(
                model=model,
                messages=messages,
                num_retries=2,
                retry_strategy="exponential_backoff_retry",
                **({"tools": tools, "tool_choice": tool_choice} if tools else {}),
            )
            latency_ms = (time.monotonic() - start) * 1000
            _rate_limiter.record(model)

            usage = response.usage
            try:
                cost = litellm.completion_cost(completion_response=response)
            except Exception:
                cost = 0.0

            log_call(
                provider=model.split("/")[0],
                model=model,
                tokens_in=usage.prompt_tokens,
                tokens_out=usage.completion_tokens,
                latency_ms=latency_ms,
                cost=cost,
            )
            message = response.choices[0].message
            if getattr(message, "tool_calls", None):
                return message

            return response.choices[0].message.content
        except Exception as e:
            print(f"[router] {model} failed: {e}")
            continue
    raise RuntimeError("All providers in the chain failed")
