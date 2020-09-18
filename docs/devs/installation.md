---
layout: default
parent: For developers
title: Installation
nav_order: 1
---


Installation
============

Download this repo and install the dependencies.


Application dependencies
------------------------

The application uses [Pipenv][pipenv] to manage Python packages.
While in development, you will need to install all dependencies:

```sh
$ pipenv shell
$ pipenv install --dev
```

If you wish to use a version of Python higher than 3.7:

```sh
$ pipenv --python 3.8 install --dev
```

You will need to set the variables in `.env.example`, and rename the file to `.env`.

![Files](https://i.imgur.com/ri2zOe8.png)

You might also need to install additional packages, depending on the [backend wallet](../guide/wallets.md) you use.
E.g. when you want to use LND you have to `pipenv run pip install lnd-grpc`.

Take a look at [Polar][polar] for an excellent way of spinning up a Lightning Network dev environment.


Running the server
------------------

LNbits uses [Quart][quart] as an application server.

```sh
$ pipenv run python -m lnbits
```

Frontend
--------

The frontend uses [Vue.js and Quasar][quasar].


[quart]: https://pgjones.gitlab.io/
[pipenv]: https://pipenv.pypa.io/
[polar]: https://lightningpolar.com/
[quasar]: https://quasar.dev/start/how-to-use-vue
