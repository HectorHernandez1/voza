import shutil
import subprocess
import sys
import time

from config import PASTE_DELAY

_IS_MACOS = sys.platform == "darwin"

# Resolve Linux clipboard/paste tools at import time
if not _IS_MACOS:
    if shutil.which("xclip"):
        _CLIP_CMD = ["xclip", "-selection", "clipboard"]
    elif shutil.which("xsel"):
        _CLIP_CMD = ["xsel", "--clipboard", "--input"]
    else:
        _CLIP_CMD = None

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
    if _CLIP_CMD is None:
        raise RuntimeError(
            "No clipboard tool found. Install one:\n"
            "  sudo apt install xclip   (or xsel)"
        )
    if not _HAS_XDOTOOL:
        raise RuntimeError(
            "xdotool not found. Install it:\n"
            "  sudo apt install xdotool"
        )

    subprocess.run(
        _CLIP_CMD,
        input=text.encode("utf-8"),
        check=True,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(PASTE_DELAY)
    subprocess.run(
        ["xdotool", "key", "--clearmodifiers", "ctrl+v"],
        check=True,
        stderr=subprocess.DEVNULL,
    )
