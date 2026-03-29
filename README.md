# Voza — AI-Powered Voice-to-Text (macOS & Linux)

AI-powered push-to-talk dictation. Hold a hotkey to record, then Whisper transcribes and an LLM cleans up your speech before pasting it into the active app.

Supports two modes:
- **OpenAI** (default) — uses OpenAI Whisper API + GPT for transcription and cleanup
- **Local** — uses whisper-server (whisper.cpp) + Ollama for fully local, offline processing

## Setup

```bash
# 1. Create a Conda environment
conda create -n voza python=3.11 -y --override-channels -c conda-forge
conda activate voza

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. (Linux only) Install system packages
sudo apt install -y wl-clipboard ydotool libportaudio2

# 4. (Linux only) Add your user to the input group for hotkey capture
sudo usermod -aG input $USER
# Log out and back in after running this

# 5. Configure
cp .env.example .env
# Edit .env and add your OpenAI API key (or set VOZA_MODE=local)
```

## Usage

```bash
./start.sh
```

Or manually:

```bash
conda activate voza
python main.py
```

Run in the background:

```bash
conda activate voza
nohup python main.py > /tmp/voza.log 2>&1 &

# Check logs
tail -f /tmp/voza.log

# Stop
kill $(pgrep -f "python main.py")
```

- **Hold Ctrl+Shift+Space** — Push-to-talk (hold to record, release to process)
- **Ctrl+Shift+Q** — Quit

Switch to any app, hold the hotkey, speak, then release. The cleaned text gets pasted into the focused app.

## Local Mode

To run fully local without an OpenAI API key:

1. Set `VOZA_MODE=local` in your `.env` file
2. Run **whisper-server** (from whisper.cpp) with your model loaded — it should be listening on `http://localhost:8080`
3. Run **Ollama** with your cleanup model pulled (e.g., `ollama pull qwen3:8b`)

See `.env.example` for all configurable URLs and model names.

## Platform Notes

### macOS
This app requires **Accessibility** permissions for global hotkeys and simulated keystrokes.
Go to **System Settings > Privacy & Security > Accessibility** and grant access to your Terminal app.

### Linux (Wayland)
- Uses **evdev** for global hotkey capture (works on Wayland and X11)
- Uses **wl-clipboard** for clipboard and **ydotool** for paste simulation
- System packages needed: `wl-clipboard`, `ydotool`, `libportaudio2`
- Your user must be in the **input** group: `sudo usermod -aG input $USER`

## How It Works

1. Global hotkey triggers microphone recording
2. Audio is transcribed (OpenAI Whisper API or local whisper-server)
3. Raw transcript is cleaned up by an LLM (GPT or Ollama) — filler words removed, punctuation fixed
4. Cleaned text is copied to the clipboard and pasted via simulated keystroke (Cmd+V on macOS, Ctrl+V on Linux)

Supports English, Spanish, and mixed-language dictation.

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
ExecStart=/path/to/your/conda/envs/voza/bin/python /path/to/voza/main.py
WorkingDirectory=/path/to/voza
Restart=on-failure
RestartSec=3
EnvironmentFile=/path/to/voza/.env

[Install]
WantedBy=default.target
EOF
```

Update the paths in the file to match your setup. Find your conda env path with `conda info --envs | grep voza`.

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
