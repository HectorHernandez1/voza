import time

from api_client import client, fallback_client
from config import VOZA_MODE, CLEANUP_MODEL, LOCAL_CLEANUP_MODEL, CLEANUP_SYSTEM_PROMPT

_MODEL = LOCAL_CLEANUP_MODEL if VOZA_MODE == "local" else CLEANUP_MODEL


def _messages(raw_text: str):
    return [
        {"role": "system", "content": CLEANUP_SYSTEM_PROMPT},
        {"role": "user", "content": f"[TRANSCRIPTION]\n{raw_text}\n[/TRANSCRIPTION]"},
    ]


def _max_tokens(raw_text: str) -> int:
    # Cleanup output is the same length as the input or shorter. English/Spanish
    # runs ~4 chars/token, so chars/2 gives ~2x headroom — a fixed cap silently
    # truncated long dictations mid-sentence.
    return max(256, len(raw_text) // 2)


def enhance(raw_text: str) -> str:
    """Send raw transcript to LLM for cleanup.

    Retries once on failure; if the local server stays unreachable, falls
    back to the OpenAI API when a key is configured.
    Returns cleaned text, or raises on persistent failure.
    """
    try:
        return _complete(client, _MODEL, raw_text)
    except Exception as e:
        if fallback_client is None:
            raise
        print(f"  Local cleanup unavailable, falling back to OpenAI: {e}")
        return _complete(fallback_client, CLEANUP_MODEL, raw_text)


def _complete(api, model, raw_text: str) -> str:
    last_error = None
    for attempt in range(2):
        try:
            response = api.chat.completions.create(
                model=model,
                max_completion_tokens=_max_tokens(raw_text),
                temperature=0,
                messages=_messages(raw_text),
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
    partial output. If the local server stays unreachable before any text is
    out, falls back to streaming from the OpenAI API when a key is configured.
    """
    started = False
    try:
        for delta in _stream(client, _MODEL, raw_text):
            started = True
            yield delta
        return
    except Exception as e:
        if started or fallback_client is None:
            raise
        print(f"  Local cleanup unavailable, falling back to OpenAI: {e}")
    yield from _stream(fallback_client, CLEANUP_MODEL, raw_text)


def _stream(api, model, raw_text: str):
    last_error = None
    for attempt in range(2):
        started = False
        try:
            stream = api.chat.completions.create(
                model=model,
                max_completion_tokens=_max_tokens(raw_text),
                temperature=0,
                stream=True,
                messages=_messages(raw_text),
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
