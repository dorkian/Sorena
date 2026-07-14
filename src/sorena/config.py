import os

_DEFAULT_CHAIN = "groq/llama-3.3-70b-versatile,gemini/gemini-3.1-flash-lite"
_DEFAULT_LIMITS = "groq/llama-3.3-70b-versatile:30,gemini/gemini-3.1-flash-lite:15"


def _parse_chain(raw: str) -> list[str]:
    return [m.strip() for m in raw.split(",") if m.strip()]


def _parse_limits(raw: str) -> dict[str, int]:
    limits = {}
    for pair in raw.split(","):
        model, rpm = pair.split(":")
        limits[model.strip()] = int(rpm)
    return limits


PROVIDER_CHAIN = _parse_chain(os.getenv("SORENA_PROVIDER_CHAIN", _DEFAULT_CHAIN))
RATE_LIMITS_RPM = _parse_limits(os.getenv("SORENA_RATE_LIMITS_RPM", _DEFAULT_LIMITS))
