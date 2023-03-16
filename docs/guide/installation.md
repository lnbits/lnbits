---
layout: default
title: Basic installation
nav_order: 2
---

# Basic installation

You can choose between four package managers, `poetry` and `nix`

By default, LNbits will use SQLite as its database. You can also use PostgreSQL which is recommended for applications with a high load (see guide below).

## Option 1 (recommended): poetry

If you have problems installing LNbits using these instructions, please have a look at the [Troubleshooting](#troubleshooting) section.

```sh
git clone https://github.com/lnbits/lnbits.git
cd lnbits

# for making sure python 3.9 is installed, skip if installed. To check your installed version: python3 --version
sudo apt update
sudo apt install software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.9 python3.9-distutils

curl -sSL https://install.python-poetry.org | python3 -
# Once the above poetry install is completed, use the installation path printed to terminal and replace in the following command
export PATH="/home/user/.local/bin:$PATH"
# Next command, you can exchange with python3.10 or newer versions.
# Identify your version with python3 --version and specify in the next line
# command is only needed when your default python is not ^3.9 or ^3.10
poetry env use python3.9
poetry install --only main

mkdir data
cp .env.example .env
# set funding source amongst other options
nano .env
```

#### Running the server

```sh
poetry run lnbits
# To change port/host pass 'poetry run lnbits --port 9000 --host 0.0.0.0'
# adding --debug in the start-up command above to help your troubleshooting and generate a more verbose output
# Note that you have to add the line DEBUG=true in your .env file, too.
```
#### Updating the server

```
cd lnbits
# Stop LNbits with `ctrl + x`
git pull
# Keep your poetry install up to date, this can be done with `poetry self update`
poetry install --only main
# Start LNbits with `poetry run lnbits`
```

## Option 2: Nix

> note: currently not supported while we make some architectural changes on the path to leave beta

```sh
git clone https://github.com/lnbits/lnbits.git
cd lnbits
# Modern debian distros usually include Nix, however you can install with:
# 'sh <(curl -L https://nixos.org/nix/install) --daemon', or use setup here https://nixos.org/download.html#nix-verify-installation

nix build .#lnbits
mkdir data

```

#### Running the server

```sh
# .env variables are currently passed when running
LNBITS_DATA_FOLDER=data LNBITS_BACKEND_WALLET_CLASS=LNbitsWallet LNBITS_ENDPOINT=https://legend.lnbits.com LNBITS_KEY=7b1a78d6c78f48b09a202f2dcb2d22eb ./result/bin/lnbits --port 9000
```


## Option 3: Docker

use latest version from docker hub
```sh
docker pull lnbitsdocker/lnbits-legend
wget https://raw.githubusercontent.com/lnbits/lnbits/main/.env.example -O .env
mkdir data
docker run --detach --publish 5000:5000 --name lnbits --volume ${PWD}/.env:/app/.env --volume ${PWD}/data/:/app/data lnbitsdocker/lnbits-legend
```
build the image yourself
```sh
git clone https://github.com/lnbits/lnbits.git
cd lnbits
docker build -t lnbitsdocker/lnbits-legend .
cp .env.example .env
mkdir data
docker run --detach --publish 5000:5000 --name lnbits --volume ${PWD}/.env:/app/.env --volume ${PWD}/data/:/app/data lnbitsdocker/lnbits-legend
```

## Option 4: Fly.io

Fly.io is a docker container hosting platform that has a generous free tier. You can host LNbits for free on Fly.io for personal use.

First, sign up for an account at [Fly.io](https://fly.io) (no credit card required).

Then, install the Fly.io CLI onto your device [here](https://fly.io/docs/getting-started/installing-flyctl/).

After install is complete, the command will output a command you should copy/paste/run to get `fly` into your `$PATH`. Something like:

```
flyctl was installed successfully to /home/ubuntu/.fly/bin/flyctl
Manually add the directory to your $HOME/.bash_profile (or similar)
  export FLYCTL_INSTALL="/home/ubuntu/.fly"
  export PATH="$FLYCTL_INSTALL/bin:$PATH"
```

You can either run those commands, then `source ~/.bash_profile` or, if you don't, you'll have to call Fly from `~/.fly/bin/flyctl`.

Once installed, run the following commands.

```
git clone https://github.com/lnbits/lnbits.git
cd lnbits
fly auth login
[complete login process]
fly launch
```

You'll be prompted to enter an app name, region, postgres (choose no), deploy now (choose no).

You'll now find a file in the directory called `fly.toml`. Open that file and modify/add the following settings.

Note: Be sure to replace `${PUT_YOUR_LNBITS_ENV_VARS_HERE}` with all relevant environment variables in `.env` or `.env.example`. Environment variable strings should be quoted here, so if in `.env` you have `LNBITS_ENDPOINT=https://legend.lnbits.com` in `fly.toml` you should have `LNBITS_ENDPOINT="https://legend.lnbits.com"`.

Note: Don't enter secret environment variables here. Fly.io offers secrets (via the `fly secrets` command) that are exposed as environment variables in your runtime. So, for example, if using the LND_REST funding source, you can run `fly secrets set LND_REST_MACAROON=<hex_macaroon_data>`.

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
sudo apt install python3.9-dev gcc build-essential

# if the secp256k1 build fails:
# if you used poetry
poetry add setuptools wheel
```

#### Poetry

If your Poetry version is older than 1.2, for `poetry install`, ignore the `--only main` flag.

### Optional: PostgreSQL database

If you want to use LNbits at scale, we recommend using PostgreSQL as the backend database. Install Postgres and setup a database for LNbits:

```sh
# on debian/ubuntu 'sudo apt-get -y install postgresql'
# or follow instructions at https://www.postgresql.org/download/linux/

# Postgres doesn't have a default password, so we'll create one.
sudo -i -u postgres
psql
# on psql
ALTER USER postgres PASSWORD 'myPassword'; # choose whatever password you want
\q
# on postgres user
createdb lnbits
exit
```

You need to edit the `.env` file.

```sh
# add the database connection string to .env 'nano .env' LNBITS_DATABASE_URL=
# postgres://<user>:<myPassword>@<host>:<port>/<lnbits> - alter line bellow with your user, password and db name
LNBITS_DATABASE_URL="postgres://postgres:postgres@localhost:5432/lnbits"
# save and exit
```

# Using LNbits

Now you can visit your LNbits at http://localhost:5000/.

Now modify the `.env` file with any settings you prefer and add a proper [funding source](./wallets.md) by modifying the value of `LNBITS_BACKEND_WALLET_CLASS` and providing the extra information and credentials related to the chosen funding source.

Then you can restart it and it will be using the new settings.

You might also need to install additional packages or perform additional setup steps, depending on the chosen backend. See [the short guide](./wallets.md) on each different funding source.

Take a look at [Polar](https://lightningpolar.com/) for an excellent way of spinning up a Lightning Network dev environment.



# Additional guides

## SQLite to PostgreSQL migration
If you already have LNbits installed and running, on an SQLite database, we **highly** recommend you migrate to postgres if you are planning to run LNbits on scale.

There's a script included that can do the migration easy. You should have Postgres already installed and there should be a password for the user (see Postgres install guide above). Additionally, your LNbits instance should run once on postgres to implement the database schema before the migration works:

```sh
# STOP LNbits

# add the database connection string to .env 'nano .env' LNBITS_DATABASE_URL=
# postgres://<user>:<password>@<host>/<database> - alter line bellow with your user, password and db name
LNBITS_DATABASE_URL="postgres://postgres:postgres@localhost/lnbits"
# save and exit

# START LNbits
# STOP LNbits
poetry run python tools/conv.py
# or
make migration
```

Hopefully, everything works and get migrated... Launch LNbits again and check if everything is working properly.


## LNbits as a systemd service

Systemd is great for taking care of your LNbits instance. It will start it on boot and restart it in case it crashes. If you want to run LNbits as a systemd service on your Debian/Ubuntu/Raspbian server, create a file at `/etc/systemd/system/lnbits.service` with the following content:

```
# Systemd unit for lnbits
# /etc/systemd/system/lnbits.service

[Unit]
Description=LNbits
# you can uncomment these lines if you know what you're doing
# it will make sure that lnbits starts after lnd (replace with your own backend service)
#Wants=lnd.service
#After=lnd.service

[Service]
# replace with the absolute path of your lnbits installation
WorkingDirectory=/home/lnbits/lnbits
# same here. run `which poetry` if you can't find the poetry binary
ExecStart=/home/lnbits/.local/bin/poetry run lnbits
# replace with the user that you're running lnbits on
User=lnbits
Restart=always
TimeoutSec=120
RestartSec=30
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Save the file and run the following commands:

```sh
sudo systemctl enable lnbits.service
sudo systemctl start lnbits.service
```
## Reverse proxy with automatic https using Caddy

Use Caddy to make your LNbits install accessible over clearnet with a domain and https cert.

Point your domain at the IP of the server you're running LNbits on, by making an `A` record.

Install Caddy on the server
https://caddyserver.com/docs/install#debian-ubuntu-raspbian

```
sudo caddy stop
```
Create a Caddyfile
```
sudo nano Caddyfile
```
Assuming your LNbits is running on port `5000` add:
```
yourdomain.com {
  handle /api/v1/payments/sse* {
    reverse_proxy 0.0.0.0:5000 {
      header_up X-Forwarded-Host yourdomain.com
      transport http {
         keepalive off
         compression off
      }
    }
  }
  reverse_proxy 0.0.0.0:5000 {
    header_up X-Forwarded-Host yourdomain.com
  }
}
```
Save and exit `CTRL + x`
```
sudo caddy start
```

## Running behind an apache2 reverse proxy over https
Install apache2 and enable apache2 mods
```sh
apt-get install apache2 certbot
a2enmod headers ssl proxy proxy-http
```
create a ssl certificate with letsencrypt
```sh
certbot certonly --webroot --agree-tos --text --non-interactive --webroot-path /var/www/html -d lnbits.org
```
create a apache2 vhost at: /etc/apache2/sites-enabled/lnbits.conf
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
restart apache2
```sh
service restart apache2
```


## Using https without reverse proxy
The most common way of using LNbits via https is to use a reverse proxy such as Caddy, nginx, or ngriok. However, you can also run LNbits via https without additional software. This is useful for development purposes or if you want to use LNbits in your local network.

We have to create a self-signed certificate using `mkcert`. Note that this certificate is not "trusted" by most browsers but that's fine (since you know that you have created it) and encryption is always better than clear text.

#### Install mkcert
You can find the install instructions for `mkcert` [here](https://github.com/FiloSottile/mkcert).

Install mkcert on Ubuntu:
```sh
sudo apt install libnss3-tools
curl -JLO "https://dl.filippo.io/mkcert/latest?for=linux/amd64"
chmod +x mkcert-v*-linux-amd64
sudo cp mkcert-v*-linux-amd64 /usr/local/bin/mkcert
```
#### Create certificate
To create a certificate, first `cd` into your LNbits folder and execute the following command on Linux:
```sh
openssl req -new -newkey rsa:4096 -x509 -sha256 -days 3650 -nodes -out cert.pem -keyout key.pem
```
This will create two new files (`key.pem` and `cert.pem `).

Alternatively, you can use mkcert ([more info](https://kifarunix.com/how-to-create-self-signed-ssl-certificate-with-mkcert-on-ubuntu-18-04/)):
```sh
# add your local IP (192.x.x.x) as well if you want to use it in your local network
mkcert localhost 127.0.0.1 ::1
```

You can then pass the certificate files to uvicorn when you start LNbits:

```sh
poetry run uvicorn lnbits.__main__:app --host 0.0.0.0 --port 5000 --ssl-keyfile ./key.pem --ssl-certfile ./cert.pem
```


## LNbits running on Umbrel behind Tor

If you want to run LNbits on your Umbrel but want it to be reached through clearnet, _Uxellodunum_ made an extensive [guide](https://community.getumbrel.com/t/guide-lnbits-without-tor/604) on how to do it.

## Docker installation

To install using docker you first need to build the docker image as:

```
git clone https://github.com/lnbits/lnbits.git
cd lnbits
docker build -t lnbits-legend .
```

You can launch the docker in a different directory, but make sure to copy `.env.example` from lnbits there

```
cp <lnbits_repo>/.env.example .env
```

and change the configuration in `.env` as required.

Then create the data directory
```
mkdir data
```

Then the image can be run as:

```
docker run --detach --publish 5000:5000 --name lnbits-legend -e "LNBITS_BACKEND_WALLET_CLASS='FakeWallet'" --volume ${PWD}/.env:/app/.env --volume ${PWD}/data/:/app/data lnbits-legend
```

Finally you can access your lnbits on your machine at port 5000.
