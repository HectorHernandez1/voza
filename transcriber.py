import time

from config import VOZA_MODE, WHISPER_MODEL, WHISPER_SERVER_URL

if VOZA_MODE == "openai":
    from api_client import client


def transcribe(audio_buffer) -> str:
    """Transcribe audio and return raw text. Routes to OpenAI or whisper-server."""
    if VOZA_MODE == "local":
        return _transcribe_local(audio_buffer)
    return _transcribe_openai(audio_buffer)


def _transcribe_openai(audio_buffer) -> str:
    """Send audio buffer to OpenAI Whisper API with one retry."""
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


def _transcribe_local(audio_buffer) -> str:
    """Send audio to whisper-server HTTP API."""
    import requests

    audio_buffer.seek(0)
    name = getattr(audio_buffer, "name", "audio.wav")
    mime = "audio/ogg" if name.endswith(".ogg") else "audio/wav"

    last_error = None
    for attempt in range(2):
        try:
            audio_buffer.seek(0)
            resp = requests.post(
                f"{WHISPER_SERVER_URL}/inference",
                files={"file": (name, audio_buffer, mime)},
                data={"response_format": "json"},
                timeout=30,
            )
            resp.raise_for_status()
            text = resp.json()["text"].strip()
            if not text:
                raise RuntimeError("whisper-server returned empty text")
            return text
        except Exception as e:
            last_error = e
            if attempt == 0:
                print(f"  whisper-server error (retrying in 1s): {e}")
                time.sleep(1)

    raise last_error
