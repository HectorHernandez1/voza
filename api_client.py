"""Shared AI clients — initialized once at import time."""

from openai import OpenAI
from config import VOZA_MODE, OPENAI_API_KEY, OLLAMA_BASE_URL

if VOZA_MODE == "local":
    client = OpenAI(
        base_url=f"{OLLAMA_BASE_URL}/v1",
        api_key="ollama",
    )
    # Cloud fallback when local servers are unreachable (requires a real key)
    fallback_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
else:
    client = OpenAI(api_key=OPENAI_API_KEY)
    fallback_client = None
