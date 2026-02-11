import time

import anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, CLAUDE_SYSTEM_PROMPT

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def enhance(raw_text: str) -> str:
    """Send raw transcript to Claude for cleanup.

    Retries once on failure after a 2-second delay.
    Returns cleaned text, or raises on persistent failure.
    """
    last_error = None
    for attempt in range(2):
        try:
            client = _get_client()
            message = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4096,
                system=CLAUDE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": raw_text}],
            )
            return message.content[0].text
        except Exception as e:
            last_error = e
            if attempt == 0:
                print(f"  Claude API error (retrying in 2s): {e}")
                time.sleep(2)

    raise last_error
