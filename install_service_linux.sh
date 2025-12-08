#!/bin/bash
# Linux systemd Service Installation Script
# Installs the Lightroom Preset Auto-Processor as a systemd service

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="lightroom-preset-processor"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

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

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run as root (use sudo)"
    exit 1
fi

echo "Installing Lightroom Preset Auto-Processor as systemd service..."
echo "Script directory: $SCRIPT_DIR"

# Create systemd service file
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Lightroom Preset Auto-Processor
After=network.target

[Service]
Type=simple
User=$SUDO_USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$PYTHON_PATH $SCRIPT_DIR/main.py
Restart=always
RestartSec=10
StandardOutput=append:$SCRIPT_DIR/service_output.log
StandardError=append:$SCRIPT_DIR/service_error.log
Environment="PATH=/usr/local/bin:/usr/bin:/bin"

[Install]
WantedBy=multi-user.target
EOF

echo "Created systemd service file: $SERVICE_FILE"

# Reload systemd
systemctl daemon-reload

# Enable service to start on boot
systemctl enable "$SERVICE_NAME"

# Start the service
systemctl start "$SERVICE_NAME"

echo ""
echo "Service installed successfully!"
echo ""
echo "To check service status:"
echo "  sudo systemctl status $SERVICE_NAME"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "To stop the service:"
echo "  sudo systemctl stop $SERVICE_NAME"
echo ""
echo "To start the service:"
echo "  sudo systemctl start $SERVICE_NAME"
echo ""
echo "To disable auto-start on boot:"
echo "  sudo systemctl disable $SERVICE_NAME"
echo ""
echo "To remove the service:"
echo "  sudo systemctl stop $SERVICE_NAME"
echo "  sudo systemctl disable $SERVICE_NAME"
echo "  sudo rm $SERVICE_FILE"
echo "  sudo systemctl daemon-reload"
echo ""

