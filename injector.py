import shutil
import subprocess
import sys
import time

from config import PASTE_DELAY

_IS_MACOS = sys.platform == "darwin"

# Resolve Linux Wayland tools at import time
if not _IS_MACOS:
    _HAS_WL_COPY = shutil.which("wl-copy") is not None
    _HAS_YDOTOOL = shutil.which("ydotool") is not None


def inject(text: str):
    """Copy text to clipboard and simulate paste keystroke."""
    if _IS_MACOS:
        _inject_macos(text)
    else:
        _inject_linux(text)


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
    if not _HAS_WL_COPY:
        raise RuntimeError(
            "wl-copy not found. Install it:\n"
            "  sudo apt install wl-clipboard"
        )
    if not _HAS_YDOTOOL:
        raise RuntimeError(
            "ydotool not found. Install it:\n"
            "  sudo apt install ydotool\n"
            "  sudo ydotoold &"
        )

    subprocess.run(
        ["wl-copy"],
        input=text.encode("utf-8"),
        check=True,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(PASTE_DELAY)
    subprocess.run(
        ["ydotool", "key", "ctrl+v"],
        check=True,
        stderr=subprocess.DEVNULL,
    )
