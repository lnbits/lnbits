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
# on debian based installations like ubuntu, you may have to intall global python packages. Try sudo apt install python3-venv -y
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env
./venv/bin/quart assets
./venv/bin/quart migrate
./venv/bin/hypercorn -k trio --bind 0.0.0.0:5000 'lnbits.app:create_app()'
```

No you can visit your LNbits at http://localhost:5000/.

Now modify the `.env` file with any settings you prefer and add a proper [funding source](./wallets.md) by modifying the value of `LNBITS_BACKEND_WALLET_CLASS` and providing the extra information and credentials related to the chosen funding source.

Then you can run restart it and it will be using the new settings.

You might also need to install additional packages or perform additional setup steps, depending on the chosen backend. See [the short guide](./wallets.md) on each different funding source.
