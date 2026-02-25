import io
import shutil
import subprocess
import threading
import wave

import numpy as np
import sounddevice as sd

from config import SAMPLE_RATE, CHANNELS, AUDIO_DEVICE

_SILENCE_THRESHOLD = 100  # peak amplitude below this = mic is silent/dead

# Check once at import time whether ffmpeg is available for OGG compression
_HAS_FFMPEG = shutil.which("ffmpeg") is not None


class Recorder:
    def __init__(self):
        self._frames = []
        self._recording = False
        self._stream = None
        self._lock = threading.Lock()
        self._last_stop_reason = None

    @property
    def last_stop_reason(self):
        """Why the last stop() returned None: 'silent', 'short', or None (success)."""
        return self._last_stop_reason

    @property
    def is_recording(self):
        return self._recording

    def start(self):
        with self._lock:
            if self._recording:
                return
            self._frames = []
            self._recording = True
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                device=AUDIO_DEVICE,
                callback=self._callback,
            )
            self._stream.start()

    def _callback(self, indata, frames, time_info, status):
        if self._recording:
            self._frames.append(indata.copy())

    def stop(self):
        """Stop recording and return an in-memory audio buffer, or None if too short."""
        with self._lock:
            if not self._recording:
                return None
            self._recording = False
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
                self._stream = None

        if not self._frames:
            self._last_stop_reason = "short"
            return None

        audio = np.concatenate(self._frames, axis=0)

        # Check if audio is essentially silent (dead/wrong mic)
        peak = int(np.max(np.abs(audio)))
        if peak < _SILENCE_THRESHOLD:
            self._last_stop_reason = "silent"
            return None

        # If less than 0.3 seconds of audio, treat as accidental press
        min_samples = int(SAMPLE_RATE * 0.3)
        if len(audio) < min_samples:
            self._last_stop_reason = "short"
            return None

        self._last_stop_reason = None
        return self._to_audio_buffer(audio)

    def _to_wav_bytes(self, audio: np.ndarray) -> io.BytesIO:
        """Convert raw audio to an in-memory WAV buffer."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)  # 16-bit = 2 bytes
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio.tobytes())
        buf.seek(0)
        buf.name = "recording.wav"
        return buf

    def _to_ogg_bytes(self, wav_buf: io.BytesIO) -> io.BytesIO:
        """Convert WAV buffer to OGG/Opus via ffmpeg for ~90% smaller upload."""
        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-f", "wav", "-i", "pipe:0",
                    "-c:a", "libopus",
                    "-b:a", "24k",       # 24kbps is plenty for speech
                    "-application", "voip",
                    "-f", "ogg", "pipe:1",
                ],
                input=wav_buf.read(),
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0 and len(result.stdout) > 0:
                ogg_buf = io.BytesIO(result.stdout)
                ogg_buf.name = "recording.ogg"
                return ogg_buf
        except (subprocess.TimeoutExpired, Exception):
            pass

        # Fallback: return the original WAV
        wav_buf.seek(0)
        return wav_buf

    def _to_audio_buffer(self, audio: np.ndarray) -> io.BytesIO:
        """Return the best available in-memory audio buffer (OGG if ffmpeg exists, else WAV)."""
        wav_buf = self._to_wav_bytes(audio)
        if _HAS_FFMPEG:
            return self._to_ogg_bytes(wav_buf)
        return wav_buf
