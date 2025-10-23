---
layout: default
title: Backend wallets
nav_order: 3
---

<a href="https://lnbits.com" target="_blank" rel="noopener noreferrer">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://i.imgur.com/QE6SIrs.png">
    <img src="https://i.imgur.com/fyKPgVT.png" alt="LNbits" style="width:300px">
  </picture>
</a>

![phase: stable](https://img.shields.io/badge/phase-stable-2EA043)
![PRs: welcome](https://img.shields.io/badge/PRs-Welcome-yellow)
[<img src="https://img.shields.io/badge/community_chat-Telegram-24A1DE">](https://t.me/lnbits)
[<img src="https://img.shields.io/badge/supported_by-%3E__OpenSats-f97316">](https://opensats.org)

# Backend wallets

**LNbits is modular**: You can switch the funding source (backend wallet) **without changing anything else** in your setup. Keep your extensions, apps, users, and config as-is — just point LNbits to a different backend via environment variables.

**What stays the same when you switch backends**

- Your LNbits setup and extensions
- Your API keys and endpoints
- Your server and deployment setup

A backend wallet is selected and configured entirely through LNbits environment variables. See the options and variables below, and compare them here: [Funding-Source-Table.md](funding-sources-table.md)

> [!NOTE]
> **Terminology:** “Backend Wallet” and “Funding Source” mean the same thing — the wallet or service that funds your LNbits.

## Funding Sources

## Funding Sources

|                                                 |                                       |                                                   |
| ----------------------------------------------- | ------------------------------------- | ------------------------------------------------- |
| [CLNRest (runes)](#clnrest-runes)               | [LND (REST)](#lnd-rest)               | [OpenNode](#opennode)                             |
| [CoreLightning](#corelightning)                 | [LND (gRPC)](#lnd-grpc)               | [Blink](#blink)                                   |
| [CoreLightning REST](#corelightning-rest)       | [LNbits](#lnbits)                     | [Alby](#alby)                                     |
| [Spark (Core Lightning)](#spark-core-lightning) | [LNPay](#lnpay)                       | [Boltz](#boltz)                                   |
| [Cliche Wallet](#cliche-wallet)                 | [ZBD](#zbd)                           | [Phoenixd](#phoenixd)                             |
| [Breez SDK](#breez-sdk)                         | [Breez Liquid SDK](#breez-liquid-sdk) | [Nostr Wallet Connect](#nostr-wallet-connect-nwc) |
| [Strike](#strike)                               | [Eclair (ACINQ)](#eclair-acinq)       | [LN.tips](#lntips)                                |
| [Fake Wallet](#fake-wallet)                     |                                       |                                                   |

---

<a id="clnrest-runes"></a>

### CLNRest (using [runes](https://docs.corelightning.org/reference/lightning-createrune))

[Core Lightning REST API docs](https://docs.corelightning.org/docs/rest)  
Should also work with the [Rust version of CLNRest](https://github.com/daywalker90/clnrest-rs)

**Environment variables**

- `LNBITS_BACKEND_WALLET_CLASS`: `CLNRestWallet`
- `CLNREST_URL`: `https://127.0.0.1:3010`
- `CLNREST_CA`: `/home/lightningd/.lightning/bitcoin/ca.pem` (or the content of the file)
- `CLNREST_CERT`: `/home/lightningd/.lightning/bitcoin/server.pem` (or the content of the file)
- `CLNREST_LAST_PAY_INDEX`: `lightning-cli listinvoices | jq -r '.invoices | map(.created_index) | max'`
- `CLNREST_NODEID`: `lightning-cli getinfo | jq -r .id` (only required for v23.08)

**Create runes (copy/paste)**

```bash
# Read-only: funds, pays, invoices, info, summary, and invoice listener
lightning-cli createrune \
  restrictions='[["method=listfunds","method=listpays","method=listinvoices","method=getinfo","method=summary","method=waitanyinvoice"]]' \
| jq -r .rune
```

```bash
# Invoice: max 1,000,001 msat, label must start with "LNbits", 60 req/min
lightning-cli createrune \
  restrictions='[["method=invoice"], ["pnameamount_msat<1000001"], ["pnamelabel^LNbits"], ["rate=60"]]' \
| jq -r .rune
```

```bash
# Pay: bolt11 amount < 1001 (msat), label must start with "LNbits", 1 req/min
lightning-cli createrune \
  restrictions='[["method=pay"], ["pinvbolt11_amount<1001"], ["pnamelabel^LNbits"], ["rate=1"]]' \
| jq -r .rune
```

```bash
# Renepay: invstring amount < 1001 (msat), label must start with "LNbits", 1 req/min
lightning-cli createrune \
  restrictions='[["method=renepay"], ["pinvinvstring_amount<1001"], ["pnamelabel^LNbits"], ["rate=1"]]' \
| jq -r .rune
```

Set the resulting values into:

- `CLNREST_READONLY_RUNE`
- `CLNREST_INVOICE_RUNE`
- `CLNREST_PAY_RUNE`
- `CLNREST_RENEPAY_RUNE`

## CoreLightning

**Required env vars**

- `LNBITS_BACKEND_WALLET_CLASS`: `CoreLightningWallet`
- `CORELIGHTNING_RPC`: `/file/path/lightning-rpc`

## CoreLightning REST

Old REST interface using [RTL c-lightning-REST](https://github.com/Ride-The-Lightning/c-lightning-REST)

**Required env vars**

- `LNBITS_BACKEND_WALLET_CLASS`: `CoreLightningRestWallet`
- `CORELIGHTNING_REST_URL`: `http://127.0.0.1:8185/`
- `CORELIGHTNING_REST_MACAROON`: `/file/path/admin.macaroon` or Base64/Hex
- `CORELIGHTNING_REST_CERT`: `/home/lightning/clnrest/tls.cert`

## Spark (Core Lightning)

**Required env vars**

- `LNBITS_BACKEND_WALLET_CLASS`: `SparkWallet`
- `SPARK_URL`: `http://10.147.17.230:9737/rpc`
- `SPARK_TOKEN`: `secret_access_key`

## LND (REST)

**Required env vars**

- `LNBITS_BACKEND_WALLET_CLASS`: `LndRestWallet`
- `LND_REST_ENDPOINT`: `http://10.147.17.230:8080/`
- `LND_REST_CERT`: `/file/path/tls.cert`
- `LND_REST_MACAROON`: `/file/path/admin.macaroon` or Base64/Hex

or:

- `LND_REST_MACAROON_ENCRYPTED`: `eNcRyPtEdMaCaRoOn`

## LND (gRPC)

**Required env vars**

- `LNBITS_BACKEND_WALLET_CLASS`: `LndWallet`
- `LND_GRPC_ENDPOINT`: `ip_address`
- `LND_GRPC_PORT`: `port`
- `LND_GRPC_CERT`: `/file/path/tls.cert`
- `LND_GRPC_MACAROON`: `/file/path/admin.macaroon` or Base64/Hex

You can also use an AES-encrypted macaroon instead:

- `LND_GRPC_MACAROON_ENCRYPTED`: `eNcRyPtEdMaCaRoOn`

To encrypt your macaroon:

```bash
uv run lnbits-cli encrypt macaroon
```

## LNbits

**Required env vars**

- `LNBITS_BACKEND_WALLET_CLASS`: `LNbitsWallet`
- `LNBITS_ENDPOINT`: for example `https://lnbits.com`
- `LNBITS_KEY`: `lnbitsAdminKey`

## LNPay

For the invoice listener to work you must have a publicly accessible URL in your LNbits and set up [LNPay webhooks](https://dashboard.lnpay.co/webhook/) pointing to `<your LNbits host>/wallet/webhook` with the event **Wallet Receive** and no secret. Example: [https://mylnbits/wallet/webhook](`https://mylnbits/wallet/webhook).

**Required env vars**

- `LNBITS_BACKEND_WALLET_CLASS`: `LNPayWallet`
- `LNPAY_API_ENDPOINT`: `https://api.lnpay.co/v1/`
- `LNPAY_API_KEY`: `sak_apiKey`
- `LNPAY_WALLET_KEY`: `waka_apiKey`

## OpenNode

For the invoice to work you must have a publicly accessible URL in your LNbits. No manual webhook configuration required.

**Required env vars**

- `LNBITS_BACKEND_WALLET_CLASS`: `OpenNodeWallet`
- `OPENNODE_API_ENDPOINT`: `https://api.opennode.com/`
- `OPENNODE_KEY`: `opennodeAdminApiKey`

## Blink

For the invoice to work you must have a publicly accessible URL in your LNbits. No manual webhook configuration required.

You can generate a Blink API key at [https://dashboard.blink.sv](https://dashboard.blink.sv). More info: [https://dev.blink.sv/api/auth#create-an-api-key](https://dev.blink.sv/api/auth#create-an-api-key)

**Required env vars**

- `LNBITS_BACKEND_WALLET_CLASS`: `BlinkWallet`
- `BLINK_API_ENDPOINT`: `https://api.blink.sv/graphql`
- `BLINK_WS_ENDPOINT`: `wss://ws.blink.sv/graphql`
- `BLINK_TOKEN`: `BlinkToken`

## Alby

For the invoice to work you must have a publicly accessible URL in your LNbits. No manual webhook configuration required.

Generate an Alby access token here: [https://getalby.com/developer/access_tokens/new](https://getalby.com/developer/access_tokens/new)

**Required env vars**

- `LNBITS_BACKEND_WALLET_CLASS`: `AlbyWallet`
- `ALBY_API_ENDPOINT`: `https://api.getalby.com/`
- `ALBY_ACCESS_TOKEN`: `AlbyAccessToken`

## Boltz

This connects to a running [boltz-client](https://docs.boltz.exchange/v/boltz-client) and handles Lightning payments through submarine swaps on the Liquid network.

You can run the daemon in standalone mode via `standalone = True` in the config or `boltzd --standalone`. Create a Liquid wallet with:

```bash
boltzcli wallet create lnbits lbtc
```

**Required env vars**

- `LNBITS_BACKEND_WALLET_CLASS`: `BoltzWallet`
- `BOLTZ_CLIENT_ENDPOINT`: `127.0.0.1:9002`
- `BOLTZ_CLIENT_MACAROON`: `/home/bob/.boltz/macaroons/admin.macaroon` or Base64/Hex
- `BOLTZ_CLIENT_CERT`: `/home/bob/.boltz/tls.cert` or Base64/Hex
- `BOLTZ_CLIENT_WALLET`: `lnbits`

## ZBD

For the invoice to work you must have a publicly accessible URL in your LNbits. No manual webhook configuration required.

Generate a ZBD API key here: [https://zbd.dev/docs/dashboard/projects/api](https://zbd.dev/docs/dashboard/projects/api)

**Required env vars**

- `LNBITS_BACKEND_WALLET_CLASS`: `ZBDWallet`
- `ZBD_API_ENDPOINT`: `https://api.zebedee.io/v0/`
- `ZBD_API_KEY`: `ZBDApiKey`

## Phoenixd

For the invoice to work you must have a publicly accessible URL in your LNbits.

You can get a phoenixd API key from `~/.phoenix/phoenix.conf`. See the phoenixd documentation for details.

**Required env vars**

- `LNBITS_BACKEND_WALLET_CLASS`: `PhoenixdWallet`
- `PHOENIXD_API_ENDPOINT`: `http://localhost:9740/`
- `PHOENIXD_API_PASSWORD`: `PhoenixdApiPassword`

## Eclair (ACINQ)

<a id="eclair-acinq"></a>

Connect to an existing Eclair node so your backend handles invoices and payments.

**Required env vars**

- `LNBITS_BACKEND_WALLET_CLASS`: `EclairWallet`
- `ECLAIR_URL`: `http://127.0.0.1:8283`
- `ECLAIR_PASSWORD`: `eclairpw`

## Fake Wallet

<a id="fake-wallet"></a>

A testing-only backend that mints accounting units inside LNbits accounting (no real sats).

**Required env vars**

- `LNBITS_BACKEND_WALLET_CLASS`: `FakeWallet`
- `FAKE_SECRET`: `ToTheMoon1`
- `FAKE_UNIT`: `sats`

## LN.tips

<a id="lntips"></a>

As the initinal LN.tips bot is no longer active the code still exists and is widly used. Connect one of custodial services as your backend to create and pay Lightning invoices through their API or selfhost this service and run it as funding source.
Resources: https://github.com/massmux/SatsMobiBot

**Required env vars**

- `LNBITS_BACKEND_WALLET_CLASS`: `LNTipsWallet`
- `LNTIPS_API_ENDPOINT`: `https://ln.tips`
- `LNTIPS_API_KEY`: `LNTIPS_ADMIN_KEY`

## Breez SDK

A Greenlight invite code or Greenlight partner certificate/key can register a new node with Greenlight. If the Greenlight node already exists, neither is required.

**Required env vars**

- `LNBITS_BACKEND_WALLET_CLASS`: `BreezSdkWallet`
- `BREEZ_API_KEY`: `...`
- `BREEZ_GREENLIGHT_SEED`: `...`
- `BREEZ_GREENLIGHT_INVITE_CODE`: `...`
- `BREEZ_GREENLIGHT_DEVICE_KEY`: `/path/to/breezsdk/device.pem` or Base64/Hex
- `BREEZ_GREENLIGHT_DEVICE_CERT`: `/path/to/breezsdk/device.crt` or Base64/Hex

## Breez Liquid SDK

This uses the [Breez SDK - Liquid](https://sdk-doc-liquid.breez.technology/) to manage Lightning payments via submarine swaps on the Liquid network. Provide a mnemonic seed phrase (for example, generate one with a Liquid wallet like [Blockstream Green](https://blockstream.com/green/)) and set it in the environment or admin UI.

**Required env vars**

- `LNBITS_BACKEND_WALLET_CLASS`: `BreezLiquidSdkWallet`
- `BREEZ_LIQUID_SEED`: `...`

Fees apply for each submarine swap. You may need to increase the reserve fee under **Settings → Funding** or via:

- `LNBITS_RESERVE_FEE_MIN`: `...`
- `LNBITS_RESERVE_FEE_PERCENT`: `...`

## Cliche Wallet

**Required env vars**

- `CLICHE_ENDPOINT`: `ws://127.0.0.1:12000`

## Nostr Wallet Connect (NWC)

To use NWC as a funding source you need a pairing URL (pairing secret) from an NWC provider. See providers here:
[https://github.com/getAlby/awesome-nwc?tab=readme-ov-file#nwc-wallets](https://github.com/getAlby/awesome-nwc?tab=readme-ov-file#nwc-wallets)

Configure in the admin UI or via env vars:

- `LNBITS_BACKEND_WALLET_CLASS`: `NWCWallet`
- `NWC_PAIRING_URL`: `nostr+walletconnect://...your...pairing...secret...`

<a id="strike"></a>

## Strike (alpha)

Custodial provider integrated via **Strike OAuth Connect** (OAuth 2.0 / OIDC). Authenticate a Strike user in your app, then call Strike APIs on the user’s behalf once scopes are granted. Requires a Strike business account, registered OAuth client, minimal scopes, and login/logout redirect URLs.

Get more info here [https://docs.strike.me/strike-oauth-connect/](https://docs.strike.me/strike-oauth-connect/)

**Integration endpoints**

- `STRIKE_API_ENDPOINT`: `https://api.strike.me/v1`
- `STRIKE_API_KEY`: `YOUR_STRIKE_API_KEY`

---

## Additional Guides

- **[Admin UI](./admin_ui.md)** — Manage server settings via a clean UI (avoid editing `.env` by hand).
- **[User Roles](./user_roles.md)** — Quick Overview of existing Roles in LNBits.
- **[Funding sources](./funding-sources-table.md)** — What’s available and how to enable/configure each.

## Powered by LNbits

LNbits empowers everyone with modular, open-source tools for building Bitcoin-based systems — fast, free, and extendable.

If you like this project, [send some tip love](https://demo.lnbits.com/tipjar/DwaUiE4kBX6mUW6pj3X5Kg) or visit our [Shop](https://shop.lnbits.de)

[![LNbits Shop](https://demo.lnbits.com/static/images/bitcoin-shop-banner.png)](https://shop.lnbits.com/)
[![Visit LNbits Shop](https://img.shields.io/badge/Visit-LNbits%20Shop-7C3AED?logo=shopping-cart&logoColor=white&labelColor=5B21B6)](https://shop.lnbits.com/)
[![Try myLNbits SaaS](https://img.shields.io/badge/Try-myLNbits%20SaaS-2563EB?logo=lightning&logoColor=white&labelColor=1E40AF)](https://my.lnbits.com/login)
[![Read LNbits News](https://img.shields.io/badge/Read-LNbits%20News-F97316?logo=rss&logoColor=white&labelColor=C2410C)](https://news.lnbits.com/)
[![Explore LNbits Extensions](https://img.shields.io/badge/Explore-LNbits%20Extensions-10B981?logo=puzzle-piece&logoColor=white&labelColor=065F46)](https://extensions.lnbits.com/)
