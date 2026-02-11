import time

import openai

from config import OPENAI_API_KEY, CLEANUP_MODEL, CLEANUP_SYSTEM_PROMPT

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = openai.OpenAI(api_key=OPENAI_API_KEY)
    return _client


def enhance(raw_text: str) -> str:
    """Send raw transcript to GPT for cleanup.

    Retries once on failure after a 2-second delay.
    Returns cleaned text, or raises on persistent failure.
    """
    last_error = None
    for attempt in range(2):
        try:
            client = _get_client()
            response = client.chat.completions.create(
                model=CLEANUP_MODEL,
                messages=[
                    {"role": "system", "content": CLEANUP_SYSTEM_PROMPT},
                    {"role": "user", "content": raw_text},
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            last_error = e
            if attempt == 0:
                print(f"  Cleanup API error (retrying in 2s): {e}")
                time.sleep(2)

    raise last_error
