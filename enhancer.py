import time

from api_client import client
from config import VOZA_MODE, CLEANUP_MODEL, LOCAL_CLEANUP_MODEL, CLEANUP_SYSTEM_PROMPT

_MODEL = LOCAL_CLEANUP_MODEL if VOZA_MODE == "local" else CLEANUP_MODEL


def enhance(raw_text: str) -> str:
    """Send raw transcript to LLM for cleanup.

    Retries once on failure after a 1-second delay.
    Returns cleaned text, or raises on persistent failure.
    """
    last_error = None
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=_MODEL,
                max_completion_tokens=256,
                temperature=0,
                messages=[
                    {"role": "system", "content": CLEANUP_SYSTEM_PROMPT},
                    {"role": "user", "content": f"[TRANSCRIPTION]\n{raw_text}\n[/TRANSCRIPTION]"},
                ],
            )
            result = response.choices[0].message.content
            if result and result.strip():
                return result
            # Model returned empty content — fall back to raw text
            return raw_text
        except Exception as e:
            last_error = e
            if attempt == 0:
                print(f"  Cleanup API error (retrying in 1s): {e}")
                time.sleep(1)

    raise last_error


def enhance_stream(raw_text: str):
    """Stream cleaned text from the LLM as it is generated.

    Yields text chunks as they arrive. Retries once (after a 1-second delay)
    only if the failure happens before any text has been yielded — once text
    is out, a mid-stream error propagates so the caller can handle the
    partial output.
    """
    last_error = None
    for attempt in range(2):
        started = False
        try:
            stream = client.chat.completions.create(
                model=_MODEL,
                max_completion_tokens=256,
                temperature=0,
                stream=True,
                messages=[
                    {"role": "system", "content": CLEANUP_SYSTEM_PROMPT},
                    {"role": "user", "content": f"[TRANSCRIPTION]\n{raw_text}\n[/TRANSCRIPTION]"},
                ],
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    started = True
                    yield delta
            return
        except Exception as e:
            if started:
                raise
            last_error = e
            if attempt == 0:
                print(f"  Cleanup API error (retrying in 1s): {e}")
                time.sleep(1)

    raise last_error
