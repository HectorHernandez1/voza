import time

from openai import OpenAI

from config import OPENAI_API_KEY, WHISPER_MODEL

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def transcribe(audio_path: str) -> str:
    """Send audio file to OpenAI Whisper API and return the raw transcript.

    Retries once on failure after a 2-second delay.
    Raises on persistent failure.
    """
    last_error = None
    for attempt in range(2):
        try:
            client = _get_client()
            with open(audio_path, "rb") as f:
                response = client.audio.transcriptions.create(
                    model=WHISPER_MODEL,
                    file=f,
                )
            return response.text
        except Exception as e:
            last_error = e
            if attempt == 0:
                print(f"  Whisper API error (retrying in 2s): {e}")
                time.sleep(2)

    raise last_error
