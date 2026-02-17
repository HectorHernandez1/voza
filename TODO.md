# Voza — Setup & Testing Checklist

## Setup

- [x] Create Conda environment (`conda create -n voza python=3.11 -y && conda activate voza`)
- [x] Install dependencies (`pip install -r requirements.txt`)
- [x] Configure API keys — copy `.env.example` to `.env` and add real OPENAI_API_KEY
- [ ] Grant Accessibility permissions to Terminal app (System Settings > Privacy & Security > Accessibility)

## Testing

- [x] Run `python main.py` and confirm startup message prints
- [x] Hotkey works when another app is in focus
- [x] Audio records correctly from the default mic
- [x] Whisper transcribes English correctly
- [ ] Whisper transcribes Spanish correctly
- [x] GPT (gpt-5-mini) removes filler words without changing meaning
- [ ] GPT preserves technical terms and code references
- [ ] GPT handles Spanish text with correct accents and punctuation
- [ ] GPT handles mixed English/Spanish without translating
- [x] Cleaned text is pasted into the focused app via clipboard
- [ ] Error handling works when APIs are unreachable
- [x] App exits cleanly on Ctrl+Shift+Q
- [ ] Works on macOS with Intel processor

## Completed Improvements

- [x] Push-to-talk (hold to record, release to stop) — replaced toggle hotkey
- [x] Shared OpenAI client — eliminates cold-start latency
- [x] Reduced retry delays (2s → 1s)
- [x] Max completion tokens cap (256) on cleanup calls
- [x] Reduced paste delay (0.4s → 0.15s)
- [x] Short-phrase bypass — skips GPT cleanup for ≤10 words
- [x] Upgraded cleanup model from gpt-5-nano → gpt-5-mini
- [x] Empty response guard — falls back to raw transcript
- [x] Launch script (`start.sh`) with auto-restart on crash

## Future Improvements — Code Mode

- [ ] **Mode toggle hotkey** — second hotkey to switch between prose mode and code mode
- [ ] **Code-aware cleanup prompt** — system prompt tuned for code syntax (e.g., "def my function open paren x close paren" → `def my_function(x):`)
- [ ] **Code vocabulary** — snake_case/camelCase commands, operator dictation ("equals equals" → `==`), bracket/paren commands
- [ ] **Indentation control** — voice commands for indent/dedent/new block
- [ ] **Target app detection** — auto-switch to code mode when an IDE (VS Code, Xcode) is focused
- [ ] **Streaming output** — use OpenAI streaming API to paste tokens as they arrive for faster feedback
