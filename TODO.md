# Voza — Setup & Testing Checklist

## Setup

- [ ] Create Python virtual environment (`python3 -m venv venv && source venv/bin/activate`)
- [ ] Install dependencies (`pip install -r requirements.txt`)
- [ ] Configure API keys — copy `.env.example` to `.env` and add real OPENAI_API_KEY and ANTHROPIC_API_KEY
- [ ] Grant Accessibility permissions to Terminal app (System Settings > Privacy & Security > Accessibility)

## Testing

- [ ] Run `python main.py` and confirm startup message prints
- [ ] Hotkey works when another app is in focus
- [ ] Audio records correctly from the default mic
- [ ] Whisper transcribes English correctly
- [ ] Whisper transcribes Spanish correctly
- [ ] Claude removes filler words without changing meaning
- [ ] Claude preserves technical terms and code references
- [ ] Claude handles Spanish text with correct accents and punctuation
- [ ] Claude handles mixed English/Spanish without translating
- [ ] Cleaned text is pasted into the focused app via clipboard
- [ ] Error handling works when APIs are unreachable
- [ ] App exits cleanly on Ctrl+Shift+Q
- [ ] Works on macOS with Intel processor
