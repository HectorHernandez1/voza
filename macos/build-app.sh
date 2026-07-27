#!/bin/bash
# Build Voza.app — a minimal macOS wrapper bundle so the app appears as
# "Voza" (not "python") in permission prompts and System Settings.
#
# The bundle launcher runs the venv Python as a child process and restarts
# it on crash (like start.sh). Launch the app via LaunchServices (`open`,
# Login Items, or the launchd agent below) so macOS attributes microphone
# and Accessibility permissions to Voza.app instead of the Python binary.
#
# Usage: ./macos/build-app.sh [install-dir]   (default: ~/Applications)

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_DIR="${1:-$HOME/Applications}"
APP="$INSTALL_DIR/Voza.app"

mkdir -p "$APP/Contents/MacOS"

cat > "$APP/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key>
    <string>com.voza.app</string>
    <key>CFBundleName</key>
    <string>Voza</string>
    <key>CFBundleDisplayName</key>
    <string>Voza</string>
    <key>CFBundleExecutable</key>
    <string>voza</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>LSUIElement</key>
    <true/>
    <key>NSMicrophoneUsageDescription</key>
    <string>Voza records your voice for dictation while you hold the push-to-talk hotkey.</string>
</dict>
</plist>
EOF

# Run script — auto-restarts on crash, stays quit after a clean exit.
cat > "$APP/Contents/MacOS/voza.sh" << EOF
#!/bin/bash
cd "$REPO_DIR"
mkdir -p "\$HOME/.voza"
while true; do
    "$REPO_DIR/.venv/bin/python" -u main.py >> "\$HOME/.voza/voza.log" 2>&1
    [ \$? -eq 0 ] && exit 0
    sleep 2
done
EOF
chmod +x "$APP/Contents/MacOS/voza.sh"

# LaunchServices refuses script main executables (error -10669), so the
# bundle entry point is a tiny Mach-O that execs the run script.
cat > /tmp/voza-launcher.c << 'EOF'
#include <mach-o/dyld.h>
#include <libgen.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

int main(void) {
    char exe[4096];
    uint32_t size = sizeof(exe);
    if (_NSGetExecutablePath(exe, &size) != 0) return 1;
    char script[4600];
    snprintf(script, sizeof(script), "%s.sh", exe);
    execl("/bin/bash", "bash", script, (char *)NULL);
    perror("execl");
    return 1;
}
EOF
clang -O2 -o "$APP/Contents/MacOS/voza" /tmp/voza-launcher.c
rm /tmp/voza-launcher.c

# Ad-hoc sign for a stable identity so granted permissions stick
codesign --force --deep -s - "$APP"

echo "Built $APP"
echo
echo "Start now:            open -g '$APP'"
echo "Start at login:       add Voza to System Settings > General > Login Items,"
echo "                      or use a launchd agent that runs: /usr/bin/open -g -a '$APP'"
echo "Grant permissions to 'Voza' (not python) when macOS prompts:"
echo "  System Settings > Privacy & Security > Microphone / Accessibility"
