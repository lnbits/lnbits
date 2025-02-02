#!/bin/sh

# Get the directory where the script is located
LAUNCH_DIR="$(dirname "$0")"

# Define persistent storage for extracted LNbits
PERSISTENT_DIR="$HOME/Library/Application Support/LNbits"

# Ensure the persistent directory exists
mkdir -p "$PERSISTENT_DIR/database"
mkdir -p "$PERSISTENT_DIR/extensions"

# Set environment variables
export LNBITS_DATA_FOLDER="$PERSISTENT_DIR/database"
export LNBITS_EXTENSIONS_PATH="$PERSISTENT_DIR/extensions"
export LNBITS_ADMIN_UI=true

# Define the LNbits binary path
LNBITS_BIN="$LAUNCH_DIR/lnbits/dist/lnbits"

# Ensure the binary is executable
if [ ! -x "$LNBITS_BIN" ]; then
    chmod +x "$LNBITS_BIN"
fi

# Define the LNbits URL
URL="http://0.0.0.0:5000"

# Start LNbits in the background
"$LNBITS_BIN" "$@" &
LNBITS_PID=$!

# Wait for LNbits to start
sleep 3

# Show GUI message using AppleScript
osascript -e 'display dialog "LNbits is running.\n\nClick OK to close it." buttons {"Close"} default button "Close"'

# Function to stop LNbits gracefully
kill_lnbits() {
    LN_PIDS=$(lsof -t -i:5000 2>/dev/null)
    if [ -n "$LN_PIDS" ]; then
        echo "Stopping LNbits (PIDs: $LN_PIDS)..."
        kill -2 $LN_PIDS  # Send SIGINT
    fi
}

# Stop LNbits when the dialog is closed
kill_lnbits

# Ensure LNbits fully stops
if ps -p $LNBITS_PID >/dev/null 2>&1; then
    wait $LNBITS_PID 2>/dev/null || true
fi
