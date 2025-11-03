---
layout: default
title: Wallet comparison
nav_order: 1
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

# Backend Wallet Comparison Table

LNbits lets you choose **how your wallets are funded** — from fully self-custodial nodes to simple hosted services. You can switch the funding source **without touching your apps, users, or extensions**. That means you can start fast, learn, and later upgrade to more control and privacy when you are ready.

**Why this matters**

- **Flexibility:** Pick the backend that fits your skills and constraints today, change it later with minimal friction.
- **Speed to ship:** Use a hosted option to get live quickly; move to a node when you need more control.
- **Scalability:** Match cost and maintenance to your stage — from hobby to production.
- **Privacy and compliance:** Choose between self-custody and provider-managed options depending on your requirements.

Below is a side-by-side comparison of Lightning funding sources you can use with LNbits.

> [!NOTE]
> “Backend Wallet” and “Funding Source” mean the same thing — the wallet or service that funds your LNbits.

## LNbits Lightning Network Funding Sources Comparison Table

| **Funding Source**             | **Custodial Type**       | **KYC Required**    | **Technical Knowledge Needed** | **Node Hosting Required** | **Privacy Level** | **Liquidity Management** | **Ease of Setup** | **Maintenance Effort** | **Cost Implications**                        | **Scalability** | **Notes**                                                                                  |
| ------------------------------ | ------------------------ | ------------------- | ------------------------------ | ------------------------- | ----------------- | ------------------------ | ----------------- | ---------------------- | -------------------------------------------- | --------------- | ------------------------------------------------------------------------------------------ |
| **LND (gRPC)**                 | Self-custodial           | ❌                  | Higher                         | ✅                        | High              | Manual                   | Moderate          | High                   | Infrastructure cost and channel opening fees | High            | gRPC interface for LND; suitable for advanced integrations.                                |
| **CoreLightning (CLN)**        | Self-custodial           | ❌                  | Higher                         | ✅                        | High              | Manual                   | Moderate          | High                   | Infrastructure cost and channel opening fees | High            | Requires setting up and managing your own CLN node.                                        |
| **Phoenixd**                   | Self-custodial           | ❌                  | Medium                         | ❌                        | Medium            | Automatic                | Moderate          | Low                    | Minimal fees                                 | Medium          | Mobile wallet backend; suitable for mobile integrations.                                   |
| **Nostr Wallet Connect (NWC)** | Custodial                | Depends on provider | Low                            | ❌                        | Variable          | Provider-managed         | Easy              | Low                    | May incur fees                               | Medium          | Connects via Nostr protocol; depends on provider's policies.                               |
| **Boltz**                      | Self-custodial           | ❌                  | Medium                         | ❌                        | Medium            | Provider-managed         | Moderate          | Moderate               | Minimal fees                                 | Medium          | Uses submarine swaps; connects to Boltz client.                                            |
| **LND (REST)**                 | Self-custodial           | ❌                  | Higher                         | ✅                        | High              | Manual                   | Moderate          | High                   | Infrastructure cost and channel opening fees | High            | REST interface for LND; suitable for web integrations.                                     |
| **CoreLightning REST**         | Self-custodial           | ❌                  | Higher                         | ✅                        | High              | Manual                   | Moderate          | High                   | Infrastructure cost and channel opening fees | High            | REST interface for CLN; suitable for web integrations.                                     |
| **LNbits (another instance)**  | Custodial                | Depends on host     | Low                            | ❌                        | Variable          | Provider-managed         | Easy              | Low                    | May incur hosting fees                       | Medium          | Connects to another LNbits instance; depends on host's policies.                           |
| **Alby**                       | Custodial                | ✅                  | Low                            | ❌                        | Low               | Provider-managed         | Easy              | Low                    | Transaction fees apply                       | Medium          | Browser extension wallet; suitable for web users.                                          |
| **Breez SDK**                  | Self-custodial           | ❌                  | Medium                         | ❌                        | High              | Automatic                | Moderate          | Low                    | Minimal fees                                 | Medium          | SDK for integrating Breez wallet functionalities.                                          |
| **OpenNode**                   | Custodial                | ✅                  | Low                            | ❌                        | Low               | Provider-managed         | Easy              | Low                    | Transaction fees apply                       | Medium          | Third-party service; suitable for merchants.                                               |
| **Blink**                      | Custodial                | ✅                  | Low                            | ❌                        | Low               | Provider-managed         | Easy              | Low                    | Transaction fees apply                       | Medium          | Third-party service; focuses on mobile integrations.                                       |
| **ZBD**                        | Custodial                | ✅                  | Low                            | ❌                        | Low               | Provider-managed         | Easy              | Low                    | Transaction fees apply                       | Medium          | Gaming-focused payment platform.                                                           |
| **Spark (CLN)**                | Self-custodial           | ❌                  | Higher                         | ✅                        | High              | Manual                   | Moderate          | High                   | Infrastructure cost and channel opening fees | High            | Web interface for CLN; requires Spark server setup.                                        |
| **Cliche Wallet**              | Self-custodial           | ❌                  | Medium                         | ❌                        | Medium            | Manual                   | Moderate          | Moderate               | Minimal fees                                 | Medium          | Lightweight wallet; suitable for embedded systems.                                         |
| **Strike**                     | Custodial                | ✅                  | Low                            | ❌                        | Low               | Provider-managed         | Easy              | Low                    | Transaction fees apply                       | Medium          | Third-party service; suitable for quick setups.                                            |
| **LNPay**                      | Custodial                | ✅                  | Low                            | ❌                        | Low               | Provider-managed         | Easy              | Low                    | Transaction fees apply                       | Medium          | Third-party service; suitable for quick setups.                                            |
| **Eclair (ACINQ)**             | Self-custodial           | ❌                  | Higher                         | ✅                        | High              | Manual                   | Moderate          | High                   | Infrastructure cost and channel opening fees | High            | Connects via API; you run and manage your Eclair node.                                     |
| **LN.tips**                    | Custodial/Self-Custodial | Depends on provider | Medium                         | ❌                        | Low               | Provider-managed         | Moderate          | Low                    | Transaction fees may apply                   | Medium          | Simple hosted service; use LN.tips API as your backend.                                    |
| **Fake Wallet**                | Testing (simulated)      | ❌                  | Low                            | ❌                        | N/A               | N/A                      | Easy              | Low                    | None (test only)                             | N/A             | For testing only; mints accounting units in LNbits (no real sats, unit name configurable). |

---

### Notes for readers

- These are typical characteristics; your exact experience may vary by configuration and provider policy.
- Pick based on your constraints: compliance (KYC), privacy, ops effort, and time-to-ship.

---

## Additional Guides

- **[Admin UI](./admin_ui.md)** — Manage server settings via a clean UI (avoid editing `.env` by hand).
- **[User Roles](./User_Roles.md)** — Quick Overview of existing Roles in LNBits.
- **[Funding sources](./funding-sources_table.md)** — What’s available and how to enable/configure each.

## Powered by LNbits

LNbits empowers everyone with modular, open-source tools for building Bitcoin-based systems — fast, free, and extendable.

If you like this project, [send some tip love](https://demo.lnbits.com/tipjar/DwaUiE4kBX6mUW6pj3X5Kg) or visit our [Shop](https://shop.lnbits.de)

[![LNbits Shop](https://demo.lnbits.com/static/images/bitcoin-shop-banner.png)](https://shop.lnbits.com/)
[![Visit LNbits Shop](https://img.shields.io/badge/Visit-LNbits%20Shop-7C3AED?logo=shopping-cart&logoColor=white&labelColor=5B21B6)](https://shop.lnbits.com/)
[![Try myLNbits SaaS](https://img.shields.io/badge/Try-myLNbits%20SaaS-2563EB?logo=lightning&logoColor=white&labelColor=1E40AF)](https://my.lnbits.com/login)
[![Read LNbits News](https://img.shields.io/badge/Read-LNbits%20News-F97316?logo=rss&logoColor=white&labelColor=C2410C)](https://news.lnbits.com/)
[![Explore LNbits Extensions](https://img.shields.io/badge/Explore-LNbits%20Extensions-10B981?logo=puzzle-piece&logoColor=white&labelColor=065F46)](https://extensions.lnbits.com/)
