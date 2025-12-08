#!/bin/bash
# macOS LaunchAgent Installation Script
# Installs the Lightroom Preset Auto-Processor as a LaunchAgent

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="com.lightroom.presetprocessor"
PLIST_FILE="$HOME/Library/LaunchAgents/${SERVICE_NAME}.plist"

# Check for virtual environment first, then system Python
if [ -f "$SCRIPT_DIR/venv/bin/python3" ]; then
    PYTHON_PATH="$SCRIPT_DIR/venv/bin/python3"
    echo "Using virtual environment Python: $PYTHON_PATH"
elif [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON_PATH="$SCRIPT_DIR/venv/bin/python"
    echo "Using virtual environment Python: $PYTHON_PATH"
else
    PYTHON_PATH=$(which python3)
    if [ -z "$PYTHON_PATH" ]; then
        echo "Error: python3 not found in PATH"
        echo "Please install Python 3.9 or later, or create a virtual environment:"
        echo "  python3 -m venv venv"
        exit 1
    fi
    echo "Using system Python: $PYTHON_PATH"
fi

echo "Installing Lightroom Preset Auto-Processor as LaunchAgent..."
echo "Script directory: $SCRIPT_DIR"

# Create LaunchAgents directory if it doesn't exist
mkdir -p "$HOME/Library/LaunchAgents"

# Create plist file
cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${SERVICE_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON_PATH}</string>
        <string>${SCRIPT_DIR}/main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${SCRIPT_DIR}/service_output.log</string>
    <key>StandardErrorPath</key>
    <string>${SCRIPT_DIR}/service_error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
EOF

echo "Created LaunchAgent plist: $PLIST_FILE"

# Load the service
# Check if service is already loaded (try multiple methods for compatibility)
SERVICE_LOADED=false
if launchctl list "$SERVICE_NAME" &>/dev/null 2>&1; then
    SERVICE_LOADED=true
elif launchctl list "gui/$(id -u)/$SERVICE_NAME" &>/dev/null 2>&1; then
    SERVICE_LOADED=true
fi

if [ "$SERVICE_LOADED" = true ]; then
    echo "Unloading existing service..."
    # Try modern bootout command first (macOS 10.11+)
    launchctl bootout "gui/$(id -u)/$SERVICE_NAME" 2>/dev/null || \
    launchctl bootout "user/$(id -u)/$SERVICE_NAME" 2>/dev/null || \
    # Fallback to legacy unload command (older macOS)
    launchctl unload "$PLIST_FILE" 2>/dev/null || true
    sleep 1  # Give it a moment to unload
fi

echo "Loading service..."
# Try modern bootstrap command first (macOS 10.11+)
if launchctl bootstrap "gui/$(id -u)" "$PLIST_FILE" 2>/dev/null; then
    echo "Service loaded using bootstrap (modern macOS)"
elif launchctl bootstrap "user/$(id -u)" "$PLIST_FILE" 2>/dev/null; then
    echo "Service loaded using bootstrap (user domain)"
else
    # Fallback to legacy load command (older macOS)
    launchctl load "$PLIST_FILE"
    echo "Service loaded using load (legacy macOS)"
fi

echo ""
echo "Service installed successfully!"
echo ""
echo "To check service status:"
echo "  launchctl list | grep $SERVICE_NAME"
echo ""
echo "To unload the service:"
echo "  launchctl bootout gui/\$(id -u)/$SERVICE_NAME"
echo "  # Or: launchctl bootout $SERVICE_NAME"
echo "  # Or (older macOS): launchctl unload $PLIST_FILE"
echo ""
echo "To remove the service:"
echo "  launchctl bootout gui/\$(id -u)/$SERVICE_NAME"
echo "  # Or: launchctl bootout $SERVICE_NAME"
echo "  # Or (older macOS): launchctl unload $PLIST_FILE"
echo "  rm $PLIST_FILE"
echo ""
echo "Logs are available at:"
echo "  ${SCRIPT_DIR}/service_output.log"
echo "  ${SCRIPT_DIR}/service_error.log"
echo "  ${SCRIPT_DIR}/preset_processor.log"

