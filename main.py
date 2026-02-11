#!/usr/bin/env python3
"""Voza — AI-powered voice-to-text dictation for macOS."""

import os
import sys
import threading

from pynput import keyboard

import config
from recorder import Recorder
from transcriber import transcribe
from enhancer import enhance
from injector import inject


def parse_hotkey(hotkey_str: str):
    """Parse a hotkey string like 'ctrl+shift+space' into a pynput HotKey combo."""
    parts = hotkey_str.lower().split("+")
    combo = []
    for part in parts:
        part = part.strip()
        if part == "ctrl":
            combo.append("<ctrl>")
        elif part == "shift":
            combo.append("<shift>")
        elif part == "alt":
            combo.append("<alt>")
        elif part == "cmd":
            combo.append("<cmd>")
        elif part == "space":
            combo.append("<space>")
        else:
            combo.append(part)
    return "+".join(combo)


recorder = Recorder()
processing_lock = threading.Lock()


def on_record_toggle():
    """Called when the record hotkey is pressed."""
    if recorder.is_recording:
        # Stop recording and process
        print("Processing...")
        audio_path = recorder.stop()

        if audio_path is None:
            print("No audio captured (too short). Ready.")
            return

        # Process in a background thread so hotkey listener isn't blocked
        threading.Thread(target=_process_audio, args=(audio_path,), daemon=True).start()
    else:
        recorder.start()
        print("Recording... (press {} to stop)".format(config.HOTKEY_RECORD))


def _process_audio(audio_path: str):
    """Run the Whisper → Claude → paste pipeline."""
    with processing_lock:
        raw_text = None
        cleaned_text = None

        try:
            # Stage 1: Whisper
            raw_text = transcribe(audio_path)
            print(f"  [Whisper] {raw_text}")
        except Exception as e:
            print(f"Error: Whisper transcription failed: {e}")
            _cleanup(audio_path)
            print("Ready.")
            return

        try:
            # Stage 2: GPT cleanup
            cleaned_text = enhance(raw_text)
        except Exception as e:
            print(f"Warning: Cleanup failed ({e}). Using raw transcript.")
            cleaned_text = raw_text

        # Stage 3: Inject into active app
        try:
            inject(cleaned_text)
            print(f"  [Pasted] {cleaned_text}")
        except Exception as e:
            print(f"Error: Failed to paste text: {e}")
            print(f"  Text was: {cleaned_text}")

        _cleanup(audio_path)
        print("Ready.")


def _cleanup(audio_path: str):
    """Remove temporary audio file."""
    try:
        os.unlink(audio_path)
    except OSError:
        pass


def on_quit():
    """Called when the quit hotkey is pressed."""
    print("\nQuitting Voza. Goodbye!")
    os._exit(0)


def main():
    config.validate()

    record_combo = parse_hotkey(config.HOTKEY_RECORD)
    quit_combo = parse_hotkey(config.HOTKEY_QUIT)

    hotkeys = keyboard.GlobalHotKeys({
        record_combo: on_record_toggle,
        quit_combo: on_quit,
    })

    print("=" * 50)
    print("  Voza — AI-Powered Voice-to-Text")
    print("=" * 50)
    print(f"  Record:  {config.HOTKEY_RECORD}")
    print(f"  Quit:    {config.HOTKEY_QUIT}")
    print(f"  Whisper: {config.WHISPER_MODEL}")
    print(f"  Cleanup: {config.CLEANUP_MODEL}")
    print("=" * 50)
    print()
    print("Voza is running. Press {} to start dictating. Press {} to quit.".format(
        config.HOTKEY_RECORD, config.HOTKEY_QUIT
    ))
    print()
    print("NOTE: This app requires macOS Accessibility permissions.")
    print("If hotkeys don't work, go to:")
    print("  System Settings > Privacy & Security > Accessibility")
    print("  and grant access to your Terminal app.")
    print()
    print("Ready.")

    hotkeys.start()

    try:
        hotkeys.join()
    except KeyboardInterrupt:
        print("\nInterrupted. Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()
