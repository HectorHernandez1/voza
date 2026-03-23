# Voza — AI-Powered Voice-to-Text (macOS & Linux)

AI-powered push-to-talk dictation. Hold a hotkey to record, then Whisper transcribes and GPT cleans up your speech before pasting it into the active app.

## Setup

```bash
# 1. Create a Conda environment
conda create -n voza python=3.11 -y --override-channels -c conda-forge
conda activate voza

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. (Linux only) Install system packages
sudo apt install -y xclip xdotool libportaudio2

# 4. Configure API keys
cp .env.example .env
# Edit .env and add your OpenAI API key
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

## Platform Notes

### macOS
This app requires **Accessibility** permissions for global hotkeys and simulated keystrokes.
Go to **System Settings > Privacy & Security > Accessibility** and grant access to your Terminal app.

### Linux
- Requires **X11** (Wayland is not supported by pynput for global hotkey capture)
- System packages needed: `xclip` (or `xsel`), `xdotool`, `libportaudio2`

## How It Works

1. Global hotkey triggers microphone recording
2. Audio is sent to the OpenAI Whisper API for transcription
3. Raw transcript is sent to OpenAI GPT to remove filler words, fix punctuation, and clean up the text
4. Cleaned text is copied to the clipboard and pasted via simulated keystroke (Cmd+V on macOS, Ctrl+V on Linux)

Supports English, Spanish, and mixed-language dictation.
