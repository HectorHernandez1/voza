# Voza — AI-Powered Voice-to-Text for macOS (Intel)

## Architecture

Two-stage AI pipeline:

```
[Global Hotkey] → [Record Mic] → [Whisper API] → [Claude API] → [Clipboard + Cmd+V Paste]
```

## Project Structure

- `main.py` — Entry point, hotkey listener, orchestrates the pipeline
- `recorder.py` — Microphone capture via sounddevice (16kHz mono int16, saves temp WAV)
- `transcriber.py` — OpenAI Whisper API client with 1-retry logic
- `enhancer.py` — Anthropic Claude API cleanup with bilingual system prompt
- `injector.py` — pbcopy + osascript Cmd+V paste into focused app
- `config.py` — Loads .env, validates API keys, holds defaults and system prompt

## Key Design Decisions

- **Clipboard + Cmd+V** for text injection — most reliable cross-app method on macOS
- **pynput GlobalHotKeys** for system-wide hotkeys (requires Accessibility permissions)
- **sounddevice** for audio capture (uses PortAudio, works on Intel Macs)
- **Background thread** for the Whisper→Claude→paste pipeline so hotkey listener stays responsive
- **Threading lock** prevents overlapping pipeline runs
- **No language parameter** on Whisper — auto-detects English/Spanish
- **Fallback** — if Claude fails, raw Whisper transcript is pasted instead
- Recordings < 0.3s are ignored (accidental hotkey press)

## Configuration

All config via `.env` file. See `.env.example` for all options. Required keys:
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`

## Hotkeys

- `Ctrl+Shift+Space` — Toggle recording
- `Ctrl+Shift+Q` — Quit

## macOS Permissions

Requires Accessibility permissions for the terminal app:
System Settings > Privacy & Security > Accessibility

## Dependencies

sounddevice, numpy, pynput, openai, anthropic, python-dotenv
