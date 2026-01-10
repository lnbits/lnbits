# Spark L2 sidecar

This sidecar exposes a small HTTP API for LNbits to talk to the Spark L2 SDK.

## Install

```
cd lnbits/wallets/sidecars/spark
npm install
```

## Run

```
SPARK_MNEMONIC="your seed phrase" \
SPARK_NETWORK=MAINNET \
SPARK_SIDECAR_PORT=8765 \
node server.mjs
```

Optional auth:

```
SPARK_SIDECAR_API_KEY="mykey"
```

Set the same key in LNbits as `SPARK_L2_API_KEY`.

## Endpoints

- `POST /v1/balance`
- `POST /v1/invoices`
- `POST /v1/payments`
- `GET /v1/invoices/{id}`
- `GET /v1/payments/{id}`
