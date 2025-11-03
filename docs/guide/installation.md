---
layout: default
title: Installation
nav_order: 1
---

<a href="https://lnbits.com" target="_blank" rel="noopener noreferrer">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://i.imgur.com/QE6SIrs.png">
    <img src="https://i.imgur.com/fyKPgVT.png" alt="LNbits" style="width:300px">
  </picture>
</a>

![phase: stable](https://img.shields.io/badge/phase-stable-2EA043) ![License: MIT](https://img.shields.io/badge/License-MIT-blue) ![PRs: welcome](https://img.shields.io/badge/PRs-Welcome-yellow) [![explore: LNbits extensions](https://img.shields.io/badge/explore-LNbits%20extensions-10B981)](https://extensions.lnbits.com/) [<img src="https://img.shields.io/badge/community_chat-Telegram-24A1DE">](https://t.me/lnbits) <img src="https://img.shields.io/badge/supported_by-%3E__OpenSats-f97316">

# Basic installation

> [!NOTE]
> **Default DB:** LNbits uses SQLite by default (simple & effective). You can switch to PostgreSQL — see the section below.

## Table of contents

- [Option 1: AppImage (Linux)](#option-1-appimage-linux)
- [Option 2: UV (recommended for developers)](#option-2-uv-recommended-for-developers)
- [Option 2a (Legacy): Poetry — Replaced by UV](#option-2a-legacy-poetry--replaced-by-uv)
- [Option 3: Install script (Debian/Ubuntu)](#option-3-install-script-debianubuntu)
- [Option 4: Nix](#option-4-nix)
- [Option 5: Docker](#option-5-docker)
- [Option 6: Fly.io](#option-6-flyio)
- [Troubleshooting](#troubleshooting)
- [Optional: PostgreSQL database](#optional-postgresql-database)
- [Using LNbits](#using-lnbits)
- [Additional guides](#additional-guides)
  - [Update LNbits (all methods)](#update-lnbits-all-methods)
  - [SQLite → PostgreSQL migration](#sqlite--postgresql-migration)
  - [LNbits as a systemd service](#lnbits-as-a-systemd-service)
  - [Reverse proxy with automatic HTTPS (Caddy)](#reverse-proxy-with-automatic-https-caddy)
  - [Apache2 reverse proxy over HTTPS](#apache2-reverse-proxy-over-https)
  - [Nginx reverse proxy over HTTPS](#nginx-reverse-proxy-over-https)
  - [HTTPS without a reverse proxy (self-signed)](#https-without-a-reverse-proxy-self-signed)
  - [LNbits on Umbrel behind Tor](#lnbits-on-umbrel-behind-tor)
  - [FreeBSD notes](#freebsd-notes)

## Option 1: AppImage (Linux)

**Quickstart**

1. Download latest AppImage from [releases](https://github.com/lnbits/lnbits/releases) **or** run:

```sh
sudo apt-get install jq libfuse2
wget $(curl -s https://api.github.com/repos/lnbits/lnbits/releases/latest | jq -r '.assets[] | select(.name | endswith(".AppImage")) | .browser_download_url') -O LNbits-latest.AppImage
chmod +x LNbits-latest.AppImage
LNBITS_ADMIN_UI=true HOST=0.0.0.0 PORT=5000 ./LNbits-latest.AppImage # most system settings are now in the admin UI, but pass additional .env variables here
```

- LNbits will create a folder for DB and extension files **in the same directory** as the AppImage.

> [!NOTE]
> **Next steps**
> Install complete → **[Running LNbits](#run-the-server)**
> Update LNBits → **[Update LNbits (all methods)](#update-lnbits-all-methods)**

## Option 2: UV (recommended for developers)

> [!IMPORTANT]
> **It is recommended to use the latest version of UV & Make sure you have Python version 3.12 installed.**

### Verify Python

```sh
python3 --version
```

### Install UV

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
```

### Install LNbits

```sh
git clone https://github.com/lnbits/lnbits.git
cd lnbits
git checkout main
uv sync --all-extras

cp .env.example .env
# Optional: set funding source and other options in .env (e.g., `nano .env`)
```

### Run the server

```sh
uv run lnbits
# To change port/host: uv run lnbits --port 9000 --host 0.0.0.0
# Add --debug to the command above and set DEBUG=true in .env for verbose output
```

### LNbits CLI

```sh
# Useful for superuser ID, updating extensions, etc.
uv run lnbits-cli --help
```

### Update LNbits

```sh
cd lnbits
# Stop LNbits with Ctrl + X or your service manager
# sudo systemctl stop lnbits

# Update code
git pull --rebase

uv sync --all-extras
uv run lnbits
```

#### Use Admin UI → Extensions → "Update All" to bring extensions up to the proper level

> [!NOTE]
> **Next steps**
> Install complete → **[Running LNbits](#run-the-server)**
> Update LNBits → **[Update LNbits (all methods)](#update-lnbits-all-methods)**

## Option 2a (Legacy): Poetry — _Replaced by UV_

<details>
<summary><strong>Poetry install and update (legacy workflow)</summary>

This legacy section is preserved for older environments.
**UV is the recommended (and faster) tool** for new installs. Use Poetry only if you have personal preferences or must support an older workflow.

> ![IMPORTANT](https://img.shields.io/badge/IMPORTANT-7c3aed?labelColor=494949)
> **It is recommended to use the latest version of Poetry & Make sure you have Python version 3.12 installed.**

### Verify Python version

```sh
python3 --version
```

### Install Poetry

```sh
# If path 'export PATH="$HOME/.local/bin:$PATH"' fails, use the path echoed by the install
curl -sSL https://install.python-poetry.org | python3 - && export PATH="$HOME/.local/bin:$PATH"
```

### Install LNbits

```sh
git clone https://github.com/lnbits/lnbits.git
cd lnbits
poetry env use 3.12
git checkout main
poetry install --only main
cp .env.example .env
# Optional: to set funding source amongst other options via the env `nano .env`
```

#### Running the server

```sh
poetry run lnbits
# To change port/host: poetry run lnbits --port 9000 --host 0.0.0.0
# Add --debug to help troubleshooting (also set DEBUG=true in .env)
```

#### LNbits CLI

```sh
# A very useful terminal client for getting the superuser ID, updating extensions, etc.
poetry run lnbits-cli --help
```

#### Updating the server

```sh
cd lnbits
# Stop LNbits with Ctrl + X or with your service manager
# sudo systemctl stop lnbits

# Update LNbits
git pull --rebase

# Check your Poetry Python version
poetry env list
# If version is less than 3.12, update it:
poetry env use python3.12
poetry env remove python3.X
poetry env list

# Reinstall and start
poetry install --only main
poetry run lnbits
```

#### Use Admin UI → Extensions → "Update All" to bring extensions up to the proper level

> ![NOTE](https://img.shields.io/badge/NOTE-3b82f6?labelColor=494949)
> **Next steps**
> Install complete → **[Running LNbits](#run-the-server)**
> Update LNBits → **[Update LNbits (all methods)](#update-lnbits-all-methods)**

</details>

## Option 3: Install script (Debian/Ubuntu)

<details>
<summary><strong>Show install script</strong> (one-line setup)</summary>

```sh
wget https://raw.githubusercontent.com/lnbits/lnbits/main/lnbits.sh &&
chmod +x lnbits.sh &&
./lnbits.sh
```

- You can use `./lnbits.sh` to run, but for more control: `cd lnbits` and use `uv run lnbits` (see Option 2).

> ![NOTE](https://img.shields.io/badge/NOTE-3b82f6?labelColor=494949)
> **Next steps**
> Install complete → **[Running LNbits](#run-the-server)**
> Update LNBits → **[Update LNbits (all methods)](#update-lnbits-all-methods)**

</details>

## Option 4: Nix

<details>
<summary><strong>Show Nix instructions</strong> (flakes, cachix, run)</summary>

```sh
# Install nix. If you have installed via another manager, remove and use this install (from https://nixos.org/download)
sh <(curl --proto '=https' --tlsv1.2 -L https://nixos.org/nix/install) --daemon --yes

# Enable nix-command and flakes experimental features for nix:
grep -qxF 'experimental-features = nix-command flakes' /etc/nix/nix.conf || \
echo 'experimental-features = nix-command flakes' | sudo tee -a /etc/nix/nix.conf

# Add user to Nix
grep -qxF "trusted-users = root $USER" /etc/nix/nix.conf || \
echo "trusted-users = root $USER" | sudo tee -a /etc/nix/nix.conf

# Restart daemon so changes apply
sudo systemctl restart nix-daemon

# Clone and build LNbits
git clone https://github.com/lnbits/lnbits.git
cd lnbits

# Make data directory and persist data/extension folders
mkdir data
PROJECT_DIR="$(pwd)"
{
  echo "export PYTHONPATH=\"$PROJECT_DIR/ns:\$PYTHONPATH\""
  echo "export LNBITS_DATA_FOLDER=\"$PROJECT_DIR/data\""
  echo "export LNBITS_EXTENSIONS_PATH=\"$PROJECT_DIR\""
} >> ~/.bashrc
grep -qxF '. /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh' ~/.bashrc || \
  echo '. /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh' >> ~/.bashrc
. ~/.bashrc

# Add cachix for cached binaries
nix-env -iA cachix -f https://cachix.org/api/v1/install
cachix use lnbits

# Build LNbits
nix build

```

#### Running the server

```sh
nix run
```

Ideally you would set the environment via the `.env` file,
but you can also set the env variables or pass command line arguments:

```sh
# .env variables are currently passed when running, but LNbits can be managed with the admin UI.
LNBITS_ADMIN_UI=true ./result/bin/lnbits --port 9000 --host 0.0.0.0

# Once you have created a user, you can set as the super_user
SUPER_USER=be54db7f245346c8833eaa430e1e0405 LNBITS_ADMIN_UI=true ./result/bin/lnbits --port 9000
```

> ![NOTE](https://img.shields.io/badge/NOTE-3b82f6?labelColor=494949)
> **Next steps**
> Update LNBits → **[Update LNbits (all methods)](#update-lnbits-all-methods)**

</details>

## Option 5: Docker

<details>
<summary><strong>Show Docker instructions</strong> (official image, volumes, extensions)</summary>

**Use latest image**

```sh
docker pull lnbits/lnbits
wget https://raw.githubusercontent.com/lnbits/lnbits/main/.env.example -O .env
mkdir data
docker run --detach --publish 5000:5000 --name lnbits \
  --volume ${PWD}/.env:/app/.env \
  --volume ${PWD}/data/:/app/data \
  lnbits/lnbits
```

- The LNbits Docker image ships **without any extensions**; by default, any extensions you install are stored **inside the container** and will be **lost** when the container is removed, so you should set `LNBITS_EXTENSIONS_PATH` to a directory that’s **mapped to a persistent host volume** so extensions **survive rebuilds/recreates**—for example:

```sh
docker run ... -e "LNBITS_EXTENSIONS_PATH='/app/data/extensions'" --volume ${PWD}/data/:/app/data ...
```

**Build image yourself**

```sh
git clone https://github.com/lnbits/lnbits.git
cd lnbits
docker build -t lnbits/lnbits .
cp .env.example .env
mkdir data
docker run --detach --publish 5000:5000 --name lnbits \
  --volume ${PWD}/.env:/app/.env \
  --volume ${PWD}/data/:/app/data \
  lnbits/lnbits
```

You can optionally override the install extras for both **Poetry** and **UV** to include optional features during build or setup:

- with Poetry, pass extras via the `POETRY_INSTALL_ARGS` Docker build-arg (e.g., to enable the **Breez** funding source: `docker build --build-arg POETRY_INSTALL_ARGS="-E breez" -t lnbits/lnbits .`);
- with UV, enable extras during environment sync (e.g., locally run `uv sync --extra breez` or `uv sync --all-extras`), and—**if your Dockerfile supports it**—you can mirror the same at build time via a build-arg such as `UV_SYNC_ARGS` (example pattern: `docker build --build-arg UV_SYNC_ARGS="--extra breez" -t lnbits/lnbits .`).

**Enable Breez funding source at build**

```sh
docker build --build-arg POETRY_INSTALL_ARGS="-E breez" -t lnbits/lnbits .
```

> ![NOTE](https://img.shields.io/badge/NOTE-3b82f6?labelColor=494949)
> **Next steps**
> Install complete → **[Running LNbits](#run-the-server)**
> Update LNBits → **[Update LNbits (all methods)](#update-lnbits-all-methods)**

</details>

## Option 6: Fly.io

<details>
<summary><strong>Deploy LNbits on Fly.io (free tier friendly)</summary>

**Fly.io is a docker container hosting platform that has a generous free tier. You can host LNbits for free on Fly.io for personal use.**

1. Create an account at [Fly.io](https://fly.io).
2. Install the Fly.io CLI ([guide](https://fly.io/docs/getting-started/installing-flyctl/)).

```
flyctl was installed successfully to /home/ubuntu/.fly/bin/flyctl
Manually add the directory to your $HOME/.bash_profile (or similar)
  export FLYCTL_INSTALL="/home/ubuntu/.fly"
  export PATH="$FLYCTL_INSTALL/bin:$PATH"
```

3. You can either run those commands, then `source ~/.bash_profile` or, if you don't, you'll have to call Fly from `~/.fly/bin/flyctl`.

- Once installed, run the following commands.

```
git clone https://github.com/lnbits/lnbits.git
cd lnbits
fly auth login
[complete login process]
fly launch
```

You'll be prompted to enter an app name, region, postgres (choose no), deploy now (choose no).

You'll now find a file in the directory called `fly.toml`. Open that file and modify/add the following settings.

> ![IMPORTANT](https://img.shields.io/badge/IMPORTANT-7c3aed?labelColor=494949)
> Be sure to replace `${PUT_YOUR_LNBITS_ENV_VARS_HERE}` with all relevant environment variables in `.env` or `.env.example`.
> Environment variable strings should be quoted here. For example, if `.env` has
> `LNBITS_ENDPOINT=https://demo.lnbits.com`, then in `fly.toml` use
> `LNBITS_ENDPOINT="https://demo.lnbits.com"`.

> ![WARNING](https://img.shields.io/badge/WARNING-ea580c?labelColor=494949)
> Don't enter secret environment variables here. Fly.io offers **secrets** (via `fly secrets`) that are exposed as env vars at runtime.
> Example (LND REST funding source):
> `fly secrets set LND_REST_MACAROON=<hex_macaroon_data>`

```
...
kill_timeout = 30
...

...
[mounts]
  source="lnbits_data"
  destination="/data"
...

...
[env]
  HOST="127.0.0.1"
  PORT=5000
  FORWARDED_ALLOW_IPS="*"
  LNBITS_BASEURL="https://mylnbits.lnbits.org/"
  LNBITS_DATA_FOLDER="/data"

  ${PUT_YOUR_LNBITS_ENV_VARS_HERE}
...

...
[[services]]
  internal_port = 5000
...
```

Next, create a volume to store the sqlite database for LNbits. Be sure to choose the same region for the volume that you chose earlier.

```
fly volumes create lnbits_data --size 1
```

You're ready to deploy! Run `fly deploy` and follow the steps to finish deployment. You'll select a `region` (up to you, choose the same as you did for the storage volume previously created), `postgres` (choose no), `deploy` (choose yes).

You can use `fly logs` to view the application logs, or `fly ssh console` to get a ssh shell in the running container.

### Troubleshooting

Problems installing? These commands have helped us install LNbits.

```sh
sudo apt install pkg-config libffi-dev libpq-dev

# build essentials for debian/ubuntu
sudo apt install python3.10-dev gcc build-essential

# if the secp256k1 build fails:
# if you used poetry
poetry add setuptools wheel
```

> ![NOTE](https://img.shields.io/badge/NOTE-3b82f6?labelColor=0b0b0b)
>
> **Next steps**
> Install complete → **[Running LNbits](#run-the-server)**
> Update LNbits → **[Update LNbits (all methods)](#update-lnbits-all-methods)**

## Troubleshooting

```sh
sudo apt install pkg-config libffi-dev libpq-dev

# build essentials (Debian/Ubuntu)
sudo apt install python3.10-dev gcc build-essential

# if secp256k1 build fails and you used poetry
poetry add setuptools wheel
```

</details>

</details>

## Optional: PostgreSQL database

> [!TIP]
> If you want to use LNbits at scale, we recommend using PostgreSQL as the backend database. Install Postgres and set up a database for LNbits.

```sh
# Debian/Ubuntu: sudo apt-get -y install postgresql
# or see https://www.postgresql.org/download/linux/

# Create a password for the postgres user
sudo -i -u postgres
psql
# in psql
ALTER USER postgres PASSWORD 'myPassword';
\q
# back as postgres user
createdb lnbits
exit
```

**Configure LNbits**

```sh
# add the database connection string to .env 'nano .env' LNBITS_DATABASE_URL=
# postgres://<user>:<myPassword>@<host>:<port>/<lnbits> - alter line bellow with your user, password and db name
LNBITS_DATABASE_URL="postgres://postgres:postgres@localhost:5432/lnbits"
# save and exit
```

# Using LNbits

Visit **[http://localhost:5000/](http://localhost:5000/)** (or `0.0.0.0:5000`).

### Option A — First-run setup in the Browser (UI)

1. On the **first start**, LNbits will **prompt you to Setup a SuperUser**.
2. After creating it, you’ll be **redirected to the Admin UI as SuperUser**.
3. In the Admin UI, **set your funding source** (backend wallet) and other preferences.
4. **Restart LNbits** if prompted or after changing critical settings.

> [!IMPORTANT]
> Use the **SuperUser only** for initial setup and instance settings (funding source, configuration, Topup).
> For maintenance, create a separate **Admin** account. For everyday usage (payments, wallets, etc.), **do not use the SuperUser** — use admin or regular user accounts instead. Its a bad behaviour.
> Read more about [SuperUser](./super_user.md) and [Admin UI](./admin_ui.md)

### Option B — Configure via `.env`

1. Edit your `.env` with preferred settings (funding, base URL, etc.).
2. Set a funding source by configuring:
   - `LNBITS_BACKEND_WALLET_CLASS`
   - plus the required credentials for your chosen backend (see **[wallets.md](./wallets.md)**).

3. **Restart LNbits** to apply changes.

---

> [!NOTE]
> **Paths overview**
>
> - **SuperUser file:** `<lnbits_root>/data/.super_user`
>   Example: `~/lnbits/data/.super_user` • View: `cat ~/lnbits/data/.super_user`
> - **Environment file:** `<lnbits_root>/.env` (for bare-metal installs)
> - **Docker:** bind a host directory to `/app/data`.
>   On the host the SuperUser file is at `<host_data_dir>/.super_user`.
>   The container reads `/app/.env` (usually bind-mounted from your project root).

> [!TIP]
> **Local Lightning test network**
> Use **Polar** to spin up a safe local Lightning environment and test LNbits without touching your live setup.
> https://lightningpolar.com/

> [!TIP]
> **API comparison before updates**
> Use **TableTown** to diff your LNbits instance against another (dev vs prod) or the upstream dev branch. Spot endpoint changes before updating.
> Crafted by [Arbadacarbayk](https://github.com/arbadacarbaYK) - a standout contribution that makes pre-release reviews fast and reliable.
> https://arbadacarbayk.github.io/LNbits_TableTown/

# Additional guides

## Update LNbits (all methods)

> After updating, open **Admin UI → Extensions → “Update All”** to make sure extensions match the core version.

<details>
<summary><strong>UV (recommended)</strong></summary>

```sh
cd lnbits
git pull --rebase
uv sync --all-extras
# restart (dev)
uv run lnbits
```

</details>

<details>
<summary><strong>Poetry (legacy)</strong></summary>

```sh
cd lnbits
git pull --rebase
# Optional: ensure Python 3.12
poetry env list
poetry env use python3.12
poetry install --only main
# restart (dev)
poetry run lnbits
```

</details>

<details>
<summary><strong>AppImage</strong></summary>

Download the latest AppImage from Releases and replace your old file **in the same directory** to keep the `./data` folder (DB, extensions).

</details>

<details>
<summary><strong>Install script (Debian/Ubuntu)</strong></summary>

```sh
# If you installed via lnbits.sh:
cd lnbits
git pull --rebase
# then use your chosen runner (UV recommended)
uv sync --all-extras
uv run lnbits
```

</details>

<details>
<summary><strong>Nix</strong></summary>

```sh
cd lnbits
git pull --rebase
nix build
# restart
nix run
```

</details>

<details>
<summary><strong>Docker (official image)</strong></summary>

```sh
docker pull lnbits/lnbits
docker stop lnbits && docker rm lnbits
docker run --detach --publish 5000:5000 --name lnbits \
  --volume ${PWD}/.env:/app/.env \
  --volume ${PWD}/data/:/app/data \
  lnbits/lnbits
```

</details>

<details>
<summary><strong>Docker (build yourself)</strong></summary>

```sh
cd lnbits
git pull --rebase
docker build -t lnbits/lnbits .
docker stop lnbits && docker rm lnbits
docker run --detach --publish 5000:5000 --name lnbits \
  --volume ${PWD}/.env:/app/.env \
  --volume ${PWD}/data/:/app/data \
  lnbits/lnbits
```

</details>

<details>
<summary><strong>Fly.io</strong></summary>

```sh
# If using Dockerfile in repo (recommended)
cd lnbits
git pull --rebase
fly deploy
# Logs & shell if needed
fly logs
fly ssh console
```

</details>

## SQLite → PostgreSQL migration

> [!TIP]
> If you run on SQLite and plan to scale, migrate to Postgres.

```sh
# STOP LNbits

# Edit .env with Postgres URL
LNBITS_DATABASE_URL="postgres://postgres:postgres@localhost/lnbits"
# save and exit

# START then STOP LNbits once to apply schema
uv run python tools/conv.py
# or
make migration
```

- Launch LNbits again and verify.

## LNbits as a systemd service

Create `/etc/systemd/system/lnbits.service`:

```
# Systemd unit for lnbits
# /etc/systemd/system/lnbits.service

[Unit]
Description=LNbits
# Optional: start after your backend
#Wants=lnd.service
#After=lnd.service

[Service]
WorkingDirectory=/home/lnbits/lnbits
# Find uv path via `which uv`
ExecStart=/home/lnbits/.local/bin/uv run lnbits
User=lnbits
Restart=always
TimeoutSec=120
RestartSec=30
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Enable & start:

```sh
sudo systemctl enable lnbits.service
sudo systemctl start lnbits.service
```

## Reverse proxy with automatic HTTPS (Caddy)

Point your domain A-record to your server IP. Install Caddy: [Caddy install guide](https://caddyserver.com/docs/install#debian-ubuntu-raspbian)

```sh
sudo caddy stop
sudo nano Caddyfile
```

Add:

```
yourdomain.com {
  reverse_proxy 0.0.0.0:5000 {
    header_up X-Forwarded-Host yourdomain.com
  }
}
```

Save (Ctrl+X) and start:

```sh
sudo caddy start
```

## Apache2 reverse proxy over HTTPS

```sh
apt-get install apache2 certbot
a2enmod headers ssl proxy proxy_http
certbot certonly --webroot --agree-tos --non-interactive --webroot-path /var/www/html -d lnbits.org
```

Create `/etc/apache2/sites-enabled/lnbits.conf`:

```sh
cat <<EOF > /etc/apache2/sites-enabled/lnbits.conf
<VirtualHost *:443>
  ServerName lnbits.org
  SSLEngine On
  SSLProxyEngine On
  SSLCertificateFile /etc/letsencrypt/live/lnbits.org/fullchain.pem
  SSLCertificateKeyFile /etc/letsencrypt/live/lnbits.org/privkey.pem
  Include /etc/letsencrypt/options-ssl-apache.conf
  LogLevel info
  ErrorLog /var/log/apache2/lnbits.log
  CustomLog /var/log/apache2/lnbits-access.log combined
  RequestHeader set "X-Forwarded-Proto" expr=%{REQUEST_SCHEME}
  RequestHeader set "X-Forwarded-SSL" expr=%{HTTPS}
  ProxyPreserveHost On
  ProxyPass / http://localhost:5000/
  ProxyPassReverse / http://localhost:5000/
  <Proxy *>
      Order deny,allow
      Allow from all
  </Proxy>
</VirtualHost>
EOF
```

Restart:

```sh
service apache2 restart
```

## Nginx reverse proxy over HTTPS

```sh
apt-get install nginx certbot
certbot certonly --nginx --agree-tos -d lnbits.org
```

Create `/etc/nginx/sites-enabled/lnbits.org`:

```sh
cat <<EOF > /etc/nginx/sites-enabled/lnbits.org
server {
    server_name lnbits.org;

    location / {
        proxy_pass http://127.0.0.1:5000;
    }

    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;

    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_pass_request_headers on;

    # WebSocket support
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "Upgrade";

    listen [::]:443 ssl;
    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/lnbits.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/lnbits.org/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}
EOF
```

Restart:

```sh
service nginx restart
```

---

## HTTPS without a reverse proxy (self-signed)

Create a self-signed cert (useful for local/dev). Browsers won’t trust it by default.

### Install mkcert

- Install instructions: [mkcert README](https://github.com/FiloSottile/mkcert)
- Ubuntu example:

```sh
sudo apt install libnss3-tools
curl -JLO "https://dl.filippo.io/mkcert/latest?for=linux/amd64"
chmod +x mkcert-v*-linux-amd64
sudo cp mkcert-v*-linux-amd64 /usr/local/bin/mkcert
```

### Create certificate

**OpenSSL**

```sh
openssl req -new -newkey rsa:4096 -x509 -sha256 -days 3650 -nodes -out cert.pem -keyout key.pem
```

**mkcert** (alternative)

```sh
# include your local IP (e.g., 192.x.x.x) if needed
mkcert localhost 127.0.0.1 ::1
```

**Run with certs**

```sh
poetry run uvicorn lnbits.__main__:app --host 0.0.0.0 --port 5000 --ssl-keyfile ./key.pem --ssl-certfile ./cert.pem
```

## LNbits on Umbrel behind Tor

See this community [guide](https://community.getumbrel.com/t/guide-lnbits-without-tor/604).

## FreeBSD notes

Issue with secp256k1 0.14.0 on FreeBSD (thanks @GitKalle):

1. Install `py311-secp256k1` with `pkg install py311-secp256k1`.
2. Change version in `pyproject.toml` from `0.14.0` to `0.13.2`.
3. Rewrite `poetry.lock` with `poetry lock`.
4. Follow install instructions with Poetry.

---

## Powered by LNbits

LNbits empowers everyone with modular, open-source tools for building Bitcoin-based systems — fast, free, and extendable.

If you like this project [send some tip love](https://demo.lnbits.com/tipjar/DwaUiE4kBX6mUW6pj3X5Kg) or visiting our [Shop](https://shop.lnbits.com)

[![LNbits Shop](https://demo.lnbits.com/static/images/bitcoin-shop-banner.png)](https://shop.lnbits.com/)
[![Visit LNbits Shop](https://img.shields.io/badge/Visit-LNbits%20Shop-7C3AED?logo=shopping-cart&logoColor=white&labelColor=5B21B6)](https://shop.lnbits.com/) [![Try myLNbits SaaS](https://img.shields.io/badge/Try-myLNbits%20SaaS-2563EB?logo=lightning&logoColor=white&labelColor=1E40AF)](https://my.lnbits.com/login) [![Read LNbits News](https://img.shields.io/badge/Read-LNbits%20News-F97316?logo=rss&logoColor=white&labelColor=C2410C)](https://news.lnbits.com/) [![Explore LNbits Extensions](https://img.shields.io/badge/Explore-LNbits%20Extensions-10B981?logo=puzzle-piece&logoColor=white&labelColor=065F46)](https://extensions.lnbits.com/)
