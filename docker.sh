#!/bin/bash

# Start boltzd in background
echo "Starting boltzd..."
boltzd --standalone &

# Wait for boltzd to come up
sleep 5

# Start LNbits
echo "Starting LNbits..."
exec poetry run lnbits --port $LNBITS_PORT --host $LNBITS_HOST --forwarded-allow-ips='*'
