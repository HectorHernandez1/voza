import time

from api_client import client
from config import WHISPER_MODEL


def transcribe(audio_buffer) -> str:
    """Send audio buffer to OpenAI Whisper API and return the raw transcript.

    Accepts an in-memory file-like object (BytesIO with a .name attribute).
    Retries once on failure after a 1-second delay.
    Raises on persistent failure.
    """
    last_error = None
    for attempt in range(2):
        try:
            audio_buffer.seek(0)
            response = client.audio.transcriptions.create(
                model=WHISPER_MODEL,
                file=audio_buffer,
            )
            return response.text
        except Exception as e:
            last_error = e
            if attempt == 0:
                print(f"  Whisper API error (retrying in 1s): {e}")
                time.sleep(1)

    raise last_error
