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
- `recorder.py` — Microphone capture via sounddevice (16kHz mono int16, in-memory WAV/OGG); tears down the input stream off-thread with a deadlock watchdog
- `transcriber.py` — Transcription: OpenAI Whisper API (mode=openai) or whisper-server HTTP API (mode=local)
- `enhancer.py` — LLM text cleanup with bilingual system prompt: GPT (mode=openai) or Ollama (mode=local)
- `injector.py` — Cross-platform text injection (pbcopy/osascript on macOS, wl-copy/wtype on Linux)
- `config.py` — Loads .env, validates config, holds defaults and system prompt
- `start.sh` — Launch script with auto-restart on crash
- `pyproject.toml` / `uv.lock` — Dependencies (uv project; run with `uv run main.py`)

## Key Design Decisions

- **Push-to-talk** — hold hotkey to record, release to stop and process
- **Clipboard + paste keystroke** for text injection — pbcopy/osascript on macOS, wl-copy/wtype on Linux
- **Streaming output** (`VOZA_STREAM=true`, default) — LLM cleanup is streamed and typed into the active app as it arrives (osascript keystroke on macOS, wtype on Wayland, xdotool on X11); falls back to single paste when disabled or unsupported (e.g. Wayland without wtype). Short-phrase bypass and error fallbacks still use single paste.
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
- **Cloud fallback in local mode** — if whisper-server or Ollama is unreachable (after one retry) and OPENAI_API_KEY is set, that request falls back to the OpenAI APIs; without a key, local errors propagate as before
- **Dual mode** — `VOZA_MODE=openai` uses OpenAI APIs, `VOZA_MODE=local` uses whisper-server + Ollama
- Recordings < 0.3s are ignored (accidental hotkey press)
- **Startup dead-mic check** — before the hotkey listener starts, records a 0.5s sample and exits if the mic is silent/dead (peak amplitude < `_SILENCE_THRESHOLD` in recorder.py). Both the auto-detect probe and this check retry a few times when everything reads silent — at login (e.g. systemd start) the audio stack may not be up yet, and a working mic always shows a nonzero noise floor. On Linux the probe also restarts PortAudio between retries to re-enumerate late-registering sound cards (skipped on macOS to avoid poking CoreAudio). The threshold is tuned low (10) because a working built-in mic in a quiet room measures peaks of ~17–52 (MacBook Air) while a truly dead/disconnected mic reads ≈0. Fatal mic-check failures exit with code **0** so the launch wrapper stays quit instead of restart-looping on a condition a restart can't fix (dead mic, missing permissions).
- **Off-thread stream teardown** — `Recorder.stop()` captures the audio and returns immediately; the PortAudio input stream is stopped/closed on a background thread so the hotkey listener never blocks on device I/O.
- **Auto-restart on audio hang** — `Pa_StopStream` can deadlock inside CoreAudio's `HALB_Mutex` (typically after sleep/wake or a device change during a long session), which pins the mic open and freezes the listener. A watchdog (`_STOP_TIMEOUT`, 2s) detects the stall and calls `on_hang` → `main._restart_on_hang`, which first waits (up to 30s) for any in-flight dictation to finish pasting, then exits with code 1 so the launch wrapper (`start.sh` / `Voza.app`) respawns a fresh instance — process death is what releases the mic. A circuit breaker skips the restart if the hang occurs within 30s of launch (avoids infinite restart loops).

## Configuration

All config via `.env` file. See `.env.example` for all options.

**OpenAI mode** (default):
- `OPENAI_API_KEY` (required)

**Both modes:**
- `VOZA_STREAM` — stream cleanup output by typing it as it arrives (default: `true`)

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
- Long-running sessions can hit a CoreAudio deadlock when stopping a recording (usually after sleep/wake or a device change). Voza detects it and auto-restarts — see "Auto-restart on audio hang" under Key Design Decisions.

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
# Install Python dependencies (uv creates .venv automatically)
uv sync

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
uv run main.py

# Background
nohup uv run main.py > /tmp/voza.log 2>&1 &
# Check logs: tail -f /tmp/voza.log
# Stop: kill $(pgrep -f "python main.py")
```

The launch wrappers (`start.sh`, `Voza.app`'s `voza.sh`) auto-restart on a **non-zero** exit and stay quit on `0`. This is load-bearing for the audio-deadlock recovery: a CoreAudio hang exits with code 1 so a fresh instance is spawned. Run via `start.sh` or `Voza.app` to get the auto-restart; a bare `uv run main.py` won't self-recover.
