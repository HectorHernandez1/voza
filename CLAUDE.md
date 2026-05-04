# Voza — AI-Powered Voice-to-Text (macOS & Linux)

## Architecture

Two-stage AI pipeline with two modes:

**OpenAI mode** (default):
```
[Hold Hotkey] → [Record Mic] → [Release] → [Whisper API] → [GPT Cleanup] → [Clipboard + Paste]
```

**Local mode** (`VOZA_MODE=local`):
```
[Hold Hotkey] → [Record Mic] → [Release] → [whisper-server] → [Ollama Cleanup] → [Clipboard + Paste]
```

## Project Structure

- `main.py` — Entry point, push-to-talk hotkey listener (pynput on macOS, evdev on Linux), orchestrates the pipeline
- `api_client.py` — Shared AI client: OpenAI client (mode=openai) or Ollama-compatible client (mode=local)
- `recorder.py` — Microphone capture via sounddevice (16kHz mono int16, in-memory WAV/OGG)
- `transcriber.py` — Transcription: OpenAI Whisper API (mode=openai) or whisper-server HTTP API (mode=local)
- `enhancer.py` — LLM text cleanup with bilingual system prompt: GPT (mode=openai) or Ollama (mode=local)
- `injector.py` — Cross-platform text injection (pbcopy/osascript on macOS, wl-copy/wtype on Linux)
- `config.py` — Loads .env, validates config, holds defaults and system prompt
- `start.sh` — Launch script with auto-restart on crash

## Key Design Decisions

- **Push-to-talk** — hold hotkey to record, release to stop and process
- **Clipboard + paste keystroke** for text injection — pbcopy/osascript on macOS, wl-copy/wtype on Linux
- **pynput Listener** on macOS for system-wide hotkeys (requires Accessibility permissions)
- **evdev** on Linux for system-wide hotkeys (reads /dev/input directly, works on Wayland; requires `input` group)
- **sounddevice** for audio capture (uses PortAudio, cross-platform)
- **Background thread** for the transcription→cleanup→paste pipeline so hotkey listener stays responsive
- **Threading lock** prevents overlapping pipeline runs
- **Short-phrase bypass** — skips LLM cleanup for ≤15 words to reduce latency
- **In-memory audio** — audio stays in BytesIO buffers (no temp files on disk)
- **OGG/Opus compression** — if ffmpeg is installed, audio is compressed before upload (~90% smaller)
- **No language parameter** on Whisper — auto-detects English/Spanish
- **Fallback** — if LLM cleanup fails or returns empty, raw Whisper transcript is pasted instead
- **Dual mode** — `VOZA_MODE=openai` uses OpenAI APIs, `VOZA_MODE=local` uses whisper-server + Ollama
- Recordings < 0.3s are ignored (accidental hotkey press)

## Configuration

All config via `.env` file. See `.env.example` for all options.

**OpenAI mode** (default):
- `OPENAI_API_KEY` (required)

**Local mode** (`VOZA_MODE=local`):
- `WHISPER_SERVER_URL` — whisper-server endpoint (default: `http://localhost:8080`)
- `OLLAMA_BASE_URL` — Ollama endpoint (default: `http://localhost:11434`)
- `LOCAL_CLEANUP_MODEL` — Ollama model for text cleanup (default: `gemma4:e4b`)

## Hotkeys

- `Ctrl+Shift+Space` — Push-to-talk (hold to record, release to process)
- `Ctrl+Shift+Q` — Quit

## Platform Notes

### macOS
- Requires Accessibility permissions: System Settings > Privacy & Security > Accessibility

### Linux (Wayland)
- Uses evdev for global hotkey capture (works on Wayland and X11)
- User must be in the `input` group: `sudo usermod -aG input $USER` (log out and back in)
- System packages: `sudo apt install -y wl-clipboard wtype libportaudio2`

## Dependencies

**Python:** sounddevice, numpy, pynput (macOS), evdev (Linux), openai, python-dotenv, requests

**System (macOS):** None (Accessibility permissions only)

**System (Linux):** wl-clipboard, wtype, libportaudio2

## Setup

```bash
# Create conda environment
conda create -n voza python=3.11 -y --override-channels -c conda-forge
conda activate voza
pip install -r requirements.txt

# Linux only — install system packages
sudo apt install -y wl-clipboard wtype libportaudio2

# Linux only — add user to input group for hotkey capture
sudo usermod -aG input $USER
# Log out and back in
```

## Running

```bash
# Foreground (with auto-restart on crash)
./start.sh

# Or directly
conda activate voza
python main.py

# Background
conda activate voza
nohup python main.py > /tmp/voza.log 2>&1 &
# Check logs: tail -f /tmp/voza.log
# Stop: kill $(pgrep -f "python main.py")
```
