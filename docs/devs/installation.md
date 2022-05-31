---
layout: default
parent: For developers
title: Installation
nav_order: 1
---

# Installation

Download the latest stable release https://github.com/lnbits/lnbits/releases

## Application dependencies

The application uses [Pipenv][pipenv] to manage Python packages.
While in development, you will need to install all dependencies:

```sh
$ pipenv shell
$ pipenv install --dev
```

If any of the modules fails to install, try checking and upgrading your setupTool module.  
`pip install -U setuptools`

If you wish to use a version of Python higher than 3.7:

```sh
$ pipenv --python 3.8 install --dev
```

You will need to copy `.env.example` to `.env`, then set variables there.

![Files](https://i.imgur.com/ri2zOe8.png)

You might also need to install additional packages, depending on the [backend wallet](../guide/wallets.md) you use.
E.g. when you want to use LND you have to `pipenv run pip install lndgrpc` and `pipenv run pip install purerpc`.

Take a look at [Polar][polar] for an excellent way of spinning up a Lightning Network dev environment.

## Running the server

LNbits uses [Quart][quart] as an application server.
Before running the server for the first time, make sure to create the data folder:

```sh
$ mkdir data
```

To then run the server, use:

```sh
$ pipenv run python -m lnbits
```

**Note**: You'll need to use _https_ for some endpoints and/or extensions. You can use [ngrok](https://ngrok.com/) for that. Follow the installation instructions on the website and when it's all set you can run:

```sh
$ ./nrok http 5000
```

this will give you an _https_ tunnel for the _localhost_, use that URL for navigating to LNBits.

## Frontend

The frontend uses [Vue.js and Quasar][quasar].

[quart]: https://pgjones.gitlab.io/
[pipenv]: https://pipenv.pypa.io/
[polar]: https://lightningpolar.com/
[quasar]: https://quasar.dev/start/how-to-use-vue
