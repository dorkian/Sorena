import os

from dotenv import load_dotenv

# Must run before the os.getenv() calls below, at import time -- callers that
# reach this module first (e.g. face.py's on-connect config message) can't
# rely on litellm's own load_dotenv() side effect happening earlier, the way
# router.py (which imports litellm before this module) accidentally does.
load_dotenv()

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
