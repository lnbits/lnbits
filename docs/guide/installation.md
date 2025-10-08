

# LNbits — Basic Installation

**Default DB:** LNbits uses **SQLite** by default (simple and effective). You can switch to **PostgreSQL** (recommended for scale) — see **Database (PostgreSQL)** below.


---


## Table of Contents

1. [Basic Install Options](#basic-install-options)

   * [Option 1 — AppImage (Linux)](#option-1-appimage-linux)
   * [Option 2 — Poetry (recommended)](#option-2-poetry-recommended)
   * [Option 3 — Install script (Debian/Ubuntu)](#option-3-install-script-debianubuntu)
   * [Option 4 — Nix](#option-4-nix)
   * [Option 5 — Docker](#option-5-docker)
   * [Option 6 — Fly.io](#option-6-flyio)

2. [Using LNbits (first run, SuperUser, funding source)](#using-lnbits)

3. [Scale & Networking Guides](#scale--networking-guides)

   * [Database (PostgreSQL) & Migration](#database-postgresql--migration)
   * [Caddy (HTTPS reverse proxy)](#reverse-proxy-with-automatic-https-using-caddy)
   * [Apache (HTTPS reverse proxy)](#running-behind-an-apache2-reverse-proxy-over-https)
   * [Nginx (HTTPS reverse proxy)](#running-behind-an-nginx-reverse-proxy-over-https)
   * [HTTPS without reverse proxy (mkcert / self-signed)](#using-https-without-reverse-proxy)
   * [Umbrel behind Tor (clearnet access)](#lnbits-running-on-umbrel-behind-tor)

4. [Service Management](#service-management)

   * [systemd service](#lnbits-as-a-systemd-service)

5. [Troubleshooting](#troubleshooting)

6. [Platform Notes (FreeBSD)](#freebsd-notes)

---

## Basic Install Options

### Option 1: AppImage (Linux)

LNbits will create a folder for DB and extension files in the directory where the AppImage runs.

```sh
sudo apt-get install libfuse2
wget $(curl -s https://api.github.com/repos/lnbits/lnbits/releases/latest | jq -r '.assets[] | select(.name | endswith(".AppImage")) | .browser_download_url') -O LNbits-latest.AppImage
chmod +x LNbits-latest.AppImage
LNBITS_ADMIN_UI=true HOST=0.0.0.0 PORT=5000 ./LNbits-latest.AppImage # most system settings are now in the admin UI, but pass additional .env variables here
```

---

### Option 2: Poetry (recommended)

> **Tip:** Recommend to use **Python 3.12** for best compatibility. Create a dedicated virtual environment and pin the version (`poetry env use 3.12`).
>
> **Note:** After installing Poetry, ensure your shell has **`$HOME/.local/bin`** on `PATH`. Use the path echoed by the installer if different.
> Make sure you have **Python 3.12** installed.

**Verify Python version**

```sh
python3 --version
```

**Install Poetry**

```sh
# If path 'export PATH="$HOME/.local/bin:$PATH"' fails, use the path echoed by the install
curl -sSL https://install.python-poetry.org | python3 - && export PATH="$HOME/.local/bin:$PATH"
```

**Install LNbits**

```sh
git clone https://github.com/lnbits/lnbits.git
cd lnbits
poetry env use 3.12
git checkout main
poetry install --only main
cp .env.example .env
# Optional: to set funding source amongst other options via the env `nano .env`
```

**Run the server**

```sh
poetry run lnbits
# To change port/host pass 'poetry run lnbits --port 9000 --host 0.0.0.0'
# Add --debug to help troubleshooting and generate more verbose output
# Note: also add 'DEBUG=true' in your .env file.
```

**LNbits CLI**

```sh
# Useful for getting the superuser ID, updating extensions, etc.
poetry run lnbits-cli --help
```

**Update the server**

```sh
cd lnbits
# Stop LNbits with `ctrl + x` or with service manager
# sudo systemctl stop lnbits

# Update LNbits
git pull --rebase

# Check your poetry version with
poetry env list
# If version is less 3.12, update it by running
poetry env use python3.12
poetry env remove python3.9
poetry env list

# Run install and start LNbits with
poetry install --only main
poetry run lnbits

# Use LNbits admin UI → Extensions → "Update All" to align extensions
```

---

### Option 3: Install script (Debian/Ubuntu)

```sh
wget https://raw.githubusercontent.com/lnbits/lnbits/main/lnbits.sh &&
chmod +x lnbits.sh &&
./lnbits.sh
```

Now visit `0.0.0.0:5000` to make a super-user account.

`./lnbits.sh` can be used to run, but for more control `cd lnbits` and use `poetry run lnbits` (see Poetry option).

---

### Option 4: Nix

```sh
# Install nix. If you have installed via another manager, remove and use this install (from https://nixos.org/download)
sh <(curl -L https://nixos.org/nix/install) --daemon

# Enable nix-command and flakes experimental features for nix:
echo 'experimental-features = nix-command flakes' >> /etc/nix/nix.conf

# Add cachix for cached binaries
nix-env -iA cachix -f https://cachix.org/api/v1/install
cachix use lnbits

# Clone and build LNbits
git clone https://github.com/lnbits/lnbits.git
cd lnbits
nix build

mkdir data
```

**Run the server**

```sh
nix run
```

**Environment options**

```sh
# .env variables are currently passed when running, but LNbits can be managed with the admin UI.
LNBITS_ADMIN_UI=true ./result/bin/lnbits --port 9000

# Once you have created a user, you can set as the super_user
SUPER_USER=be54db7f245346c8833eaa430e1e0405 LNBITS_ADMIN_UI=true ./result/bin/lnbits --port 9000
```

---

### Option 5: Docker

> **Important:** The official image ships **without extensions preinstalled**. Persist your extensions by setting `LNBITS_EXTENSIONS_PATH` to a folder mapped to a **Docker volume** (e.g., `/app/data/extensions`).
>
> **Tip:** Always mount **`.env`** and a persistent **`data/`** directory to keep settings and the database across container recreations.
> Use latest version from Docker Hub **or** build the image yourself.

**Pull official image**

```sh
docker pull lnbits/lnbits
wget https://raw.githubusercontent.com/lnbits/lnbits/main/.env.example -O .env
mkdir data
docker run --detach --publish 5000:5000 --name lnbits \
  --volume ${PWD}/.env:/app/.env \
  --volume ${PWD}/data/:/app/data \
  lnbits/lnbits
```

> The LNbits Docker image ships with **no extensions installed**. To persist extensions across container rebuilds, set `LNBITS_EXTENSIONS_PATH` to a directory mapped to a Docker volume:

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

**Enable Breez funding source at build time (optional)**

```sh
docker build --build-arg POETRY_INSTALL_ARGS="-E breez" -t lnbits/lnbits .
```

Finally, access LNbits on port **5000** of your host.

---

### Option 6: Fly.io

> **Security:** Put secrets (macaroons, API keys, etc.) into **Fly Secrets** (`fly secrets set ...`), not directly in `fly.toml`. They will be exposed as env vars at runtime.
> Fly.io is a Docker hosting platform with a generous free tier. You can host LNbits for free for personal use.

1. **Create account:** [https://fly.io](https://fly.io) (no credit card required).

2. **Install CLI:** [https://fly.io/docs/getting-started/installing-flyctl/](https://fly.io/docs/getting-started/installing-flyctl/)

After install, add `flyctl` to your PATH (example output):

```
flyctl was installed successfully to /home/ubuntu/.fly/bin/flyctl
Manually add the directory to your $HOME/.bash_profile (or similar)
  export FLYCTL_INSTALL="/home/ubuntu/.fly"
  export PATH="$FLYCTL_INSTALL/bin:$PATH"
```

Either run those exports and `source ~/.bash_profile`, or call Fly as `~/.fly/bin/flyctl`.

3. **Launch app**

```sh
git clone https://github.com/lnbits/lnbits.git
cd lnbits
fly auth login
# complete login process
fly launch
```

Choose: app name, region, **postgres: no**, **deploy now: no**.

4. **Edit `fly.toml`** and set:

> Replace `${PUT_YOUR_LNBITS_ENV_VARS_HERE}` with relevant `.env` values. Strings must be quoted. Use `fly secrets` for sensitive values.

```
...
kill_timeout = 30
...

[mounts]
  source="lnbits_data"
  destination="/data"
...

[env]
  HOST="127.0.0.1"
  PORT=5000
  FORWARDED_ALLOW_IPS="*"
  LNBITS_BASEURL="https://mylnbits.lnbits.org/"
  LNBITS_DATA_FOLDER="/data"

  ${PUT_YOUR_LNBITS_ENV_VARS_HERE}
...

[[services]]
  internal_port = 5000
...
```

5. **Create volume** (choose same region):

```sh
fly volumes create lnbits_data --size 1
```

6. **Deploy**

```sh
fly deploy
```

Pick region (same as volume), postgres (no), deploy (yes).

**Inspect**: `fly logs` or `fly ssh console` for a shell in the running container.

---

## Using LNbits

Visit **[http://localhost:5000/](http://localhost:5000/)** (or `0.0.0.0:5000`).

### Option A — First-run setup in the UI

1. On the **first start**, LNbits will **prompt you to create a SuperUser**.
2. After creating it, you’ll be **redirected to the Admin UI as SuperUser**.
3. In the Admin UI, **set your funding source** (backend wallet) and other preferences.
4. **Restart LNbits** if prompted or after changing critical settings.

> **Important:** Use the **SuperUser only** for initial setup and instance settings (funding source, configuration, Topup).
> For maintenance, create a separate **Admin** account. For everyday usage (payments, wallets, etc.), **do not use the SuperUser** — use admin or regular user accounts instead.

### Option B — Configure via `.env`

1. Edit your `.env` with preferred settings (funding, base URL, etc.).
2. Set a funding source by configuring:

   * `LNBITS_BACKEND_WALLET_CLASS`
   * plus the required credentials for your chosen backend (see **[wallets.md](./wallets.md)**).
3. **Restart LNbits** to apply changes.

> **Note (paths):**
> - The SuperUser ID is stored in `<lnbits_root>/data/.super_user`.
> - Example: `~/lnbits/data/.super_user` (view with `cat ~/lnbits/data/.super_user`).
> - Your `.env` lives in `<lnbits_root>/.env` (e.g., `~/lnbits/.env`).
> - **Docker:** map a host directory to `/app/data`; the SuperUser file will be at `<host_data_dir>/.super_user`. The container reads `/app/.env` (usually mounted from your project root).

**Nice to know — Local dev:** Use **Polar** for a local Lightning Network setup: [https://lightningpolar.com/](https://lightningpolar.com/)

---

## Scale & Networking Guides

## Database (PostgreSQL) & Migration

### Optional: PostgreSQL database

> **Recommendation:** For **production** or higher traffic, use **PostgreSQL** as the backend database instead of SQLite.
> Recommended for scale. Install Postgres and set up a database:

```sh
# Debian/Ubuntu
# sudo apt-get -y install postgresql
# or follow instructions at https://www.postgresql.org/download/linux/

# Postgres doesn't have a default password, so we'll create one.
sudo -i -u postgres
psql
# in psql
ALTER USER postgres PASSWORD 'myPassword'; # choose a password
\q
# back on postgres user
createdb lnbits
exit
```

Edit `.env`:

```sh
# postgres://<user>:<myPassword>@<host>:<port>/<lnbits>
LNBITS_DATABASE_URL="postgres://postgres:postgres@localhost:5432/lnbits"
```

### SQLite to PostgreSQL migration

> **Warning:** **Stop LNbits** before migrating. Ensure LNbits has been started **once** on PostgreSQL to create the schema, then run the migration tool.
> If you run LNbits on SQLite and plan to scale, migrate to Postgres. Ensure Postgres is installed and your LNbits instance has run **once** on Postgres to create schema.

```sh
# STOP LNbits

# Set DB connection in .env
# postgres://<user>:<password>@<host>/<database>
LNBITS_DATABASE_URL="postgres://postgres:postgres@localhost/lnbits"
# save and exit

# START LNbits once, then STOP
poetry run python tools/conv.py
# or
make migration
```

Launch LNbits again and verify everything works.

---

### Reverse proxy with automatic HTTPS using Caddy

Use Caddy to expose LNbits over a domain with HTTPS.

1. **DNS**: Point your domain’s `A` record to your server IP.
2. **Install Caddy**: [https://caddyserver.com/docs/install#debian-ubuntu-raspbian](https://caddyserver.com/docs/install#debian-ubuntu-raspbian)

Stop any running Caddy:

```sh
sudo caddy stop
```

Create a **Caddyfile**:

```sh
sudo nano Caddyfile
```

Example (LNbits on port `5000`):

```caddy
yourdomain.com {
  reverse_proxy 0.0.0.0:5000 {
    header_up X-Forwarded-Host yourdomain.com
  }
}
```

Save & exit (`CTRL + x`), then:

```sh
sudo caddy start
```

### Running behind an Apache2 reverse proxy over HTTPS

Install Apache2 and enable modules:

```sh
apt-get install apache2 certbot
a2enmod headers ssl proxy proxy_http
```

Create a LetsEncrypt certificate:

```sh
certbot certonly --webroot --agree-tos --non-interactive --webroot-path /var/www/html -d lnbits.org
```

Create `/etc/apache2/sites-enabled/lnbits.conf`:

```apache
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
```

Restart Apache:

```sh
service apache2 restart
```

### Running behind an Nginx reverse proxy over HTTPS

Install nginx:

```sh
apt-get install nginx certbot
```

Create a LetsEncrypt certificate:

```sh
certbot certonly --nginx --agree-tos -d lnbits.org
```

Create `/etc/nginx/sites-enabled/lnbits.org`:

```nginx
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
```

Restart nginx:

```sh
service nginx restart
```

### Using https without reverse proxy

> **Warning:** Self‑signed certificates are **not trusted** by browsers. Expect a warning page. This method is best for **development** or **local network** use.
> You can run LNbits via HTTPS without additional software (useful for development or LAN). Create a self‑signed certificate with **mkcert** or `openssl`.

**Install mkcert (Ubuntu)**

```sh
sudo apt install libnss3-tools
curl -JLO "https://dl.filippo.io/mkcert/latest?for=linux/amd64"
chmod +x mkcert-v*-linux-amd64
sudo cp mkcert-v*-linux-amd64 /usr/local/bin/mkcert
```

**Create certificate**

```sh
# OpenSSL (creates key.pem and cert.pem)
openssl req -new -newkey rsa:4096 -x509 -sha256 -days 3650 -nodes -out cert.pem -keyout key.pem

# or mkcert (add local IP if needed)
mkcert localhost 127.0.0.1 ::1
```

**Start with TLS**

```sh
poetry run uvicorn lnbits.__main__:app --host 0.0.0.0 --port 5000 --ssl-keyfile ./key.pem --ssl-certfile ./cert.pem
```

### LNbits running on Umbrel behind Tor

If you run LNbits on Umbrel but want clearnet access, see this community guide by *Uxellodunum*:
[https://community.getumbrel.com/t/guide-lnbits-without-tor/604](https://community.getumbrel.com/t/guide-lnbits-without-tor/604)

---

## Service Management

### LNbits as a systemd service

> **Tip:** Use `which poetry` to find the Poetry binary path. Ensure `WorkingDirectory` matches your LNbits folder, and run as a dedicated **service user** (e.g., `lnbits`).
> Create `/etc/systemd/system/lnbits.service`:

```ini
# Systemd unit for lnbits
# /etc/systemd/system/lnbits.service

[Unit]
Description=LNbits
# Optional: ensure lnbits starts after your backend
#Wants=lnd.service
#After=lnd.service

[Service]
# Adjust paths for your environment
WorkingDirectory=/home/lnbits/lnbits
ExecStart=/home/lnbits/.local/bin/poetry run lnbits
User=lnbits
Restart=always
TimeoutSec=120
RestartSec=30
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Enable and start:

```sh
sudo systemctl enable lnbits.service
sudo systemctl start lnbits.service
```

---

## Troubleshooting

> **Tip:** If `secp256k1` fails to build with Poetry, add build helpers: `poetry add setuptools wheel`. Ensure system build tools are installed (see below).
> These packages often help on Debian/Ubuntu:

```sh
sudo apt install pkg-config libffi-dev libpq-dev

# build essentials for debian/ubuntu
sudo apt install python3.10-dev gcc build-essential

# if the secp256k1 build fails (Poetry)
poetry add setuptools wheel
```

---

## FreeBSD notes

Issue with `secp256k1 0.14.0` on FreeBSD (thanks @GitKalle):

1. Install `py311-secp256k1` with `pkg install py311-secp256k1`
2. Change version in `pyproject.toml` from `0.14.0` to `0.13.2`
3. Regenerate lock file: `poetry lock`
4. Follow the Poetry install instructions above


## Powered by LNbits 

LNbits empowers everyone with modular, open-source tools for building Bitcoin-based systems — fast, free, and extendable. 

[![Visit LNbits Shop](https://img.shields.io/badge/Visit-LNbits%20Shop-7C3AED?logo=shopping-cart\&logoColor=white\&labelColor=5B21B6)](https://shop.lnbits.com/) [![Try myLNbits SaaS](https://img.shields.io/badge/Try-myLNbits%20SaaS-2563EB?logo=lightning\&logoColor=white\&labelColor=1E40AF)](https://my.lnbits.com/login) [![Read LNbits News](https://img.shields.io/badge/Read-LNbits%20News-F97316?logo=rss\&logoColor=white\&labelColor=C2410C)](https://news.lnbits.com/) [![Explore LNbits Extensions](https://img.shields.io/badge/Explore-LNbits%20Extensions-10B981?logo=puzzle-piece\&logoColor=white\&labelColor=065F46)](https://extensions.lnbits.com/) 

If you like this project [send some tip love](https://demo.lnbits.com/lnurlp/link/fH59GD)!
