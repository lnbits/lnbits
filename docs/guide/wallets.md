---
layout: default
title: Backend wallets
nav_order: 3
---


Backend wallets
===============

LNbits can run on top of many lightning-network funding sources. Currently there is support for
CLightning, LND, LNbits, LNPay, lntxbot and OpenNode, with more being added regularily.

A backend wallet can be configured using the following LNbits environment variables:


### CLightning

Using this wallet requires the installation of the `pylightning` Python package.

- `LNBITS_BACKEND_WALLET_CLASS`: **CLightningWallet**
- `CLIGHTNING_RPC`: /file/path/lightning-rpc

### Spark (c-lightning)

- `LNBITS_BACKEND_WALLET_CLASS`: **SparkWallet**
- `SPARK_URL`: http://10.147.17.230:9737/rpc
- `SPARK_TOKEN`: secret_access_key

### LND (gRPC)

Using this wallet requires the installation of the `lndgrpc` and `purerpc` Python packages.

- `LNBITS_BACKEND_WALLET_CLASS`: **LndWallet**
- `LND_GRPC_ENDPOINT`: ip_address
- `LND_GRPC_PORT`: port
- `LND_CERT`: /file/path/tls.cert
- `LND_ADMIN_MACAROON`: /file/path/admin.macaroon
- `LND_INVOICE_MACAROON`: /file/path/invoice.macaroon
- `LND_READ_MACAROON`: /file/path/read.macaroon


### LND (REST)

- `LNBITS_BACKEND_WALLET_CLASS`: **LndRestWallet**
- `LND_REST_ENDPOINT`: ip_address
- `LND_CERT`: /file/path/tls.cert
- `LND_ADMIN_MACAROON`: /file/path/admin.macaroon
- `LND_INVOICE_MACAROON`: /file/path/invoice.macaroon
- `LND_READ_MACAROON`: /file/path/read.macaroon


### LNbits

- `LNBITS_BACKEND_WALLET_CLASS`: **LNbitsWallet**
- `LNBITS_ENDPOINT`: e.g. https://lnbits.com
- `LNBITS_ADMIN_KEY`: apiKey
- `LNBITS_INVOICE_KEY`: apiKey


### LNPay

- `LNBITS_BACKEND_WALLET_CLASS`: **LNPayWallet**
- `LNPAY_API_ENDPOINT`: https://lnpay.co/v1/
- `LNPAY_API_KEY`: apiKey
- `LNPAY_ADMIN_KEY`: apiKey
- `LNPAY_INVOICE_KEY`: apiKey
- `LNPAY_READ_KEY`: apiKey


### lntxbot

- `LNBITS_BACKEND_WALLET_CLASS`: **LntxbotWallet**
- `LNTXBOT_API_ENDPOINT`: https://lntxbot.bigsun.xyz/
- `LNTXBOT_ADMIN_KEY`: apiKey
- `LNTXBOT_INVOICE_KEY`: apiKey


### OpenNode

- `LNBITS_BACKEND_WALLET_CLASS`: **OpenNodeWallet**
- `OPENNODE_API_ENDPOINT`: https://api.opennode.com/
- `OPENNODE_ADMIN_KEY`: apiKey
- `OPENNODE_INVOICE_KEY`: apiKey
