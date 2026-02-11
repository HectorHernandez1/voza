import subprocess
import time

from config import PASTE_DELAY


def inject(text: str):
    """Copy text to the macOS clipboard and simulate Cmd+V to paste."""
    # Copy to clipboard via pbcopy
    proc = subprocess.run(
        ["pbcopy"],
        input=text.encode("utf-8"),
        check=True,
    )

    # Wait for the previously focused app to be ready
    time.sleep(PASTE_DELAY)

    # Simulate Cmd+V via osascript
    subprocess.run(
        [
            "osascript",
            "-e",
            'tell application "System Events" to keystroke "v" using command down',
        ],
        check=True,
    )
