import io
import shutil
import subprocess
import threading
import wave

import numpy as np
import sounddevice as sd

from config import SAMPLE_RATE, CHANNELS, AUDIO_DEVICE

# Peak amplitude below this = mic is silent/dead. A working built-in mic in a
# quiet room measures peaks of ~17-52 (MacBook Air), a dead/disconnected mic ~0,
# so keep this well under the quiet-room floor.
_SILENCE_THRESHOLD = 10

# Max seconds to wait for PortAudio to tear down a recording stream.
# Pa_StopStream can deadlock inside CoreAudio's HALB_Mutex (often after
# sleep/wake or a device change mid-session); bounding the wait keeps a hang
# from freezing the hotkey listener and green-lighting the mic indefinitely.
_STOP_TIMEOUT = 2.0

# Check once at import time whether ffmpeg is available for OGG compression
_HAS_FFMPEG = shutil.which("ffmpeg") is not None


class Recorder:
    def __init__(self):
        self._frames = []
        self._active = [False]
        self._recording = False
        self._stream = None
        self._lock = threading.Lock()
        self._last_stop_reason = None
        self._last_duration = 0.0
        self.on_hang = None  # optional callback(reason) if stream teardown deadlocks

    @property
    def last_stop_reason(self):
        """Why the last stop() returned None: 'silent', 'short', or None (success)."""
        return self._last_stop_reason

    @property
    def last_duration(self):
        """Seconds of audio captured by the last successful stop()."""
        return self._last_duration

    @property
    def is_recording(self):
        return self._recording

    def start(self):
        with self._lock:
            if self._recording:
                return
            # Bind this recording's frame list and active flag into the stream
            # callback via a closure. A previous stream whose teardown hung can
            # keep firing its callback; it holds references to its own (dead)
            # list and flag, so it can never write into a newer recording.
            frames = []
            active = [True]

            def _callback(indata, nframes, time_info, status):
                if active[0]:
                    frames.append(indata.copy())

            self._frames = frames
            self._active = active
            self._recording = True
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                device=AUDIO_DEVICE,
                callback=_callback,
            )
            self._stream.start()

    def _safe_teardown(self, stream):
        """Stop+close a PortAudio stream, swallowing errors (best-effort)."""
        try:
            stream.stop()
        except Exception:
            pass
        try:
            stream.close()
        except Exception:
            pass

    def _watch_teardown(self, teardown):
        """If teardown hasn't finished within _STOP_TIMEOUT, treat it as a hang."""
        teardown.join(timeout=_STOP_TIMEOUT)
        if teardown.is_alive():
            reason = ("Audio device deadlocked (CoreAudio hang) — the mic is "
                      "stuck open until the process exits.")
            if self.on_hang is not None:
                self.on_hang(reason)
            else:
                print("Warning: " + reason + " Quit and restart Voza.")

    def stop(self):
        """Stop recording and return an in-memory audio buffer, or None if too short."""
        with self._lock:
            if not self._recording:
                return None
            self._recording = False
            self._active[0] = False  # stop the callback appending to `frames`
            stream = self._stream
            self._stream = None
            frames = self._frames
            self._frames = []

        # Tear down the input stream off the hotkey-listener thread so the
        # pipeline stays snappy. A watchdog verifies teardown actually finished:
        # Pa_StopStream can deadlock inside CoreAudio's HALB_Mutex (often after
        # sleep/wake), pinning the mic open until the process exits. If that
        # happens the watchdog calls on_hang (e.g. to auto-restart the app).
        if stream is not None:
            teardown = threading.Thread(
                target=self._safe_teardown, args=(stream,), daemon=True
            )
            teardown.start()
            threading.Thread(
                target=self._watch_teardown, args=(teardown,), daemon=True
            ).start()

        if not frames:
            self._last_stop_reason = "short"
            return None

        audio = np.concatenate(frames, axis=0)

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
        self._last_duration = len(audio) / SAMPLE_RATE
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
