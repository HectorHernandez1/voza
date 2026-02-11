# Voza — AI-Powered Voice-to-Text for macOS

System-wide dictation tool that records your voice, transcribes it with OpenAI Whisper, cleans it up with Claude, and pastes the result into whatever app you're using.

## Setup

```bash
# 1. Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure API keys
cp .env.example .env
# Edit .env and add your OpenAI and Anthropic API keys
```

## Usage

```bash
python main.py
```

- **Ctrl+Shift+Space** — Start/stop recording
- **Ctrl+Shift+Q** — Quit

Switch to any app, press the hotkey, speak, press the hotkey again. The cleaned text gets pasted into the focused app.

## macOS Permissions

This app requires **Accessibility** permissions for global hotkeys and simulated keystrokes.

Go to **System Settings > Privacy & Security > Accessibility** and grant access to your Terminal app (Terminal.app, iTerm2, etc.).

## How It Works

1. Global hotkey triggers microphone recording
2. Audio is sent to the OpenAI Whisper API for transcription
3. Raw transcript is sent to the Claude API to remove filler words, fix punctuation, and clean up the text
4. Cleaned text is copied to the clipboard and pasted via simulated Cmd+V

Supports English, Spanish, and mixed-language dictation.
