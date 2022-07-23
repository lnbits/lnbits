---
layout: default
title: Basic installation
nav_order: 2
---



# Basic installation

You can choose between two python package managers, `venv` and `pipenv`. Both are fine but if you don't know what you're doing, just go for the first option.

By default, LNbits will use SQLite as its database. You can also use PostgreSQL which is recommended for applications with a high load (see guide below).

## Option 1: pipenv

You can also use Pipenv to manage your python packages. 

```sh
git clone https://github.com/lnbits/lnbits-legend.git
cd lnbits-legend/

sudo apt update && sudo apt install -y pipenv
pipenv install --dev
# pipenv --python 3.9 install --dev (if you wish to use a version of Python higher than 3.7)
pipenv shell
# pipenv --python 3.9 shell (if you wish to use a version of Python higher than 3.7)

# If any of the modules fails to install, try checking and upgrading your setupTool module
# pip install -U setuptools wheel

# install libffi/libpq in case "pipenv install" fails
# sudo apt-get install -y libffi-dev libpq-dev

 mkdir data && cp .env.example .env
``` 

#### Running the server
    
```sh
pipenv run python -m uvicorn lnbits.__main__:app --port 5000 --host 0.0.0.0
```

Add the flag `--reload` for development (includes hot-reload).


## Option 2: venv

Download this repo and install the dependencies:

```sh
git clone https://github.com/lnbits/lnbits-legend.git
cd lnbits-legend/
# ensure you have virtualenv installed, on debian/ubuntu 'apt install python3-venv'
python3 -m venv venv
# If you have problems here, try `sudo apt install -y pkg-config libpq-dev`
./venv/bin/pip install -r requirements.txt
# create the data folder and the .env file
mkdir data && cp .env.example .env
```

#### Running the server

```sh
./venv/bin/uvicorn lnbits.__main__:app --port 5000
```

If you want to host LNbits on the internet, run with the option `--host 0.0.0.0`. 

### Troubleshooting

Problems installing? These commands have helped us install LNbits. 

```sh
sudo apt install pkg-config libffi-dev libpq-dev

# if the secp256k1 build fails:
# if you used pipenv (option 1)
pipenv install setuptools wheel 
# if you used venv (option 2)
./venv/bin/pip install setuptools wheel 
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
To create a certificate, first `cd` into your lnbits folder and execute the following command ([more info](https://kifarunix.com/how-to-create-self-signed-ssl-certificate-with-mkcert-on-ubuntu-18-04/))
```sh
# add your local IP (192.x.x.x) as well if you want to use it in your local network
mkcert localhost 127.0.0.1 ::1 
```

This will create two new files (`localhost-key.pem` and `localhost.pem `) which you can then pass to uvicorn when you start LNbits:

```sh
./venv/bin/uvicorn lnbits.__main__:app --host 0.0.0.0 --port 5000 --ssl-keyfile ./localhost-key.pem --ssl-certfile ./localhost.pem 
```


## LNbits running on Umbrel behind Tor

If you want to run LNbits on your Umbrel but want it to be reached through clearnet, _Uxellodunum_ made an extensive [guide](https://community.getumbrel.com/t/guide-lnbits-without-tor/604) on how to do it.

## Docker installation

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
