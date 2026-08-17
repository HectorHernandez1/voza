import os
import shutil
import subprocess
import sys
import time

from config import PASTE_DELAY

_IS_MACOS = sys.platform == "darwin"

if not _IS_MACOS:
    _IS_WAYLAND = os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
    _HAS_WL_COPY = shutil.which("wl-copy") is not None
    _HAS_WTYPE = shutil.which("wtype") is not None
    _HAS_XCLIP = shutil.which("xclip") is not None
    _HAS_XDOTOOL = shutil.which("xdotool") is not None


def inject(text: str):
    """Copy text to clipboard and simulate paste keystroke."""
    if _IS_MACOS:
        _inject_macos(text)
    else:
        _inject_linux(text)


def can_stream() -> bool:
    """Whether this platform can type text incrementally (streaming output).

    Wayland needs wtype — uinput alone can't produce arbitrary Unicode.
    """
    if _IS_MACOS:
        return True
    if _IS_WAYLAND:
        return _HAS_WTYPE
    return _HAS_XDOTOOL


# Buffer streamed deltas until this many chars before typing a batch, so we
# don't spawn one typing subprocess per token.
_STREAM_FLUSH_AT = 24


class StreamTyper:
    """Types streamed text chunks into the focused app as they arrive.

    feed() buffers deltas and flushes on word boundaries; close() flushes
    whatever remains. `text` holds everything typed so far, so callers can
    recover from a stream that dies partway through.
    """

    def __init__(self):
        self.text = ""
        self._buffer = ""
        self._first = True

    def feed(self, chunk: str):
        self._buffer += chunk
        if len(self._buffer) < _STREAM_FLUSH_AT:
            return
        cut = max(self._buffer.rfind(" "), self._buffer.rfind("\n"))
        if cut == -1:
            cut = len(self._buffer) - 1
        self._type(self._buffer[:cut + 1])
        self._buffer = self._buffer[cut + 1:]

    def close(self):
        # Clear the buffer before typing: if _type fails partway, a second
        # close() (e.g. from an error handler) must not retype the same text.
        pending, self._buffer = self._buffer, ""
        if pending:
            self._type(pending)

    def _type(self, text: str):
        if self._first:
            time.sleep(PASTE_DELAY)  # let hotkey modifiers settle
            self._first = False
        _type_text(text)
        self.text += text


def _type_text(text: str):
    if _IS_MACOS:
        _type_macos(text)
    elif _IS_WAYLAND:
        subprocess.run(
            ["wtype", "-"],
            input=text.encode("utf-8"),
            check=True,
            stderr=subprocess.DEVNULL,
        )
    else:
        subprocess.run(
            ["xdotool", "type", "--clearmodifiers", "--delay", "1", "--file", "-"],
            input=text.encode("utf-8"),
            check=True,
            stderr=subprocess.DEVNULL,
        )


def _type_macos(text: str):
    # keystroke can't type a linefeed from a string — send Return between lines
    for i, line in enumerate(text.split("\n")):
        if i > 0:
            subprocess.run(
                ["osascript", "-e", 'tell application "System Events" to key code 36'],
                check=True,
                stderr=subprocess.DEVNULL,
            )
        if line:
            subprocess.run(
                [
                    "osascript",
                    "-e", "on run argv",
                    "-e", 'tell application "System Events" to keystroke (item 1 of argv)',
                    "-e", "end run",
                    line,
                ],
                check=True,
                stderr=subprocess.DEVNULL,
            )


def _inject_macos(text: str):
    subprocess.run(
        ["pbcopy"],
        input=text.encode("utf-8"),
        check=True,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(PASTE_DELAY)
    subprocess.run(
        [
            "osascript",
            "-e",
            'tell application "System Events" to keystroke "v" using command down',
        ],
        check=True,
        stderr=subprocess.DEVNULL,
    )


def _inject_linux(text: str):
    if _IS_WAYLAND:
        _inject_linux_wayland(text)
    else:
        _inject_linux_x11(text)


def _inject_linux_wayland(text: str):
    if not _HAS_WL_COPY:
        raise RuntimeError("wl-copy not found. Install it:\n  sudo apt install wl-clipboard")

    subprocess.run(
        ["wl-copy"],
        input=text.encode("utf-8"),
        check=True,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(PASTE_DELAY)
    _send_ctrl_v_uinput()


def _send_ctrl_v_uinput():
    from evdev import UInput, ecodes as e

    capabilities = {e.EV_KEY: [e.KEY_LEFTCTRL, e.KEY_V]}
    ui = UInput(capabilities, name="voza-virtual-kbd")
    try:
        time.sleep(0.05)
        ui.write(e.EV_KEY, e.KEY_LEFTCTRL, 1)
        ui.write(e.EV_KEY, e.KEY_V, 1)
        ui.syn()
        time.sleep(0.02)
        ui.write(e.EV_KEY, e.KEY_V, 0)
        ui.write(e.EV_KEY, e.KEY_LEFTCTRL, 0)
        ui.syn()
        time.sleep(0.02)
    finally:
        ui.close()


def _inject_linux_x11(text: str):
    if not _HAS_XCLIP:
        raise RuntimeError("xclip not found. Install it:\n  sudo apt install xclip")
    if not _HAS_XDOTOOL:
        raise RuntimeError("xdotool not found. Install it:\n  sudo apt install xdotool")

    subprocess.run(
        ["xclip", "-selection", "clipboard"],
        input=text.encode("utf-8"),
        check=True,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(PASTE_DELAY)
    subprocess.run(["xdotool", "key", "ctrl+v"], check=True, stderr=subprocess.DEVNULL)
