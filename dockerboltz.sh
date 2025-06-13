#!/bin/bash

# Start boltzd in background
echo "Starting boltzd..."
boltzd --standalone &

# Wait for boltzd to come up
sleep 5

# Create Liquid wallet (if needed), capture mnemonic
echo "Creating Liquid wallet (lnbits)..."
MNEMONIC=$(yes N | boltzcli wallet create lnbits lbtc 2>&1 | awk '/Mnemonic:/ {getline; print}')
export BOLTZ_CLIENT_WALLET_MNEMONIC="$MNEMONIC"

# Show the mnemonic (for debug)
echo "Wallet mnemonic: $BOLTZ_CLIENT_WALLET_MNEMONIC"

# Start LNbits
echo "Starting LNbits..."
exec poetry run lnbits --port $LNBITS_PORT --host $LNBITS_HOST --forwarded-allow-ips='*'
