#!/usr/bin/env python3
"""Voza — AI-powered voice-to-text dictation for macOS."""

import os
import sys
import threading

import numpy as np
import sounddevice as sd
from pynput import keyboard

import config
from recorder import Recorder, _SILENCE_THRESHOLD
from transcriber import transcribe
from enhancer import enhance
from injector import inject


# ---------------------------------------------------------------------------
# Key parsing helpers
# ---------------------------------------------------------------------------

# Map config names → pynput Key objects for modifiers / special keys
_SPECIAL_KEYS = {
    "ctrl": keyboard.Key.ctrl,
    "shift": keyboard.Key.shift,
    "alt": keyboard.Key.alt,
    "cmd": keyboard.Key.cmd,
    "space": keyboard.Key.space,
}


def _parse_combo(hotkey_str: str):
    """Return a frozenset of pynput key objects for a hotkey string like 'ctrl+shift+space'."""
    keys = set()
    for part in hotkey_str.lower().split("+"):
        part = part.strip()
        if part in _SPECIAL_KEYS:
            keys.add(_SPECIAL_KEYS[part])
        else:
            # Single character key
            keys.add(keyboard.KeyCode.from_char(part))
    return frozenset(keys)


def _normalize_key(key):
    """Normalize a key event into a comparable value."""
    # Map left/right variants to their generic counterparts
    _VARIANTS = {
        keyboard.Key.ctrl_l: keyboard.Key.ctrl,
        keyboard.Key.ctrl_r: keyboard.Key.ctrl,
        keyboard.Key.shift_l: keyboard.Key.shift,
        keyboard.Key.shift_r: keyboard.Key.shift,
        keyboard.Key.alt_l: keyboard.Key.alt,
        keyboard.Key.alt_r: keyboard.Key.alt,
        keyboard.Key.cmd_l: keyboard.Key.cmd,
        keyboard.Key.cmd_r: keyboard.Key.cmd,
    }
    return _VARIANTS.get(key, key)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

recorder = Recorder()
processing_lock = threading.Lock()
pressed_keys: set = set()


# ---------------------------------------------------------------------------
# Mic verification
# ---------------------------------------------------------------------------

def _check_mic():
    """Record a short sample to verify the default mic is alive. Exit if dead."""
    print("  Checking microphone...", end=" ", flush=True)
    try:
        duration = 0.5  # half-second test
        audio = sd.rec(
            int(config.SAMPLE_RATE * duration),
            samplerate=config.SAMPLE_RATE,
            channels=config.CHANNELS,
            dtype="int16",
            device=config.AUDIO_DEVICE,
        )
        sd.wait()
    except Exception as e:
        print(f"\n\n  ERROR: Could not access microphone: {e}")
        print("  Please check that a microphone is connected and permissions are granted.")
        print("  Then restart the app.\n")
        sys.exit(1)

    peak = int(np.max(np.abs(audio)))
    if peak < _SILENCE_THRESHOLD:
        print(f"SILENT (peak={peak})")
        print()
        print("  WARNING: Microphone appears dead or muted.")
        print("  Possible fixes:")
        print("    1. Check that your mic is not muted in System Settings > Sound > Input")
        print("    2. Run: sudo killall coreaudiod  (resets the audio daemon)")
        print("    3. Unplug and replug your microphone")
        print("  Then restart the app.")
        print()
        sys.exit(1)
    else:
        print(f"OK (peak={peak})")


# ---------------------------------------------------------------------------
# Audio pipeline
# ---------------------------------------------------------------------------

# Known Whisper hallucination outputs from silent/bad audio
_HALLUCINATION_WORDS = {
    "you", "the", "a", "i", "thank you", "thanks",
    "bye", "goodbye", "yeah", "yes", "no", "okay",
    "so", "and", "but", "or", "it", "he", "she",
}


def _process_audio(audio_path: str):
    """Run the Whisper → GPT → paste pipeline."""
    with processing_lock:
        raw_text = None
        cleaned_text = None

        try:
            raw_text = transcribe(audio_path)
            print(f"  [Whisper] {raw_text}")
        except Exception as e:
            print(f"Error: Whisper transcription failed: {e}")
            _cleanup(audio_path)
            print("Ready.")
            return

        # Guard against Whisper hallucinations from silent/bad audio
        stripped = raw_text.strip().strip(".!?,").lower()
        if stripped in _HALLUCINATION_WORDS:
            print("  [Warning] Likely mic issue — transcript looks like a hallucination.")
            print("  Check your audio input device. Skipping paste.")
            _cleanup(audio_path)
            print("Ready.")
            return

        # Short phrases don't need GPT cleanup — skip to save time
        if len(raw_text.split()) <= 10:
            cleaned_text = raw_text
            print("  [Cleanup] Skipped (short phrase)")
        else:
            try:
                cleaned_text = enhance(raw_text)
            except Exception as e:
                print(f"Warning: Cleanup failed ({e}). Using raw transcript.")
                cleaned_text = raw_text

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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    config.validate()
    _check_mic()

    record_combo = _parse_combo(config.HOTKEY_RECORD)
    quit_combo = _parse_combo(config.HOTKEY_QUIT)

    # --- key callbacks ---------------------------------------------------

    def on_press(key):
        key = _normalize_key(key)
        pressed_keys.add(key)

        # Quit combo
        if quit_combo <= pressed_keys:
            print("\nQuitting Voza. Goodbye!")
            os._exit(0)

        # Record combo — start recording when all keys are held
        if record_combo <= pressed_keys and not recorder.is_recording:
            if processing_lock.locked():
                return  # still processing previous clip
            recorder.start()
            print("Recording... (release to stop)")

    def on_release(key):
        key = _normalize_key(key)

        # If we were recording and any key in the combo is released → stop
        if recorder.is_recording and key in record_combo:
            print("Processing...")
            audio_path = recorder.stop()
            pressed_keys.discard(key)

            if audio_path is None:
                reason = recorder.last_stop_reason
                if reason == "silent":
                    print("  Mic appears silent/dead. Check your input device.")
                    print("  Try: System Settings > Sound > Input, or restart the app.")
                else:
                    print("  No audio captured (too short).")
                print("Ready.")
                return

            threading.Thread(
                target=_process_audio, args=(audio_path,), daemon=True
            ).start()
        else:
            pressed_keys.discard(key)

    # --- banner ----------------------------------------------------------

    print("=" * 50)
    print("  Voza — AI-Powered Voice-to-Text")
    print("=" * 50)
    print(f"  Record:  {config.HOTKEY_RECORD} (push-to-talk)")
    print(f"  Quit:    {config.HOTKEY_QUIT}")
    dev_info = sd.query_devices(config.AUDIO_DEVICE, kind='input')
    print(f"  Mic:     [{config.AUDIO_DEVICE}] {dev_info['name']}")
    print(f"  Whisper: {config.WHISPER_MODEL}")
    print(f"  Cleanup: {config.CLEANUP_MODEL}")
    print("=" * 50)
    print()
    print("Hold {} to record, release to process & paste.".format(
        config.HOTKEY_RECORD
    ))
    print("Press {} to quit.".format(config.HOTKEY_QUIT))
    print()
    print("NOTE: This app requires macOS Accessibility permissions.")
    print("If hotkeys don't work, go to:")
    print("  System Settings > Privacy & Security > Accessibility")
    print("  and grant access to your Terminal app.")
    print()
    print("Ready.")

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        try:
            listener.join()
        except KeyboardInterrupt:
            print("\nInterrupted. Goodbye!")
            sys.exit(0)


if __name__ == "__main__":
    main()
