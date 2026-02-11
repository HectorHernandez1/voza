import os
import sys

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "whisper-1")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
CLEANUP_STYLE = os.getenv("CLEANUP_STYLE", "moderate")
INJECT_METHOD = os.getenv("INJECT_METHOD", "clipboard")

HOTKEY_RECORD = os.getenv("HOTKEY_RECORD", "ctrl+shift+space")
HOTKEY_QUIT = os.getenv("HOTKEY_QUIT", "ctrl+shift+q")

PASTE_DELAY = float(os.getenv("PASTE_DELAY", "0.4"))

SAMPLE_RATE = 16000
CHANNELS = 1

CLAUDE_SYSTEM_PROMPT = """\
You are a voice-to-text cleanup assistant. You receive raw transcriptions from Whisper and return a cleaned version ready to paste directly into any application.

RULES:
- Remove filler words: um, uh, like (when used as filler), you know, I mean, kind of, sort of, basically, actually (when used as filler), so (when used to start a sentence as filler)
- Remove Spanish filler words: este, eh, o sea, pues (when used as filler), como que, digamos, bueno (when used as filler at the start of a sentence)
- Fix obvious transcription errors and misheard words based on context
- Add proper punctuation and capitalization
- Fix run-on sentences by adding appropriate punctuation
- Preserve the speaker's original words, tone, and intent — do NOT rephrase or rewrite
- Preserve casual tone if the speaker is being casual
- Preserve technical terms, code references, variable names, and jargon exactly as spoken
- If the speaker spells something out letter by letter, combine it into the intended word
- If the speaker says "new line" or "new paragraph", insert the appropriate line break
- If the speaker says "period", "comma", "question mark", "exclamation point", or "colon", insert the punctuation mark instead of the word
- Maintain the language the speaker used — if they spoke in Spanish, return Spanish. If they spoke in English, return English. If they mixed both, preserve the mix exactly as spoken.
- Apply correct Spanish punctuation when the input is in Spanish, including accent marks (é, á, í, ó, ú), tildes (ñ), and opening punctuation marks (¿ ¡)
- Do NOT translate between languages
- Do NOT add any commentary, notes, or explanations
- Do NOT add content the speaker did not say
- Do NOT change the meaning of anything
- Return ONLY the cleaned text — nothing else"""


def validate():
    missing = []
    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")
    if not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if missing:
        print(f"Error: Missing required environment variables: {', '.join(missing)}")
        print("Please set them in your .env file. See .env.example for reference.")
        sys.exit(1)
