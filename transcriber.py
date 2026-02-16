import time

from api_client import client
from config import WHISPER_MODEL


def transcribe(audio_path: str) -> str:
    """Send audio file to OpenAI Whisper API and return the raw transcript.

    Retries once on failure after a 1-second delay.
    Raises on persistent failure.
    """
    last_error = None
    for attempt in range(2):
        try:
            with open(audio_path, "rb") as f:
                response = client.audio.transcriptions.create(
                    model=WHISPER_MODEL,
                    file=f,
                )
            return response.text
        except Exception as e:
            last_error = e
            if attempt == 0:
                print(f"  Whisper API error (retrying in 1s): {e}")
                time.sleep(1)

    raise last_error

