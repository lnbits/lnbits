---
layout: default
title: Basic installation
nav_order: 2
---

# Basic installation
Install Postgres and setup a database for LNbits:

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

Download this repo and install the dependencies:

```sh
git clone https://github.com/lnbits/lnbits-legend.git
cd lnbits-legend/
# ensure you have virtualenv installed, on debian/ubuntu 'apt install python3-venv' should work
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env
# add the database connection string to .env 'nano .env' LNBITS_DATABASE_URL=
# postgres://<user>:<myPassword>@<host>/<lnbits> - alter line bellow with your user, password and db name
LNBITS_DATABASE_URL="postgres://postgres:postgres@localhost/lnbits"
# save and exit
./venv/bin/uvicorn lnbits.__main__:app --port 5000
```

Now you can visit your LNbits at http://localhost:5000/. 

Now modify the `.env` file with any settings you prefer and add a proper [funding source](./wallets.md) by modifying the value of `LNBITS_BACKEND_WALLET_CLASS` and providing the extra information and credentials related to the chosen funding source.

Then you can restart it and it will be using the new settings.

You might also need to install additional packages or perform additional setup steps, depending on the chosen backend. See [the short guide](./wallets.md) on each different funding source.

## Important note
If you already have LNbits installed and running, on an SQLite database, we **HIGHLY** recommend you migrate to postgres!

There's a script included that can do the migration easy. You should have Postgres already installed and there should be a password for the user, check the guide above. Additionally, your lnbits instance should run once on postgres to implement the database schema before the migration works:

```sh
# STOP LNbits

# add the database connection string to .env 'nano .env' LNBITS_DATABASE_URL=
# postgres://<user>:<password>@<host>/<database> - alter line bellow with your user, password and db name
LNBITS_DATABASE_URL="postgres://postgres:postgres@localhost/lnbits"
# save and exit

# START LNbits
# STOP LNbits
# on the LNBits folder, locate and edit 'conv.py' with the relevant credentials
python3 conv.py
```

Hopefully, everything works and get migrated... Launch LNbits again and check if everything is working properly.



# Additional guides

### LNbits as a systemd service

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

### LNbits running on Umbrel behind Tor

If you want to run LNbits on your Umbrel but want it to be reached through clearnet, _Uxellodunum_ made an extensive [guide](https://community.getumbrel.com/t/guide-lnbits-without-tor/604) on how to do it.

### Docker installation

Arguably simplest and most reproducible way to install lnbits on your computer is to use docker-compose based setup. This gets lnbits up and running in minutes by running this commands:

```
git clone https://github.com/lnbits/lnbits.git
cd lnbits/
cp .env.example .env
```
edit the .env file and run
```
docker-compose build
docker-compose up --detach
```

The docker-compose installation provides postgres database service (requires corresponding adjustment of the .env file). 

To access the service you can use your http://localhost:5000/


A TOR service allows you (or anyone else!) to connect to lnbits through the TOR network (can be prevented by removing tor-node in docker-compose.yml file). 

To find out your TOR hidden service address run:

```
docker-compose exec tor-node cat /var/lib/tor/hidden_service/hostname
```
and connect through the [TOR browser](https://www.torproject.org/download/) or TOR enabled wallet.


# Additional guides

## LNbits running on Umbrel behind Tor

If you want to run LNbits on your Umbrel but want it to be reached through clearnet, _Uxellodunum_ made an extensive [guide](https://community.getumbrel.com/t/guide-lnbits-without-tor/604) on how to do it.
