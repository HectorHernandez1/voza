# Voza — AI-Powered Voice-to-Text (macOS & Linux)

AI-powered push-to-talk dictation. Hold a hotkey to record, then Whisper transcribes and an LLM cleans up your speech — the cleaned text streams into the active app live as it's generated.

Supports two modes:
- **OpenAI** (default) — uses OpenAI Whisper API + GPT for transcription and cleanup
- **Local** — uses whisper-server (whisper.cpp) + Ollama for fully local, offline processing. If a local server is unreachable and an `OPENAI_API_KEY` is set, Voza automatically falls back to the OpenAI APIs for that request.

## Setup

```bash
# 1. Install Python dependencies (uv creates .venv automatically)
uv sync

# 2. (Linux only) Install system packages
sudo apt install -y wl-clipboard wtype libportaudio2

# 3. (Linux only) Add your user to the input group for hotkey capture
sudo usermod -aG input $USER
# Log out and back in after running this

# 4. Configure
cp .env.example .env
# Edit .env and add your OpenAI API key (or set VOZA_MODE=local)
```

## Usage

```bash
./start.sh
```

Or manually:

```bash
uv run main.py
```

Run in the background:

```bash
nohup uv run main.py > /tmp/voza.log 2>&1 &

# Check logs
tail -f /tmp/voza.log

# Stop
kill $(pgrep -f "python main.py")
```

- **Hold Ctrl+Shift+Space** — Push-to-talk (hold to record, release to process)
- **Ctrl+Shift+Q** — Quit

Switch to any app, hold the hotkey, speak, then release. The cleaned text is typed into the focused app live as the LLM generates it (or pasted all at once if you set `VOZA_STREAM=false`).

## Local Mode

To run fully local without an OpenAI API key:

1. Set `VOZA_MODE=local` in your `.env` file
2. Run **whisper-server** (from whisper.cpp) with your model loaded — it should be listening on `http://localhost:8080`
3. Run **Ollama** with your cleanup model pulled (e.g., `ollama pull gemma4:e4b`)

On macOS, both are one brew command away:

```bash
brew install ollama whisper-cpp
brew services start ollama
ollama pull gemma4:e4b

# Download a Whisper model (large-v3-turbo recommended on Apple Silicon)
mkdir -p ~/.voza/models
curl -L -o ~/.voza/models/ggml-large-v3-turbo.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin
whisper-server -m ~/.voza/models/ggml-large-v3-turbo.bin --host 127.0.0.1 --port 8080
```

See `.env.example` for all configurable URLs and model names. If `OPENAI_API_KEY`
is also set in `.env`, local mode falls back to the OpenAI APIs whenever
whisper-server or Ollama is unreachable — dictation keeps working even if a
local server is down.

## Project Structure

- `main.py` — entry point: push-to-talk hotkey listener, pipeline orchestration
- `recorder.py` — microphone capture (sounddevice, in-memory WAV/OGG)
- `transcriber.py` — Whisper API or whisper-server transcription (with cloud fallback)
- `enhancer.py` — LLM cleanup, streaming and non-streaming (with cloud fallback)
- `injector.py` — cross-platform text injection (clipboard paste + live typing)
- `api_client.py` — shared OpenAI/Ollama clients
- `config.py` — .env loading, validation, defaults, system prompt
- `start.sh` — launch script with auto-restart on crash
- `pyproject.toml` / `uv.lock` — dependencies (uv project)

## Platform Notes

### macOS
This app requires **Accessibility** permissions for global hotkeys and simulated keystrokes.
Go to **System Settings > Privacy & Security > Accessibility** and grant access to your Terminal app.

### Linux (Wayland)
- Uses **evdev** for global hotkey capture (works on Wayland and X11)
- Uses **wl-clipboard** for clipboard, **uinput** (via evdev) for the paste keystroke, and **wtype** for streamed typing
- System packages needed: `wl-clipboard`, `wtype`, `libportaudio2`
- Your user must be in the **input** group: `sudo usermod -aG input $USER`

## How It Works

1. Global hotkey triggers microphone recording
2. Audio is transcribed (OpenAI Whisper API or local whisper-server)
3. Raw transcript is cleaned up by an LLM (GPT or Ollama) — filler words removed, punctuation fixed
4. Cleaned text streams into the focused app as it's generated, typed via simulated keystrokes (osascript on macOS, wtype on Wayland, xdotool on X11). Short phrases skip cleanup and are pasted directly via the clipboard; set `VOZA_STREAM=false` to always paste the full text at once.

Supports English, Spanish, and mixed-language dictation.

## Run at Login (macOS)

Voza and whisper-server can run as launchd agents so everything starts at login
(Ollama already does this via `brew services start ollama`).

Create `~/Library/LaunchAgents/com.voza.app.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.voza.app</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/voza/.venv/bin/python</string>
        <string>-u</string>
        <string>main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/voza</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>ThrottleInterval</key>
    <integer>5</integer>
    <key>StandardOutPath</key>
    <string>/Users/you/.voza/voza.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/you/.voza/voza.log</string>
</dict>
</plist>
```

`KeepAlive.SuccessfulExit=false` restarts Voza on crashes but leaves it stopped
after a clean quit (Ctrl+Shift+Q) until the next login.

For local mode, create `~/Library/LaunchAgents/com.voza.whisper-server.plist` the
same way with `ProgramArguments` of `whisper-server -m <model> --host 127.0.0.1
--port 8080` and plain `KeepAlive` `true`.

```bash
launchctl load ~/Library/LaunchAgents/com.voza.app.plist            # start now + at login
launchctl unload ~/Library/LaunchAgents/com.voza.app.plist          # stop + disable
tail -f ~/.voza/voza.log                                            # watch logs
```

Grant **Microphone** and **Accessibility** permissions to the `.venv` Python
binary when macOS prompts on first launch.

## Run as a Service (Linux)

To have Voza start automatically when you log in, set it up as a systemd user service.

### 1. Create the service file

```bash
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/voza.service << 'EOF'
[Unit]
Description=Voza Voice-to-Text Dictation
After=whisper-server.service ollama.service

[Service]
ExecStart=/path/to/voza/.venv/bin/python /path/to/voza/main.py
WorkingDirectory=/path/to/voza
Restart=on-failure
RestartSec=3
EnvironmentFile=/path/to/voza/.env

[Install]
WantedBy=default.target
EOF
```

Update the paths in the file to match your setup.

### 2. Enable and start

```bash
systemctl --user daemon-reload
systemctl --user enable voza
systemctl --user start voza
```

### 3. Manage the service

```bash
systemctl --user status voza        # Check status
systemctl --user stop voza          # Stop
systemctl --user start voza         # Start
systemctl --user restart voza       # Restart (after code changes)
journalctl --user -u voza -f        # Watch live logs
```

### whisper-server service (for local mode)

If using local mode, whisper-server should also run as a service. Create `/etc/systemd/system/whisper-server.service`:

```ini
[Unit]
Description=Whisper.cpp Server (ROCm)
After=network.target

[Service]
ExecStart=/path/to/whisper.cpp/build/bin/whisper-server -m /path/to/models/ggml-large-v3.bin --host 127.0.0.1 --port 8080
Restart=on-failure
RestartSec=5
User=your-username

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable whisper-server
sudo systemctl start whisper-server
```
