#!/bin/sh

# Get the script directory
cd "$(dirname "$0")" || exit 1
LAUNCH_DIR="$(pwd)"

# Define persistent storage for LNbits
PERSISTENT_DIR="$HOME/Library/Application Support/LNbits"

# Ensure persistent directories exist
mkdir -p "$PERSISTENT_DIR/database"
mkdir -p "$PERSISTENT_DIR/extensions"

# Set environment variables
export LNBITS_DATA_FOLDER="$PERSISTENT_DIR/database"
export LNBITS_EXTENSIONS_PATH="$PERSISTENT_DIR/extensions"
export LNBITS_ADMIN_UI=true

# Define the LNbits binary path
LNBITS_BIN="$LAUNCH_DIR/lnbits/dist/lnbits"

# Ensure the binary exists and is executable
if [ ! -f "$LNBITS_BIN" ]; then
    echo "Error: LNbits binary not found at $LNBITS_BIN"
    exit 1
fi

chmod +x "$LNBITS_BIN"

# Default host and port
DEFAULT_HOST="0.0.0.0"
DEFAULT_PORT="5000"

# Check if --host or --port are provided in arguments
HOST_SET=false
PORT_SET=false

for arg in "$@"; do
    case $arg in
        --host)
            HOST_SET=true
            ;;
        --port)
            PORT_SET=true
            ;;
    esac
done

# Append default values if not provided
EXTRA_ARGS=""
if [ "$HOST_SET" = false ]; then
    EXTRA_ARGS="$EXTRA_ARGS --host $DEFAULT_HOST"
fi
if [ "$PORT_SET" = false ]; then
    EXTRA_ARGS="$EXTRA_ARGS --port $DEFAULT_PORT"
fi

# Start LNbits in the background
set -- "$LNBITS_BIN" $EXTRA_ARGS "$@"
"$@" &
LNBITS_PID=$!

# Wait for LNbits to start
sleep 3

# Show GUI message in the background to avoid blocking execution
osascript -e 'display dialog "LNbits is running.\n\n http://0.0.0.0:5000" buttons {"Close Server"} default button "Close Server"' &

# Function to stop LNbits gracefully
kill_lnbits() {
    echo "Stopping LNbits..."
    if [ -n "$LNBITS_PID" ] && ps -p "$LNBITS_PID" >/dev/null 2>&1; then
        kill -2 "$LNBITS_PID"
    fi
    pkill -f "lnbits" || killall lnbits || true
}

# Stop LNbits when the dialog is closed
wait $LNBITS_PID 2>/dev/null || kill_lnbits