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

# Admin UI

We introduced the **Admin UI** to make setup simpler and safer. Instead of hand editing the `.env` file, you configure key server settings directly in the frontend with clear labels and guardrails. On a fresh install the Admin UI is enabled by default, and at first launch you are prompted to create **Super User** credentials so that sensitive operations, such as switching funding sources, remain in trusted hands. When the Admin UI is enabled, configuration is written to and read from the database; for all settings managed by the UI, the parameters in `.env` are largely no longer used. If you disable the Admin UI, the `.env` file becomes the single source of truth again and the UI will not override it. For privileged actions and role details see **[Super User](./super_user.md)**. For a complete reference of legacy variables consult **[.env.example](/lnbits/.env.example)**.

<img width="900" height="640" alt="grafik" src="https://github.com/user-attachments/assets/d8852b4b-21be-446f-a1e7-d3eb794d3505" />

> [!IMPORTANT]
> **State model Admin UI**  
> Enabled: configuration is stored in the database and used from there.  
> Disabled: the `.env` file is the single source of truth.

> [!WARNING]
> Some settings remain `.env` only. Use **[.env.example](/lnbits/.env.example)** as the authoritative reference for those variables.

<details>
  <summary><strong>.env-only settings (not managed by Admin UI)</strong></summary>

```
######################################
###### .env ONLY SETTINGS ############
######################################
# The following settings are ONLY set in your .env file.
# They are NOT managed by the Admin UI and are not stored in the database.

# === Logging and Development ===

DEBUG=False
DEBUG_DATABASE=False
BUNDLE_ASSETS=True

# logging into LNBITS_DATA_FOLDER/logs/
ENABLE_LOG_TO_FILE=true

# https://loguru.readthedocs.io/en/stable/api/logger.html#file
LOG_ROTATION="100 MB"
LOG_RETENTION="3 months"

# for database cleanup commands
# CLEANUP_WALLETS_DAYS=90

# === Admin Settings ===

# Enable Admin UI.
# Warning: Enabling this will make LNbits ignore most configurations in file.
# Only the configurations defined in `ReadOnlySettings` will still be read
# from environment variables. The rest will be stored in the database and
# changeable through the Admin UI.
# Disable this and clear the `settings` table to make LNbits use this file again.
LNBITS_ADMIN_UI=true

HOST=127.0.0.1
PORT=5000
# VERSION=
# USER_AGENT=

# === LNbits ===

# Database:
#  - To use SQLite, specify LNBITS_DATA_FOLDER
#  - To use PostgreSQL, set LNBITS_DATABASE_URL=postgres://...
#  - To use CockroachDB, set LNBITS_DATABASE_URL=cockroachdb://...
# For PostgreSQL and CockroachDB, install `psycopg2`.
LNBITS_DATA_FOLDER="./data"
# LNBITS_DATABASE_URL="postgres://user:password@host:port/databasename"

# Extensions to install by default. If an extension from this list is uninstalled,
# it will be reinstalled on the next restart unless removed from this list.
LNBITS_EXTENSIONS_DEFAULT_INSTALL="tpos"

# LNBITS_EXTENSIONS_MANIFESTS="https://raw.githubusercontent.com/lnbits/lnbits-extensions/main/extensions.json,https://raw.githubusercontent.com/lnbits/lnbits-extensions/main/extensions-trial.json"
# GitHub has API rate limits. Increase the limit by setting a GITHUB_TOKEN.
# LNBITS_EXT_GITHUB_TOKEN=github_pat_xxxxxxxxxxxxxxxxxx

# Which funding sources are allowed in the Admin UI
# LNBITS_ALLOWED_FUNDING_SOURCES="VoidWallet, FakeWallet, CoreLightningWallet, CoreLightningRestWallet, LndRestWallet, EclairWallet, LndWallet, LnTipsWallet, LNPayWallet, LNbitsWallet, BlinkWallet, AlbyWallet, ZBDWallet, PhoenixdWallet, OpenNodeWallet, NWCWallet, BreezSdkWallet, BoltzWallet, StrikeWallet, CLNRestWallet"

# Uvicorn variable to allow HTTPS behind a proxy
# IMPORTANT: your web server must forward headers correctly.
# http://docs.lnbits.org/guide/installation.html#running-behind-an-apache2-reverse-proxy-over-https
FORWARDED_ALLOW_IPS="*"

# Path where extensions will be installed (defaults to ./lnbits/).
# Inside this directory, the `extensions` and `upgrades` sub-directories will be created.
# LNBITS_EXTENSIONS_PATH="/path/to/some/dir"

# ID of the super user. The user ID must exist.
# SUPER_USER=""

# LNBITS_TITLE="LNbits API"
# LNBITS_PATH="folder/path"

# === Auth Configurations ===

# Secret Key: will default to the hash of the super user if not set.
# Strongly recommended: set your own random value.
AUTH_SECRET_KEY=""

# === Funding Source ===
# How many times to retry connecting to the Funding Source before defaulting to VoidWallet
# FUNDING_SOURCE_MAX_RETRIES=4

######################################
###### END .env ONLY SETTINGS ########
######################################
```
</details>

## What you can do with the Admin UI

- Switch funding sources and other server level settings
- Manage who can access LNbits (**[Allowed Users](#allowed-users)**)
- Promote or demote Admin Users
- Gate extensions to Admins only or disable them globally
- Adjust balances with credit or debit
- Adjust site customization

> [!NOTE]
> See **[Super User](./super_user.md)** for the role and permission differences compared to Admin Users.

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

## First run and Super User ID

On first start with the Admin UI enabled you will be prompted to generate a Super User. If you need to read it from disk later:

```bash
cat data/.super_user
# example
123de4bfdddddbbeb48c8bc8382fe123
```

> [!WARNING]
> For security reasons, Super Users and Admin users must authenticate with credentials (username and password).

After login you will see **Settings** and **Users** in the sidebar between **Wallets** and **Extensions**, plus a role badge in the top left.

<img width="1353" height="914" alt="grafik" src="https://github.com/user-attachments/assets/06bb4f36-a23a-4058-87ec-60440d322c25" />

## Reset to defaults

Using `Reset to defaults` in the Admin UI wipes stored settings. After a restart, a new `Super User` is created and the old one is no longer valid.

## Allowed Users

Environment variable: `LNBITS_ALLOWED_USERS` (comma-separated list of user IDs).

When set **at least one**, LNbits becomes private: only the listed users and Admins can access the frontend. Account creation is disabled automatically. You can also disable account creation explicitly.

<img width="1889" height="870" alt="grafik" src="https://github.com/user-attachments/assets/89011b75-a267-44ea-971a-1517968b7af5" />

> [!WARNING]
> Assign your own account first when enabling **Allowed Users** to avoid locking yourself out. If you do get locked out, use your Super User to recover access.

## Additional Guides

* **[Backend Wallets](./wallets.md)** — Explore options to fund your LNbits instance.
* **[User Roles](./User_Roles.md)** — Overview of existing roles in LNbits.
* **[Funding sources](./funding-sources_table.md)** — What is available and how to configure each.

## Powered by LNbits

LNbits empowers everyone with modular, open source tools for building Bitcoin based systems — fast, free, and extendable.

If you like this project, [send some tip love](https://demo.lnbits.com/tipjar/DwaUiE4kBX6mUW6pj3X5Kg) or visit our [Shop](https://shop.lnbits.de)

[![LNbits Shop](https://demo.lnbits.com/static/images/bitcoin-shop-banner.png)](https://shop.lnbits.com/)  
[![Visit LNbits Shop](https://img.shields.io/badge/Visit-LNbits%20Shop-7C3AED?logo=shopping-cart\&logoColor=white\&labelColor=5B21B6)](https://shop.lnbits.com/)
[![Try myLNbits SaaS](https://img.shields.io/badge/Try-myLNbits%20SaaS-2563EB?logo=lightning\&logoColor=white\&labelColor=1E40AF)](https://my.lnbits.com/login)
[![Read LNbits News](https://img.shields.io/badge/Read-LNbits%20News-F97316?logo=rss\&logoColor=white\&labelColor=C2410C)](https://news.lnbits.com/)
[![Explore LNbits Extensions](https://img.shields.io/badge/Explore-LNbits%20Extensions-10B981?logo=puzzle-piece\&logoColor=white\&labelColor=065F46)](https://extensions.lnbits.com/)
