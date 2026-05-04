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
    if not _HAS_WTYPE:
        raise RuntimeError("wtype not found. Install it:\n  sudo apt install wtype")

    subprocess.run(
        ["wl-copy"],
        input=text.encode("utf-8"),
        check=True,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(PASTE_DELAY)
    subprocess.run(["wtype", "-M", "ctrl", "-k", "v", "-m", "ctrl"], check=True, stderr=subprocess.DEVNULL)


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
