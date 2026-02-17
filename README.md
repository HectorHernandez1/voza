# Voza — AI-Powered Voice-to-Text for macOS

AI-powered push-to-talk dictation for macOS. Hold a hotkey to record, then Whisper transcribes and GPT cleans up your speech before pasting it into the active app.

## Setup

```bash
# 1. Create a Conda environment
conda create -n voza python=3.11 -y
conda activate voza

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure API keys
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

- **Hold Ctrl+Shift+Space** — Push-to-talk (hold to record, release to process)
- **Ctrl+Shift+Q** — Quit

Switch to any app, hold the hotkey, speak, then release. The cleaned text gets pasted into the focused app.

## macOS Permissions

This app requires **Accessibility** permissions for global hotkeys and simulated keystrokes.

Go to **System Settings > Privacy & Security > Accessibility** and grant access to your Terminal app (Terminal.app, iTerm2, etc.).

## How It Works

1. Global hotkey triggers microphone recording
2. Audio is sent to the OpenAI Whisper API for transcription
3. Raw transcript is sent to OpenAI GPT (gpt-5-mini) to remove filler words, fix punctuation, and clean up the text
4. Cleaned text is copied to the clipboard and pasted via simulated Cmd+V

Supports English, Spanish, and mixed-language dictation.
