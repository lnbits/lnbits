---
layout: default
title: Basic installation
nav_order: 2
---

# Basic installation

You can choose between four package managers, `poetry`, `nix` and `venv`.

By default, LNbits will use SQLite as its database. You can also use PostgreSQL which is recommended for applications with a high load (see guide below).

## Option 1: poetry

```sh
git clone https://github.com/lnbits/lnbits-legend.git
cd lnbits-legend/

# for making sure python 3.9 is installed, skip if installed
sudo apt update
sudo apt install software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.9

curl -sSL https://install.python-poetry.org | python3 -
export PATH="/home/ubuntu/.local/bin:$PATH" # or whatever is suggested in the poetry install notes printed to terminal
poetry env use python3.9
poetry install --no-dev

mkdir data
cp .env.example .env
sudo nano .env # set funding source


```

#### Running the server

```sh
poetry run lnbits
# To change port/host pass 'poetry run lnbits --port 9000 --host 0.0.0.0'
```

## Option 2: Nix

```sh
git clone https://github.com/lnbits/lnbits-legend.git
cd lnbits-legend/
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

## Option 3: venv

```sh
git clone https://github.com/lnbits/lnbits-legend.git
cd lnbits-legend/
# ensure you have virtualenv installed, on debian/ubuntu 'apt install python3-venv'
python3 -m venv venv
# If you have problems here, try `sudo apt install -y pkg-config libpq-dev`
./venv/bin/pip install -r requirements.txt
# create the data folder and the .env file
mkdir data && cp .env.example .env
# build the static files
./venv/bin/python build.py
```

#### Running the server

```sh
./venv/bin/uvicorn lnbits.__main__:app --port 5000
```

If you want to host LNbits on the internet, run with the option `--host 0.0.0.0`.

## Option 4: Docker

```sh
git clone https://github.com/lnbits/lnbits-legend.git
cd lnbits-legend
docker build -t lnbits-legend .
cp .env.example .env
mkdir data
docker run --detach --publish 5000:5000 --name lnbits-legend --volume ${PWD}/.env:/app/.env --volume ${PWD}/data/:/app/data lnbits-legend
```

### Troubleshooting

Problems installing? These commands have helped us install LNbits.

```sh
sudo apt install pkg-config libffi-dev libpq-dev

# if the secp256k1 build fails:
# if you used venv
./venv/bin/pip install setuptools wheel
# if you used poetry
poetry add setuptools wheel
# build essentials for debian/ubuntu
sudo apt install python3-dev gcc build-essential
```

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
# postgres://<user>:<myPassword>@<host>/<lnbits> - alter line bellow with your user, password and db name
LNBITS_DATABASE_URL="postgres://postgres:postgres@localhost/lnbits"
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
# on the LNBits folder, locate and edit 'tools/conv.py' with the relevant credentials
python3 tools/conv.py
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
WorkingDirectory=/home/bitcoin/lnbits
# same here
ExecStart=/home/bitcoin/lnbits/venv/bin/uvicorn lnbits.__main__:app --port 5000
# replace with the user that you're running lnbits on
User=bitcoin
Restart=always
TimeoutSec=120
RestartSec=30
# this makes sure that you receive logs in real time
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Save the file and run the following commands:

```sh
sudo systemctl enable lnbits.service
sudo systemctl start lnbits.service
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

We have to create a self-signed certificate using `mkcert`. Note that this certiciate is not "trusted" by most browsers but that's fine (since you know that you have created it) and encryption is always better than clear text.

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
./venv/bin/uvicorn lnbits.__main__:app --host 0.0.0.0 --port 5000 --ssl-keyfile ./key.pem --ssl-certfile ./cert.pem
```


## LNbits running on Umbrel behind Tor

If you want to run LNbits on your Umbrel but want it to be reached through clearnet, _Uxellodunum_ made an extensive [guide](https://community.getumbrel.com/t/guide-lnbits-without-tor/604) on how to do it.

## Docker installation

To install using docker you first need to build the docker image as:

```
git clone https://github.com/lnbits/lnbits-legend.git
cd lnbits-legend
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
