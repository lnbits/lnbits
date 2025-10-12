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
# LNbits Super User



**Table of Content:**
- [What is the Super User?](#what-is-the-super-user)
- [When is the Super User created?](#when-is-the-super-user-created)
- [Enabling the Admin UI](#enabling-the-admin-ui)
- [Super User identity & storage](#super-user-identity--storage)
- [Security model (since v1)](#security-model-since-v1)
- [Admin vs Super User](#admin-vs-super-user)
- [Additional Guides](#additional-guides)




<details>
  <summary><strong>TL:DR</strong></summary>

- **No Admin UI → No Super User.** The Super User (SU) is created **only** when `LNBITS_ADMIN_UI=true`.
- **Why SU exists:** SU has extra frontend powers beyond an admin (e.g., **change funding source**, **restart server**, **credit/debit accounts**).
- **Security since v1:** Logging in as SU/admin **by user ID is disabled**. After enabling the Admin UI and visiting your instance, you’ll be **prompted to set a username + password** for the SU.
- **Why Admin UI:** Manage LNbits from a **clean UI** instead of editing `.env` and using the CLI for routine ops.

</details>

## What is the Super User?

The **Super User** is a privileged operator account in LNbits with front-end capabilities that extend beyond those of an ordinary admin. It is created with the initialisation of the [Admin UI](./admin_ui.md)

**Key SU capabilities:**

* **Change funding source** for the instance.
* **Restart the server** from within the web UI.
* **Credit / debit accounts** for operational adjustments.

> [!NOTE]
> These SU actions are intentionally separated from ordinary admin tasks to better align with the principle of dedicated privilege.

## Admin vs Super User

| Capability                            | Admin      | Super User |
| ------------------------------------- | ---------- | ---------- |
| View Admin UI                         | If enabled | If enabled |
| Manage users & wallets (standard ops) | ✓          | ✓          |
| Instance-level settings               | ✓          | ✓          |
| Change funding source                 | —          | ✓          |
| Credit/debit accounts                 | —          | ✓          |
| Restart server from UI                | —          | ✓          |

## When is the Super User created?

* The SU is **only created** when the **Admin UI is enabled**: `LNBITS_ADMIN_UI=true`.
* If `LNBITS_ADMIN_UI` is **not enabled**, there is **no SU** and the related UI is hidden.


## Enabling the Admin UI
> [!WARNING]
> For detailed information look up [Admin UI](./admin_ui.md) Section. Only enable if you understandf what you are doing.

Set the environment variable in your deployment:

```bash
# .env
LNBITS_ADMIN_UI=true
```

## Super User identity & storage

LNbits stores the **Super User ID** at:

```
/lnbits/data/.super_user
```

## Security model (since v1)

* **User-ID logins are disabled** for SU/admin roles.
* **SU requires credentials:** you must set **username + password** when enabling the Admin UI and first visiting your instance URL.

**Recommendation:**

* Use a strong, unique password manager-generated secret.
* Back up `/lnbits/data/.super_user` along with the rest of `/lnbits/data` in your standard secure backup workflow.


## Additional Guides
- **[Admin UI](./admin_ui.md)** — Manage server settings via a clean UI (avoid editing `.env` by hand).
- **[User Roles](./User_Roles.md)** — Quick Overview of existing Roles in LNBits.
- **[Funding sources](./funding-sources_table.md)** — What’s available and how to enable/configure each.

## Powered by LNbits
LNbits empowers everyone with modular, open-source tools for building Bitcoin-based systems - fast, free, and extendable.

If you like this project, [send some tip love](https://demo.lnbits.com/tipjar/DwaUiE4kBX6mUW6pj3X5Kg) or visit our [Shop](https://shop.lnbits.de)

[![LNbits Shop](https://demo.lnbits.com/static/images/bitcoin-shop-banner.png)](https://shop.lnbits.com/)  
[![Visit LNbits Shop](https://img.shields.io/badge/Visit-LNbits%20Shop-7C3AED?logo=shopping-cart&logoColor=white&labelColor=5B21B6)](https://shop.lnbits.com/)
[![Try myLNbits SaaS](https://img.shields.io/badge/Try-myLNbits%20SaaS-2563EB?logo=lightning&logoColor=white&labelColor=1E40AF)](https://my.lnbits.com/login)
[![Read LNbits News](https://img.shields.io/badge/Read-LNbits%20News-F97316?logo=rss&logoColor=white&labelColor=C2410C)](https://news.lnbits.com/)
[![Explore LNbits Extensions](https://img.shields.io/badge/Explore-LNbits%20Extensions-10B981?logo=puzzle-piece&logoColor=white&labelColor=065F46)](https://extensions.lnbits.com/)
