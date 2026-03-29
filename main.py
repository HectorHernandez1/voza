#!/usr/bin/env python3
"""Voza — AI-powered voice-to-text dictation."""


import sys
import threading

import numpy as np
import sounddevice as sd

_IS_MACOS = sys.platform == "darwin"

if _IS_MACOS:
    from pynput import keyboard
else:
    import evdev
    import evdev.ecodes as e

import config
from recorder import Recorder, _SILENCE_THRESHOLD, _HAS_FFMPEG
from transcriber import transcribe
from enhancer import enhance
from injector import inject


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

recorder = Recorder()
processing_lock = threading.Lock()


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
    except Exception as exc:
        print(f"\n\n  ERROR: Could not access microphone: {exc}")
        print("  Please check that a microphone is connected and permissions are granted.")
        print("  Then restart the app.\n")
        sys.exit(1)

    peak = int(np.max(np.abs(audio)))
    if peak < _SILENCE_THRESHOLD:
        print(f"SILENT (peak={peak})")
        print()
        print("  WARNING: Microphone appears dead or muted.")
        print("  Possible fixes:")
        if _IS_MACOS:
            print("    1. Check that your mic is not muted in System Settings > Sound > Input")
            print("    2. Run: sudo killall coreaudiod  (resets the audio daemon)")
        else:
            print("    1. Check that your mic is not muted (e.g., pavucontrol or alsamixer)")
            print("    2. Run: pulseaudio -k  (restarts PulseAudio)")
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


def _process_audio(audio_buffer):
    """Run the Whisper → LLM → paste pipeline."""
    with processing_lock:
        raw_text = None
        cleaned_text = None

        try:
            raw_text = transcribe(audio_buffer)
            print(f"  [Whisper] {raw_text}")
        except Exception as exc:
            print(f"Error: Whisper transcription failed: {exc}")
            print("Ready.")
            return

        # Guard against Whisper hallucinations from silent/bad audio
        stripped = raw_text.strip().strip(".!?,").lower()
        if stripped in _HALLUCINATION_WORDS:
            print("  [Warning] Likely mic issue — transcript looks like a hallucination.")
            print("  Check your audio input device. Skipping paste.")
            print("Ready.")
            return

        # Short phrases don't need LLM cleanup — skip to save time
        if len(raw_text.split()) <= 15:
            cleaned_text = raw_text
            print("  [Cleanup] Skipped (short phrase)")
        else:
            try:
                cleaned_text = enhance(raw_text)
            except Exception as exc:
                print(f"Warning: Cleanup failed ({exc}). Using raw transcript.")
                cleaned_text = raw_text

        try:
            inject(cleaned_text)
            print(f"  [Pasted] {cleaned_text}")
        except Exception as exc:
            print(f"Error: Failed to paste text: {exc}")
            print(f"  Text was: {cleaned_text}")

        print("Ready.")


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

def _print_banner():
    dev_info = sd.query_devices(config.AUDIO_DEVICE, kind='input')
    mode_label = config.VOZA_MODE.upper()

    print("=" * 50)
    print("  Voza — AI-Powered Voice-to-Text")
    print("=" * 50)
    print(f"  Mode:    {mode_label}")
    print(f"  Record:  {config.HOTKEY_RECORD} (push-to-talk)")
    print(f"  Quit:    {config.HOTKEY_QUIT}")
    print(f"  Mic:     [{config.AUDIO_DEVICE}] {dev_info['name']}")

    if config.VOZA_MODE == "local":
        print(f"  Whisper: whisper-server @ {config.WHISPER_SERVER_URL}")
        print(f"  Cleanup: {config.LOCAL_CLEANUP_MODEL} (Ollama)")
    else:
        print(f"  Whisper: {config.WHISPER_MODEL}")
        print(f"  Cleanup: {config.CLEANUP_MODEL}")

    print(f"  Compress: {'OGG/Opus (ffmpeg)' if _HAS_FFMPEG else 'Off (install ffmpeg to enable)'}")

    print("=" * 50)
    print()
    print("Hold {} to record, release to process & paste.".format(
        config.HOTKEY_RECORD
    ))
    print("Press {} to quit.".format(config.HOTKEY_QUIT))
    print()
    if _IS_MACOS:
        print("NOTE: This app requires macOS Accessibility permissions.")
        print("If hotkeys don't work, go to:")
        print("  System Settings > Privacy & Security > Accessibility")
        print("  and grant access to your Terminal app.")
    else:
        print("NOTE: Using evdev for hotkey capture (Wayland-compatible).")
        print("Required system packages: wl-clipboard and wtype.")
        print("Your user must be in the 'input' group for hotkey capture.")
    print()
    print("Ready.")


# ---------------------------------------------------------------------------
# macOS listener (pynput)
# ---------------------------------------------------------------------------

if _IS_MACOS:
    _SPECIAL_KEYS = {
        "ctrl": keyboard.Key.ctrl,
        "shift": keyboard.Key.shift,
        "alt": keyboard.Key.alt,
        "cmd": keyboard.Key.cmd,
        "space": keyboard.Key.space,
    }

    def _parse_combo_pynput(hotkey_str: str):
        keys = set()
        for part in hotkey_str.lower().split("+"):
            part = part.strip()
            if part in _SPECIAL_KEYS:
                keys.add(_SPECIAL_KEYS[part])
            else:
                keys.add(keyboard.KeyCode.from_char(part))
        return frozenset(keys)

    def _normalize_key(key):
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

    def _run_macos():
        record_combo = _parse_combo_pynput(config.HOTKEY_RECORD)
        quit_combo = _parse_combo_pynput(config.HOTKEY_QUIT)
        pressed_keys: set = set()

        def on_press(key):
            key = _normalize_key(key)
            pressed_keys.add(key)

            if quit_combo <= pressed_keys:
                print("\nQuitting Voza. Goodbye!")
                import os as _os; _os._exit(0)

            if record_combo <= pressed_keys and not recorder.is_recording:
                if processing_lock.locked():
                    return
                recorder.start()
                print("Recording... (release to stop)")

        def on_release(key):
            key = _normalize_key(key)

            if recorder.is_recording and key in record_combo:
                print("Processing...")
                audio_buffer = recorder.stop()
                pressed_keys.discard(key)

                if audio_buffer is None:
                    reason = recorder.last_stop_reason
                    if reason == "silent":
                        print("  Mic appears silent/dead. Check your input device.")
                        print("  Try: System Settings > Sound > Input, or restart the app.")
                    else:
                        print("  No audio captured (too short).")
                    print("Ready.")
                    return

                threading.Thread(
                    target=_process_audio, args=(audio_buffer,), daemon=True
                ).start()
            else:
                pressed_keys.discard(key)

        _print_banner()
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            try:
                listener.join()
            except KeyboardInterrupt:
                print("\nInterrupted. Goodbye!")
                sys.exit(0)


# ---------------------------------------------------------------------------
# Linux listener (evdev)
# ---------------------------------------------------------------------------

if not _IS_MACOS:
    # Map config key names to sets of equivalent evdev keycodes
    _EVDEV_SPECIAL = {
        "ctrl":  {e.KEY_LEFTCTRL, e.KEY_RIGHTCTRL},
        "shift": {e.KEY_LEFTSHIFT, e.KEY_RIGHTSHIFT},
        "alt":   {e.KEY_LEFTALT, e.KEY_RIGHTALT},
        "cmd":   {e.KEY_LEFTMETA, e.KEY_RIGHTMETA},
        "space": {e.KEY_SPACE},
    }

    # Single characters a-z
    _EVDEV_CHAR = {
        chr(c): getattr(e, f"KEY_{chr(c).upper()}")
        for c in range(ord('a'), ord('z') + 1)
    }

    def _parse_combo_evdev(hotkey_str: str):
        """Parse 'ctrl+shift+space' into a tuple of frozensets of evdev keycodes."""
        groups = []
        for part in hotkey_str.lower().split("+"):
            part = part.strip()
            if part in _EVDEV_SPECIAL:
                groups.append(frozenset(_EVDEV_SPECIAL[part]))
            elif part in _EVDEV_CHAR:
                groups.append(frozenset({_EVDEV_CHAR[part]}))
            else:
                raise ValueError(f"Unknown key in hotkey: {part}")
        return tuple(groups)

    def _combo_active(combo, pressed: set) -> bool:
        """Check if all key groups in a combo have at least one key pressed."""
        return all(group & pressed for group in combo)

    def _combo_contains(combo, code: int) -> bool:
        """Check if a keycode belongs to any group in the combo."""
        return any(code in group for group in combo)

    def _find_keyboard_device() -> evdev.InputDevice:
        """Find the first keyboard device in /dev/input/event*."""
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        for dev in devices:
            caps = dev.capabilities()
            # EV_KEY = 1; look for KEY_SPACE and KEY_A as keyboard markers
            if 1 in caps:
                key_codes = set(caps[1])
                if e.KEY_SPACE in key_codes and e.KEY_A in key_codes:
                    return dev
        raise RuntimeError(
            "No keyboard device found in /dev/input/.\n"
            "Ensure your user is in the 'input' group:\n"
            "  sudo usermod -aG input $USER\n"
            "Then log out and back in."
        )

    def _run_linux():
        record_combo = _parse_combo_evdev(config.HOTKEY_RECORD)
        quit_combo = _parse_combo_evdev(config.HOTKEY_QUIT)
        pressed: set = set()

        dev = _find_keyboard_device()
        print(f"  Keyboard: {dev.name} ({dev.path})")

        _print_banner()

        try:
            for event in dev.read_loop():
                if event.type != e.EV_KEY:
                    continue

                key_event = evdev.categorize(event)
                code = key_event.scancode

                if key_event.keystate == evdev.KeyEvent.key_down:
                    pressed.add(code)

                    if _combo_active(quit_combo, pressed):
                        print("\nQuitting Voza. Goodbye!")
                        import os as _os; _os._exit(0)

                    if _combo_active(record_combo, pressed) and not recorder.is_recording:
                        if processing_lock.locked():
                            continue
                        recorder.start()
                        print("Recording... (release to stop)")

                elif key_event.keystate == evdev.KeyEvent.key_up:
                    if recorder.is_recording and _combo_contains(record_combo, code):
                        print("Processing...")
                        audio_buffer = recorder.stop()
                        pressed.discard(code)

                        if audio_buffer is None:
                            reason = recorder.last_stop_reason
                            if reason == "silent":
                                print("  Mic appears silent/dead. Check your input device.")
                                print("  Try: pavucontrol or alsamixer to check input levels, or restart the app.")
                            else:
                                print("  No audio captured (too short).")
                            print("Ready.")
                            continue

                        threading.Thread(
                            target=_process_audio, args=(audio_buffer,), daemon=True
                        ).start()
                    else:
                        pressed.discard(code)

        except KeyboardInterrupt:
            print("\nInterrupted. Goodbye!")
            sys.exit(0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    config.validate()
    _check_mic()

    if _IS_MACOS:
        _run_macos()
    else:
        _run_linux()


if __name__ == "__main__":
    main()
