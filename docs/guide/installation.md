---
layout: default
title: Basic installation
nav_order: 2
---


Basic installation
==================

Download this repo and install the dependencies:

```sh
git clone https://github.com/lnbits/lnbits.git
cd lnbits/
# ensure you have virtualenv installed, on debian/ubuntu 'apt install python3-venv' should work
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env
mkdir data
./venv/bin/quart assets
./venv/bin/quart migrate
./venv/bin/hypercorn -k trio --bind 0.0.0.0:5000 'lnbits.app:create_app()'
```

Now you can visit your LNbits at http://localhost:5000/.

Now modify the `.env` file with any settings you prefer and add a proper [funding source](./wallets.md) by modifying the value of `LNBITS_BACKEND_WALLET_CLASS` and providing the extra information and credentials related to the chosen funding source.

Then you can restart it and it will be using the new settings.

You might also need to install additional packages or perform additional setup steps, depending on the chosen backend. See [the short guide](./wallets.md) on each different funding source.

Docker installation
===================

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
