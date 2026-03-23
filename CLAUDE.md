# Voza — AI-Powered Voice-to-Text (macOS & Linux)

## Architecture

Two-stage AI pipeline:

```
[Hold Hotkey] → [Record Mic] → [Release] → [Whisper API] → [GPT Cleanup] → [Clipboard + Cmd+V Paste]
```

## Project Structure

- `main.py` — Entry point, push-to-talk hotkey listener, orchestrates the pipeline
- `api_client.py` — Shared OpenAI client (initialized once at import)
- `recorder.py` — Microphone capture via sounddevice (16kHz mono int16, saves temp WAV)
- `transcriber.py` — OpenAI Whisper API client with 1-retry logic
- `enhancer.py` — OpenAI GPT cleanup (gpt-4o-mini, temperature=0) with bilingual system prompt
- `injector.py` — Cross-platform text injection (pbcopy/osascript on macOS, xclip/xdotool on Linux)
- `config.py` — Loads .env, validates API keys, holds defaults and system prompt
- `start.sh` — Launch script with auto-restart on crash

## Key Design Decisions

- **Push-to-talk** — hold hotkey to record, release to stop and process
- **Clipboard + paste keystroke** for text injection — pbcopy/osascript on macOS, xclip/xdotool on Linux
- **pynput Listener** for system-wide hotkeys with press/release tracking (macOS: Accessibility permissions; Linux: X11 required)
- **sounddevice** for audio capture (uses PortAudio, cross-platform)
- **Background thread** for the Whisper→GPT→paste pipeline so hotkey listener stays responsive
- **Threading lock** prevents overlapping pipeline runs
- **Short-phrase bypass** — skips GPT cleanup for ≤15 words to reduce latency
- **In-memory audio** — audio stays in BytesIO buffers (no temp files on disk)
- **OGG/Opus compression** — if ffmpeg is installed, audio is compressed before upload (~90% smaller)
- **No language parameter** on Whisper — auto-detects English/Spanish
- **Fallback** — if GPT cleanup fails or returns empty, raw Whisper transcript is pasted instead
- Recordings < 0.3s are ignored (accidental hotkey press)

## Configuration

All config via `.env` file. See `.env.example` for all options. Required key:
- `OPENAI_API_KEY`

## Hotkeys

- `Ctrl+Shift+Space` — Push-to-talk (hold to record, release to process)
- `Ctrl+Shift+Q` — Quit

## Platform Notes

### macOS
- Requires Accessibility permissions: System Settings > Privacy & Security > Accessibility

### Linux
- Requires X11 (Wayland not supported by pynput for global hotkeys)
- System packages: `sudo apt install -y xclip xdotool libportaudio2`

## Dependencies

**Python:** sounddevice, numpy, pynput, openai, python-dotenv

**System (Linux only):** xclip (or xsel), xdotool, libportaudio2

## Setup

```bash
# Create conda environment
conda create -n voza python=3.11 -y --override-channels -c conda-forge
conda activate voza
pip install -r requirements.txt

# Linux only — install system packages
sudo apt install -y xclip xdotool libportaudio2
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
