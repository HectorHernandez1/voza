import time

from api_client import client
from config import CLEANUP_MODEL, CLEANUP_SYSTEM_PROMPT


def enhance(raw_text: str) -> str:
    """Send raw transcript to GPT for cleanup.

    Retries once on failure after a 1-second delay.
    Returns cleaned text, or raises on persistent failure.
    """
    last_error = None
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=CLEANUP_MODEL,
                max_tokens=256,
                messages=[
                    {"role": "system", "content": CLEANUP_SYSTEM_PROMPT},
                    {"role": "user", "content": raw_text},
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            last_error = e
            if attempt == 0:
                print(f"  Cleanup API error (retrying in 1s): {e}")
                time.sleep(1)

    raise last_error

