---
layout: default
title: Super user
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

# LNbits Super User (SU)

**Table of Contents**

- [What is the Super User?](#what-is-the-super-user)
- [When is the Super User created?](#when-is-the-super-user-created)
- [Disabeling the Admin UI](#disabeling-the-admin-ui)
- [Super User identity and storage](#super-user-identity-and-storage)
- [Security model since v1](#security-model-since-v1)
- [Admin vs Super User](#admin-vs-super-user)
- [Operational guidance](#operational-guidance)
- [Additional guides](#additional-guides)

<details>
  <summary><strong>TLDR</strong></summary>

- **No Admin UI → No Super User.** The Super User (SU) exists only when `LNBITS_ADMIN_UI=true`.
- **Why SU exists:** SU can do a few high impact actions regular admins cannot, like **changing the funding source**, **restarting the server from the UI**, and **crediting or debiting accounts**.
- **Login changes since v1:** Logging in by **user ID** for SU and admins is **disabled**. On first visit after enabling the Admin UI you will be prompted to set a **username and password** for the SU.
- **Trust model:** Admins and the SU share about **99 percent of the same powers**, but the SU is the one trusted with funding source control and cannot be demoted by regular admins.

</details>

## What is the Super User?

The **Super User** is the owner-operator account of an LNbits instance. Think of it as your “break glass” operator with a few capabilities that are intentionally reserved for the person ultimately responsible for the server and the funding rails.

The SU is created alongside the [Admin UI](./admin_ui.md) and is meant to keep enviroment operations pleasant in the UI while keeping the most sensitive knobs in trusted hands.

**Key SU capabilities**

- **Change the funding source** for the instance
- **Restart the LNbits server** from the web UI
- **Credit or debit accounts** for operational corrections

> Note
> These are separated from regular admin tasks on purpose. It helps maintain least privilege and reduces the chance of accidental or malicious changes.

## Admin vs Super User

| Capability               | Admin      | Super User |
| ------------------------ | ---------- | ---------- |
| View Admin UI            | If enabled | If enabled |
| Change funding source    | —          | ✓          |
| Credit or debit accounts | —          | ✓          |
| Restart server from UI   | —          | ✓          |
| Manage users and wallets | ✓          | ✓          |
| Instance-level settings  | ✓          | ✓          |
| Manage notifications     | ✓          | ✓          |
| Exchange rates           | ✓          | ✓          |
| View all Payments        | ✓          | ✓          |

**Why both roles?**
In many teams the person running the server prefers to **delegate day-to-day admin work** while keeping funding and final authority safe. Admins can do almost everything; the SU retains the last few high risk powers.

## When is the Super User created?

- The SU is created **only** when you enable the Admin UI: `LNBITS_ADMIN_UI=true`.
- If the Admin UI is **disabled**, there is **no SU** and all SU-only UI is hidden.

## Disabeling the Admin UI

> [!IMPORTANT]
> Read the [Admin UI guide](./admin_ui.md) before Disabeling. You are turning on a management surface; do it deliberately.

Set the environment variable in your deployment:

```bash
# .env
LNBITS_ADMIN_UI=false
```

## Super User identity and storage

LNbits stores the **Super User ID** at:

```
/lnbits/data/.super_user
```

- Back this up along with the rest of `/lnbits/data` as part of your secure backup routine.
- **Changing who is the SU** can only be done by someone with **CLI access to the host OS** where LNbits runs. **Regular admins cannot revoke or replace the SU in the Admin UI.**

## Security model since v1

- **User-ID logins are disabled** for SU and admin roles.
- **Credentialed login is required:** set a **username and password** for the SU at first run of the Admin UI.
- **SU secrecy:** Regular users and admins **cannot discover the SU user ID** through normal UI flows.

## Operational guidance

These are practical tips for running a safe and friendly instance.

- It is normal to **delegate admin** duties to trusted people. Admins have about **99 percent** of SU powers for day-to-day work.
- Keep the **SU** reserved for the person legally or operationally responsible for the **funding source**.
- Use admin roles for regular day-to-day management and keep the SU for reserved SU tasks only.

## Additional guides

- **[Admin UI](./admin_ui.md)** — Manage server settings in the browser instead of editing `.env` or using the CLI for routine tasks.
- **[User Roles](./User_Roles.md)** — Overview of roles and what they can do.
- **[Funding sources](./funding-sources_table.md)** — Available options and how to enable and configure them.
- **[Install LNBits](./installation.md)** — Choose your prefared way to install LNBits.

## Powered by LNbits

LNbits empowers everyone with modular, open source tools for building Bitcoin-based systems — fast, free, and extendable.

If you like this project, [send some tip love](https://demo.lnbits.com/tipjar/DwaUiE4kBX6mUW6pj3X5Kg) or visit our [Shop](https://shop.lnbits.de)

[![LNbits Shop](https://demo.lnbits.com/static/images/bitcoin-shop-banner.png)](https://shop.lnbits.com/)
[![Visit LNbits Shop](https://img.shields.io/badge/Visit-LNbits%20Shop-7C3AED?logo=shopping-cart&logoColor=white&labelColor=5B21B6)](https://shop.lnbits.com/)
[![Try myLNbits SaaS](https://img.shields.io/badge/Try-myLNbits%20SaaS-2563EB?logo=lightning&logoColor=white&labelColor=1E40AF)](https://my.lnbits.com/login)
[![Read LNbits News](https://img.shields.io/badge/Read-LNbits%20News-F97316?logo=rss&logoColor=white&labelColor=C2410C)](https://news.lnbits.com/)
[![Explore LNbits Extensions](https://img.shields.io/badge/Explore-LNbits%20Extensions-10B981?logo=puzzle-piece&logoColor=white&labelColor=065F46)](https://extensions.lnbits.com/)
