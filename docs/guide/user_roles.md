---
layout: default
title: User Roles
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

# LNbits Roles: A Quick Overview

### Understand **who can do what** in seconds: `Super User`, `Admin`, and `Regular User`.

**Jump to:**
[Roles at a Glance](#roles-at-a-glance) •
[Super User](#super-user--master-control) •
[Admin](#admin--day-to-day-manager) •
[Regular User](#regular-user--everyday-use) •
[Best Practices](#best-practices) •
[Additional Guides](#additional-guides)

---

## Roles at a Glance

| Capability                       | **Super User** (owner) | **Admin** (manager) | **Regular User** (end user) |
| -------------------------------- | :--------------------: | :-----------------: | :-------------------------: |
| Change **funding source**        |           ✅           |         ❌          |             ❌              |
| Credit/Debit any wallet          |           ✅           |         ❌          |             ❌              |
| Manage Admins & Users            |           ✅           |         ✅          |             ❌              |
| Enable/disable extensions        |           ✅           |         ✅          |             ❌              |
| Use wallets & allowed extensions |           ✅           |         ✅          |             ✅              |

> **Plain talk:** **Super User** = Owner • **Admin** = Trusted manager • **Regular User** = End user

## Role Snapshots

### Super User — Master Control

For initial setup and rare, high-impact changes.

- Configure **server-level settings** (e.g., funding source).
- **Credit/Debit** any wallet.
- Create and manage initial **Admin(s)**.

> **Sign-in:** username + password (v1+). The old query-string login is retired.

### Admin — Day-to-Day Manager

For running the service without touching the most sensitive knobs.

- Manage **Users**, **Admins**, and **Extensions** in the Admin UI.
- Adjust security-related settings (e.g., `rate_limiter`, `ip_blocker`).
- Handle operations settings (e.g., `service_fee`, `invoice_expiry`).
- Build brand design in **Site Customization**.
- Update user accounts.

**Typical tasks:** onboarding users, enabling extensions, tidying wallets, reviewing activity.

> **Sign-in:** username + password (v1+). The old query-string login is retired.

### Regular User — Everyday Use

For using LNbits, not administering it.

- Access **personal wallets** and **allowed extensions**.
- No server/admin privileges.

**Typical tasks:** receive and send payments, use enabled extensions.

## Best Practices

- **Minimize risk:** Reserve **Super User** for rare, sensitive actions (funding source, debit/credit). Use **Admin** for daily operations.
- **Keep access tidy:** Review your Admin list occasionally; remove unused accounts.
- **Change management:** Test risky changes (like funding) in a staging setup first.

## Additional Guides

- **[Admin UI](./admin_ui.md)** — Manage server settings via a clean UI (avoid editing `.env` by hand).
- **[Super User](./super_user.md)** — Deep dive on responsibilities and safe usage patterns.
- **[Funding sources](./funding-sources-table.md)** — What’s available and how to enable/configure each.

## Powered by LNbits

LNbits empowers everyone with modular, open-source tools for building Bitcoin-based systems—fast, free, and extendable.

If you like this project, [send some tip love](https://demo.lnbits.com/tipjar/DwaUiE4kBX6mUW6pj3X5Kg) or visit our [Shop](https://shop.lnbits.de)

[![LNbits Shop](https://demo.lnbits.com/static/images/bitcoin-shop-banner.png)](https://shop.lnbits.com/)
[![Visit LNbits Shop](https://img.shields.io/badge/Visit-LNbits%20Shop-7C3AED?logo=shopping-cart&logoColor=white&labelColor=5B21B6)](https://shop.lnbits.com/)
[![Try myLNbits SaaS](https://img.shields.io/badge/Try-myLNbits%20SaaS-2563EB?logo=lightning&logoColor=white&labelColor=1E40AF)](https://my.lnbits.com/login)
[![Read LNbits News](https://img.shields.io/badge/Read-LNbits%20News-F97316?logo=rss&logoColor=white&labelColor=C2410C)](https://news.lnbits.com/)
[![Explore LNbits Extensions](https://img.shields.io/badge/Explore-LNbits%20Extensions-10B981?logo=puzzle-piece&logoColor=white&labelColor=065F46)](https://extensions.lnbits.com/)
