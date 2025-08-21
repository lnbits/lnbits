#!/bin/bash
set -e

boltzd --standalone --referralId lnbits &

# Capture boltzd PID to monitor if needed
BOLTZ_PID=$!

# Wait for boltzd to start
for i in {1..10}; do
  if nc -z localhost 9002; then
    echo "boltzd is up!"
    break
  fi
  echo "Waiting for boltzd to start..."
  sleep 1
done

# Optional: check if still not up
if ! nc -z localhost 9002; then
  echo "boltzd did not start successfully."
  exit 1
fi

echo "Starting LNbits on $LNBITS_HOST:$LNBITS_PORT..."
exec uv run lnbits --port "$LNBITS_PORT" --host "$LNBITS_HOST" --forwarded-allow-ips='*'
