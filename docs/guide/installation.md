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

There's a script included that can do the migration easy. You should have Postgres already installed and there should be a password for the user, check the guide above.

```sh
# STOP LNbits
# on the LNBits folder, locate and edit 'conv.py' with the relevant credentials
python3 conv.py

# add the database connection string to .env 'nano .env' LNBITS_DATABASE_URL=
# postgres://<user>:<password>@<host>/<database> - alter line bellow with your user, password and db name
LNBITS_DATABASE_URL="postgres://postgres:postgres@localhost/lnbits"
# save and exit
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
#Wants=lnd.service # you can uncomment these lines if you know what you're doing
#After=lnd.service # it will make sure that lnbits starts after lnd (replace with your own backend service)

[Service]
WorkingDirectory=/home/bitcoin/lnbits # replace with the absolute path of your lnbits installation
ExecStart=/home/bitcoin/lnbits/venv/bin/uvicorn lnbits.__main__:app --port 5000 # same here
User=bitcoin # replace with the user that you're running lnbits on
Restart=always
TimeoutSec=120
RestartSec=30
Environment=PYTHONUNBUFFERED=1 # this makes sure that you receive logs in real time

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

To install using docker you first need to build the docker image as:

```
git clone https://github.com/lnbits/lnbits.git
cd lnbits/ # ${PWD} referred as <lnbits_repo>
docker build -t lnbits .
```

You can launch the docker in a different directory, but make sure to copy `.env.example` from lnbits there

```
cp <lnbits_repo>/.env.example .env
```

and change the configuration in `.env` as required.

Then create the data directory for the user ID 1000, which is the user that runs the lnbits within the docker container.

```
mkdir data
sudo chown 1000:1000 ./data/
```

Then the image can be run as:

```
docker run --detach --publish 5000:5000 --name lnbits --volume ${PWD}/.env:/app/.env --volume ${PWD}/data/:/app/data lnbits
```

Finally you can access your lnbits on your machine at port 5000.

# Additional guides

## LNbits running on Umbrel behind Tor

If you want to run LNbits on your Umbrel but want it to be reached through clearnet, _Uxellodunum_ made an extensive [guide](https://community.getumbrel.com/t/guide-lnbits-without-tor/604) on how to do it.
