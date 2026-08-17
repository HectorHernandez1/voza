#!/usr/bin/env python3
"""Voza — AI-powered voice-to-text dictation."""


import sys
import threading
import time

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
from enhancer import enhance, enhance_stream
from injector import inject, can_stream, StreamTyper


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

recorder = Recorder()
processing_lock = threading.Lock()

_PROCESS_START = time.monotonic()
# If a hang recurs within this many seconds of launch, don't loop forever: stop
# and let the user restart manually. A fresh process almost always clears it.
_MIN_UPTIME_BEFORE_RESTART = 30


def _restart_on_hang(reason):
    """Called when the audio device deadlocks mid-recording.

    CoreAudio keeps the mic open until the process dies, so exit and let the
    launch wrapper (start.sh / Voza.app) respawn a fresh instance."""
    import os as _os
    print("\n" + reason, flush=True)

    # The hang fires ~2s after the hotkey was released, so the just-recorded
    # dictation is usually still mid-transcription. Wait (bounded) for the
    # pipeline to finish pasting before killing the process.
    if processing_lock.acquire(timeout=30):
        processing_lock.release()
    else:
        print("In-flight dictation didn't finish in 30s; restarting anyway.",
              flush=True)

    if time.monotonic() - _PROCESS_START < _MIN_UPTIME_BEFORE_RESTART:
        print("Not auto-restarting (hang too soon after launch). "
              "Restart Voza manually.", flush=True)
        _os._exit(0)
    print("Restarting Voza...", flush=True)
    _os._exit(1)


recorder.on_hang = _restart_on_hang


# ---------------------------------------------------------------------------
# Mic verification
# ---------------------------------------------------------------------------

def _check_mic():
    """Record a short sample to verify the default mic is alive. Exit if dead."""
    print("  Checking microphone...", end=" ", flush=True)

    duration = 0.5  # half-second test
    # A silent read at login often means the audio stack is still coming up,
    # not a dead mic — retry a few times before giving up for good.
    attempts = 3
    peak = 0

    for attempt in range(attempts):
        result = {}

        def _record():
            try:
                audio = sd.rec(
                    int(config.SAMPLE_RATE * duration),
                    samplerate=config.SAMPLE_RATE,
                    channels=config.CHANNELS,
                    dtype="int16",
                    device=config.AUDIO_DEVICE,
                )
                sd.wait()
                result["audio"] = audio
            except Exception as exc:
                result["error"] = exc

        # Run the recording under a watchdog. A busy CoreAudio device (e.g. right
        # after another app released the mic, or a Continuity device waking up) can
        # make sd.wait() block forever — which would wedge startup before the
        # hotkey listener ever starts. If it doesn't finish in time, warn and move
        # on: config's auto-detect probe already confirmed the mic records.
        worker = threading.Thread(target=_record, daemon=True)
        worker.start()
        worker.join(timeout=duration + 3.0)

        if worker.is_alive():
            print("TIMED OUT")
            print("  WARNING: Microphone check timed out (audio device busy).")
            print("  Continuing anyway — if dictation produces no text, close other")
            print("  apps using the mic (or unplug/replug it) and restart.")
            try:
                sd.stop()
            except Exception:
                pass
            return

        if "error" in result:
            print(f"\n\n  ERROR: Could not access microphone: {result['error']}")
            print("  Please check that a microphone is connected and permissions are granted.")
            print("  Then restart the app.\n")
            # Exit 0: a restart won't fix a missing mic/permissions, and a non-zero
            # exit would make the launch wrapper respawn us in a loop.
            sys.exit(0)

        peak = int(np.max(np.abs(result["audio"])))
        if peak >= _SILENCE_THRESHOLD:
            break
        if attempt < attempts - 1:
            print(f"silent (peak={peak}), retrying...", end=" ", flush=True)
            time.sleep(1.0)

    if peak < _SILENCE_THRESHOLD:
        print(f"SILENT (peak={peak})")
        print()
        # Every device reading exactly 0 is the boot-race signature (a working
        # mic always has a nonzero noise floor, and a dead one still enumerates)
        # — the audio stack likely isn't up yet, so this WILL fix itself. Exit
        # non-zero so systemd's Restart=on-failure retries; the unit's
        # StartLimitBurst bounds the loop if the mic really is dead. Linux only:
        # the race is a systemd phenomenon, and on macOS a non-zero exit would
        # make the launch wrapper respawn forever on a truly muted mic.
        if not _IS_MACOS and config.PROBE_ALL_SILENT:
            print("  All input devices read zero — audio stack is likely still starting.")
            print("  Exiting with status 1 so the service manager retries shortly.")
            print()
            sys.exit(1)
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
        # Exit 0: a dead mic won't come back on its own, and a non-zero exit
        # would make the launch wrapper respawn us in a loop.
        sys.exit(0)
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

# Only treat a transcript as a hallucination when the recording was this long:
# a deliberate "Okay." takes ~1s, while silence-derived hallucinations come from
# longer holds. Below this, short answers like "yes"/"no" paste normally.
_HALLUCINATION_MIN_DURATION = 3.0


def _process_audio(audio_buffer, duration):
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

        # Guard against Whisper hallucinations from silent/bad audio: a lone
        # filler word out of a long recording means the audio was noise, but a
        # quick press saying "okay" is real dictation and must paste.
        stripped = raw_text.strip().strip(".!?,").lower()
        if stripped in _HALLUCINATION_WORDS and duration >= _HALLUCINATION_MIN_DURATION:
            print("  [Warning] Likely mic issue — transcript looks like a hallucination.")
            print("  Check your audio input device. Skipping paste.")
            print("Ready.")
            return

        # Short phrases don't need LLM cleanup — skip to save time
        # Higher threshold for local mode (Ollama is slower than GPT-4o-mini)
        skip_threshold = 20 if config.VOZA_MODE == "local" else 15
        if len(raw_text.split()) <= skip_threshold:
            print("  [Cleanup] Skipped (short phrase)")
            _paste(raw_text)
            print("Ready.")
            return

        # Streaming path: type cleaned text into the active app as it arrives
        if config.STREAM_OUTPUT and can_stream():
            typer = StreamTyper()
            try:
                for chunk in enhance_stream(raw_text):
                    typer.feed(chunk)
                typer.close()
            except Exception as exc:
                try:
                    typer.close()
                except Exception:
                    pass  # typing is already broken; keep the fallback path alive
                if typer.text:
                    print(f"Warning: Stream interrupted ({exc}). Partial text was typed.")
                    print(f"  Raw transcript was: {raw_text}")
                    print("Ready.")
                    return
                print(f"Warning: Cleanup failed ({exc}). Using raw transcript.")
                _paste(raw_text)
                print("Ready.")
                return

            if typer.text.strip():
                print(f"  [Typed] {typer.text}")
            else:
                # Model returned nothing — fall back to the raw transcript
                _paste(raw_text)
            print("Ready.")
            return

        # Non-streaming path: full cleanup, then one paste
        try:
            cleaned_text = enhance(raw_text)
        except Exception as exc:
            print(f"Warning: Cleanup failed ({exc}). Using raw transcript.")
            cleaned_text = raw_text

        _paste(cleaned_text)
        print("Ready.")


def _paste(text: str):
    """Inject text via clipboard + paste keystroke, logging the outcome."""
    try:
        inject(text)
        print(f"  [Pasted] {text}")
    except Exception as exc:
        print(f"Error: Failed to paste text: {exc}")
        print(f"  Text was: {text}")


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

    if config.STREAM_OUTPUT:
        stream_label = "On" if can_stream() else "Off (not supported on this setup)"
    else:
        stream_label = "Off (VOZA_STREAM=false)"
    print(f"  Stream:  {stream_label}")

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
                    target=_process_audio,
                    args=(audio_buffer, recorder.last_duration),
                    daemon=True,
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
        for path in evdev.list_devices():
            dev = evdev.InputDevice(path)
            caps = dev.capabilities()
            # EV_KEY = 1; look for KEY_SPACE and KEY_A as keyboard markers
            if 1 in caps:
                key_codes = set(caps[1])
                if e.KEY_SPACE in key_codes and e.KEY_A in key_codes:
                    return dev
            dev.close()
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
                            target=_process_audio,
                            args=(audio_buffer, recorder.last_duration),
                            daemon=True,
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
