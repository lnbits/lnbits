#!/bin/bash
set -e

SPARK_MNEMONIC="$SPARK_MNEMONIC" \
SPARK_NETWORK="$SPARK_NETWORK" \
SPARK_SIDECAR_PORT="$SPARK_SIDECAR_PORT" \
SPARK_PAY_WAIT_MS=20000 \
node server.mjs

# Wait for startup
for i in {1..10}; do
  if nc -z localhost 8765; then
    echo "sparksidebar is up!"
    break
  fi
  echo "Waiting for sparksidebar to start..."
  sleep 1
done

# Optional: check if still not up
if ! nc -z localhost 8765; then
  echo "sparksidebar did not start successfully."
  exit 1
fi

echo "Starting LNbits on $LNBITS_HOST:$LNBITS_PORT..."
exec uv run lnbits --port "$LNBITS_PORT" --host "$LNBITS_HOST" --forwarded-allow-ips='*'
