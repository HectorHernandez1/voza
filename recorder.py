import tempfile
import threading

import numpy as np
import sounddevice as sd

from config import SAMPLE_RATE, CHANNELS

_SILENCE_THRESHOLD = 100  # peak amplitude below this = mic is silent/dead


class Recorder:
    def __init__(self):
        self._frames = []
        self._recording = False
        self._stream = None
        self._lock = threading.Lock()

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
                callback=self._callback,
            )
            self._stream.start()

    def _callback(self, indata, frames, time_info, status):
        if self._recording:
            self._frames.append(indata.copy())

    def stop(self):
        """Stop recording and return path to a temporary WAV file, or None if too short."""
        with self._lock:
            if not self._recording:
                return None
            self._recording = False
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
                self._stream = None

        if not self._frames:
            return None

        audio = np.concatenate(self._frames, axis=0)

        # If less than 0.3 seconds of audio, treat as accidental press
        min_samples = int(SAMPLE_RATE * 0.3)
        if len(audio) < min_samples:
            return None

        return self._save_wav(audio)

    def _save_wav(self, audio: np.ndarray) -> str:
        import wave

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        with wave.open(tmp.name, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)  # 16-bit = 2 bytes
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio.tobytes())
        return tmp.name
