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
