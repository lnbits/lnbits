---
layout: default
title: Basic installation
nav_order: 2
---


Basic installation
==================

Download this repo and install the dependencies:

```sh
$ git clone https://github.com/lnbits/lnbits.git
$ python3 -m venv .venv
$ source ./.venv/bin/activate
(.venv) $ pip install -r requirements.txt
```

You will need to set the variables in `.env.example`, and rename the file to `.env`.

Run the server:

```sh
(.venv) $ python -m lnbits
```

You might also need to install additional packages, depending on the [backend wallet](./wallets.md) you use.
E.g. when you want to use LND you have to run:

```sh
(.venv) $ pip install lnd-grpc
```
