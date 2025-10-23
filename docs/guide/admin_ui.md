---
layout: default
title: Admin UI
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

# LNBits Admin UI

[What you can do](#what-you-can-do-with-the-admin-ui) · [First Run](#first-run-and-super-user-id) · [Enable/Disable](#enabling-or-disabling-the-admin-ui) · [Reset](#reset-to-defaults) · [Allowed Users](#allowed-users) · [Guides](#additional-guides)

**We introduced the Admin UI as the new default to make setup simpler and more straightforward**. Instead of hand editing the `.env` file, you configure key server settings directly in the frontend with clear labels and guardrails.

<ins>On a fresh install the Admin UI is enabled by default</ins>, and at first launch you are prompted to create **Super User** credentials so that sensitive operations, such as switching funding sources, remain in trusted hands. When the Admin UI is enabled, configuration is written to and read from the database; for all settings managed by the UI, the parameters in `.env` are largely no longer used. If you disable the Admin UI, the `.env` file becomes the single source of truth again.

For privileged actions and role details see **[Super User](./super_user.md)** & [User Roles](./user_roles.md)
For a complete reference of legacy variables consult **[.env.example](../../.env.example)**.

<img width="900" height="640" alt="grafik" src="https://github.com/user-attachments/assets/d8852b4b-21be-446f-a1e7-d3eb794d3505" />

> [!WARNING]
> Some settings remain `.env` only. Use **[.env.example](../../.env.example#L3-L87)** as the authoritative reference for those variables.

## What you can do with the Admin UI

- Switch funding sources and other server level settings
- Manage who can access LNbits (**[Allowed Users](#allowed-users)**)
- Promote or demote Admin Users
- Gate extensions to Admins only or disable them globally
- Adjust balances with credit or debit
- Adjust site customization

> [!NOTE]
> See **[Super User](./super_user.md)** for the role and permission differences compared to Admin Users.

## First run and Super User ID

On first start with the Admin UI enabled you will be prompted to generate a Super User.

<img width="1573" height="976" alt="Admin_UI_first_install" src="https://github.com/user-attachments/assets/05aa634f-06ec-4a4d-a5c6-d90927c90991" />

If you need to read it from disk later:

```bash
cat /lnbits/data/.super_user
# example
123de4bfdddddbbeb48c8bc8382fe123
```

> [!WARNING]
> For security reasons, Super Users and Admin users must authenticate with credentials (username and password).

After login you will see **Settings** and **Users** in the sidebar between **Wallets** and **Extensions**, plus a role badge in the top left.

<img width="1353" height="914" alt="grafik" src="https://github.com/user-attachments/assets/06bb4f36-a23a-4058-87ec-60440d322c25" />

## Enabling or disabling the Admin UI

The Admin UI is enabled by default on new installs. To change the state:

1. Stop LNbits

   ```bash
   sudo systemctl stop lnbits.service
   ```

2. Edit your `.env`

   ```
   cd ~/lnbits
   sudo nano .env
   ```

3. Set one of

   ```
   # Enable Admin UI
   LNBITS_ADMIN_UI=true

   # Disable Admin UI
   LNBITS_ADMIN_UI=false
   ```

4. Start LNbits

   ```
   sudo systemctl start lnbits.service
   ```

> [!NOTE]
> With the Admin UI enabled, config is DB-backed and UI-managed settings ignore .env. Disable it to revert to [.env](../../.env.example) as the single source of truth.

## Reset to defaults

Using `Reset to defaults` in the Admin UI wipes stored settings. After a restart, a new `Super User` is created and the old one is no longer valid.

## Allowed Users

When set **at least one**, LNbits becomes private: only the listed users and Admins can access the frontend. Account creation is disabled automatically. You can also disable account creation explicitly.

<img width="1889" height="870" alt="grafik" src="https://github.com/user-attachments/assets/89011b75-a267-44ea-971a-1517968b7af5" />

> [!WARNING]
> Assign your own account first when enabling **Allowed Users** to avoid locking yourself out. If you do get locked out, use your Super User to recover access.

## Additional Guides

- **[Backend Wallets](./wallets.md)** — Explore options to fund your LNbits instance.
- **[User Roles](./user_roles.md)** — Overview of existing roles in LNbits.
- **[Funding sources](./funding-sources-table.md)** — What is available and how to configure each.
- **[Install LNBits](./installation.md)** — Choose your prefared way to install LNBits.

## Powered by LNbits

LNbits empowers everyone with modular, open source tools for building Bitcoin based systems — fast, free, and extendable.

If you like this project, [send some tip love](https://demo.lnbits.com/tipjar/DwaUiE4kBX6mUW6pj3X5Kg) or visit our [Shop](https://shop.lnbits.de)

[![LNbits Shop](https://demo.lnbits.com/static/images/bitcoin-shop-banner.png)](https://shop.lnbits.com/)
[![Visit LNbits Shop](https://img.shields.io/badge/Visit-LNbits%20Shop-7C3AED?logo=shopping-cart&logoColor=white&labelColor=5B21B6)](https://shop.lnbits.com/)
[![Try myLNbits SaaS](https://img.shields.io/badge/Try-myLNbits%20SaaS-2563EB?logo=lightning&logoColor=white&labelColor=1E40AF)](https://my.lnbits.com/login)
[![Read LNbits News](https://img.shields.io/badge/Read-LNbits%20News-F97316?logo=rss&logoColor=white&labelColor=C2410C)](https://news.lnbits.com/)
[![Explore LNbits Extensions](https://img.shields.io/badge/Explore-LNbits%20Extensions-10B981?logo=puzzle-piece&logoColor=white&labelColor=065F46)](https://extensions.lnbits.com/)
