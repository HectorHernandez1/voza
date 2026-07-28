# Voza — Setup & Testing Checklist

## Setup

- [x] Install dependencies with uv (`uv sync` — creates `.venv` automatically)
- [x] Configure API keys — copy `.env.example` to `.env` and add real OPENAI_API_KEY
- [x] Set up local mode — whisper-server (large-v3-turbo) + Ollama (`gemma4:e4b`), both as login services
- [ ] Grant Accessibility + Microphone permissions to the launching app (System Settings > Privacy & Security)

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
- [x] Short-phrase bypass — skips GPT cleanup for ≤15 words
- [x] Upgraded cleanup model from gpt-5-nano → gpt-4o-mini
- [x] Empty response guard — falls back to raw transcript
- [x] Launch script (`start.sh`) with auto-restart on crash
- [x] In-memory audio buffers — eliminated temp file disk I/O
- [x] OGG/Opus compression via ffmpeg (falls back to WAV if ffmpeg unavailable)
- [x] Deterministic decoding (temperature=0) on cleanup calls
- [x] Streaming output — LLM cleanup streams and is typed into the active app as it arrives (`VOZA_STREAM`, default on)
- [x] uv project workflow — `pyproject.toml` + `uv.lock`, `uv run main.py` (replaced conda + requirements.txt)
- [x] Cloud fallback — local mode falls back to OpenAI APIs when whisper-server/Ollama are unreachable (tested)
- [x] Run at login on macOS — launchd agents for Voza, whisper-server, and Ollama

## Future Project — Standalone App Distribution

Goal: turn Voza into an installable Mac app others can use.

- [ ] **Phase 1 — Developer ID app (outside App Store, keeps all features)**
  - Apple Developer Program membership ($99/yr)
  - Bundle the app (briefcase/py2app short-term, or native rewrite), sign with Developer ID, notarize
  - Distribute via website/GitHub; Sparkle for auto-updates
  - Keeps auto-typing into other apps — no sandbox restrictions
- [ ] **Phase 2 (optional) — Mac App Store version**
  - Hard constraint: App Sandbox ignores CGEventPost, so auto-typing into other
    apps is impossible — output must become clipboard + manual Cmd+V (this is
    why superwhisper/Wispr Flow distribute outside the store)
  - Requires full Swift rewrite: AVAudioEngine (capture), Apple Speech framework
    (on-device transcription), Foundation Models framework (on-device cleanup,
    macOS 26+) — would eliminate the whisper-server and Ollama dependencies
  - Sandbox entitlements (mic, network), privacy policy, App Review
  - Estimated 6–10 weeks side-project time

## Future Improvements — Code Mode

- [ ] **Mode toggle hotkey** — second hotkey to switch between prose mode and code mode
- [ ] **Code-aware cleanup prompt** — system prompt tuned for code syntax (e.g., "def my function open paren x close paren" → `def my_function(x):`)
- [ ] **Code vocabulary** — snake_case/camelCase commands, operator dictation ("equals equals" → `==`), bracket/paren commands
- [ ] **Indentation control** — voice commands for indent/dedent/new block
- [ ] **Target app detection** — auto-switch to code mode when an IDE (VS Code, Xcode) is focused
