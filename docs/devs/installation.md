---
layout: default
parent: For developers
title: Installation
nav_order: 1
---

# Installation

LNbits uses [Pipenv][pipenv] to manage Python packages.

```sh
git clone https://github.com/lnbits/lnbits-legend.git
cd lnbits-legend/

sudo apt-get install pipenv
pipenv shell
# pipenv --python 3.9 shell (if you wish to use a version of Python higher than 3.7)
pipenv install --dev
# pipenv --python 3.9 install --dev (if you wish to use a version of Python higher than 3.7)

# If any of the modules fails to install, try checking and upgrading your setupTool module
# pip install -U setuptools

# install libffi/libpq in case "pipenv install" fails
# sudo apt-get install -y libffi-dev libpq-dev
``` 
## Running the server

Create the data folder and edit the .env file:

    mkdir data
    cp .env.example .env
    sudo nano .env

To then run the server for development purposes (includes hot-reload), use:

    pipenv run python -m uvicorn lnbits.__main__:app --host 0.0.0.0  --reload
    
For production, use:

    pipenv run python -m uvicorn lnbits.__main__:app --host 0.0.0.0

You might also need to install additional packages, depending on the [backend wallet](../guide/wallets.md) you use.
E.g. when you want to use LND you have to `pipenv run pip install lndgrpc` and `pipenv run pip install purerpc`.

Take a look at [Polar][polar] for an excellent way of spinning up a Lightning Network dev environment.

**Notes**: 

* We reccomend using <a href="https://caddyserver.com/docs/install#debian-ubuntu-raspbian">Caddy</a> for a reverse-proxy if you want to serve your install through a domain, alternatively you can use [ngrok](https://ngrok.com/).
* <a href="https://linuxize.com/post/how-to-use-linux-screen/#starting-linux-screen">Screen</a> works well if you want LNbits to continue running when you close your terminal session.
