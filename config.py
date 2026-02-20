import os
import sys

import sounddevice as sd

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "whisper-1")
CLEANUP_MODEL = os.getenv("CLEANUP_MODEL", "gpt-5-mini")
CLEANUP_STYLE = os.getenv("CLEANUP_STYLE", "moderate")
INJECT_METHOD = os.getenv("INJECT_METHOD", "clipboard")

HOTKEY_RECORD = os.getenv("HOTKEY_RECORD", "ctrl+shift+space")
HOTKEY_QUIT = os.getenv("HOTKEY_QUIT", "ctrl+shift+q")

PASTE_DELAY = float(os.getenv("PASTE_DELAY", "0.15"))

SAMPLE_RATE = 16000
CHANNELS = 1

# Audio device — set to device name (partial match), index number, or "auto".
# "auto" (default) probes all mics and picks the loudest one.
_AUDIO_DEVICE_RAW = os.getenv("AUDIO_DEVICE", "auto")


def _probe_best_device():
    """Record a short sample on every input device and return the index with the highest peak."""
    import numpy as np

    devs = sd.query_devices()
    best_idx = None
    best_peak = -1
    best_name = ""

    # Skip iOS devices that appear via Continuity — they cause long hangs
    _skip = {"iphone", "ipad"}

    for i, d in enumerate(devs):
        if d['max_input_channels'] < 1:
            continue
        if any(s in d['name'].lower() for s in _skip):
            continue
        try:
            audio = sd.rec(
                int(SAMPLE_RATE * 0.3),
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                device=i,
            )
            sd.wait()
            peak = int(np.max(np.abs(audio)))
            if peak > best_peak:
                best_peak = peak
                best_idx = i
                best_name = d['name']
        except Exception:
            continue  # skip devices that error out

    if best_idx is not None:
        print(f"  Auto-detected mic: [{best_idx}] {best_name} (peak={best_peak})")
    return best_idx


def _resolve_audio_device():
    """Resolve AUDIO_DEVICE env var to a device index, or auto-detect the best mic."""
    raw = _AUDIO_DEVICE_RAW.strip().lower()

    # Auto-detect: probe all devices and pick the loudest
    if not raw or raw == "auto":
        return _probe_best_device()

    # Try as integer index first
    try:
        idx = int(raw)
        dev = sd.query_devices(idx)
        if dev['max_input_channels'] > 0:
            return idx
        print(f"  Warning: Device [{idx}] has no input channels. Falling back to auto-detect.")
        return _probe_best_device()
    except (ValueError, sd.PortAudioError):
        pass

    # Try as name substring match
    devs = sd.query_devices()
    for i, d in enumerate(devs):
        if d['max_input_channels'] > 0 and raw in d['name'].lower():
            return i

    print(f"  Warning: No input device matching '{_AUDIO_DEVICE_RAW.strip()}'. Falling back to auto-detect.")
    return _probe_best_device()


AUDIO_DEVICE = _resolve_audio_device()

CLEANUP_SYSTEM_PROMPT = """\
You are a voice-to-text cleanup assistant. You receive raw transcriptions from Whisper and return a cleaned version ready to paste directly into any application.

RULES:
- Remove filler words: um, uh, like (when used as filler), you know, I mean, kind of, sort of, basically, actually (when used as filler), so (when used to start a sentence as filler)
- Remove Spanish filler words: este, eh, o sea, pues (when used as filler), como que, digamos, bueno (when used as filler at the start of a sentence)
- Fix obvious transcription errors and misheard words based on context
- Add proper punctuation and capitalization
- Fix run-on sentences by adding appropriate punctuation (periods, semicolons, or commas)
- When a speaker chains multiple clauses with "and", break them into separate sentences where appropriate — for example, "I went to the store and I bought milk and then I came home" → "I went to the store. I bought milk, and then I came home."
- Preserve the speaker's original words, tone, and intent — do NOT rephrase or rewrite
- Preserve casual tone if the speaker is being casual
- Preserve technical terms, code references, variable names, and jargon exactly as spoken
- Assume the primary programming language is Python. When the speaker references code, prefer Python conventions (snake_case for variables and functions, PascalCase for classes)
- Recognize common programming and Git terms even if Whisper mistranscribes them — for example: "git pull", "git push", "git fetch", "git commit", "git merge", "git rebase", "pip install", "def", "self", "init", "__init__", "pytest", "venv"
- If the speaker spells something out letter by letter, combine it into the intended word
- If the speaker says "new line" or "new paragraph", insert the appropriate line break
- If the speaker says "period", "comma", "question mark", "exclamation point", or "colon", insert the punctuation mark instead of the word
- If the speaker corrects themselves (e.g., "A, sorry I meant B", "A, wait no, B", "A, actually B", "A, I mean B", "A, no no, B", "A, bueno quise decir B"), discard the incorrect part and keep ONLY the correction. The final output should read as if the speaker said the corrected version from the start.
- Maintain the language the speaker used — if they spoke in Spanish, return Spanish. If they spoke in English, return English. If they mixed both, preserve the mix exactly as spoken.
- Apply correct Spanish punctuation when the input is in Spanish, including accent marks (é, á, í, ó, ú), tildes (ñ), and opening punctuation marks (¿ ¡)
- If I say a sequence of numbers, format them as digits separated by commas (e.g., "one two three four" → "1, 2, 3, 4")
- Do NOT translate between languages
- Do NOT add any commentary, notes, or explanations
- Do NOT add content the speaker did not say
- Do NOT change the meaning of anything
- Return ONLY the cleaned text — nothing else"""


def validate():
    if not OPENAI_API_KEY:
        print("Error: Missing required environment variable: OPENAI_API_KEY")
        print("Please set it in your .env file. See .env.example for reference.")
        sys.exit(1)
