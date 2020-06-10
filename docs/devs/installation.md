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

You will need to set the variables in `.env.example`, and rename the file to `.env`.

![Files](https://i.imgur.com/ri2zOe8.png)

You might also need to install additional packages, depending on the [backend wallets](../guide/wallets.md) you configured.
E.g. when you want to use LND you have to `pipenv install lnd-grpc`.

Take a look at [Polar](https://lightningpolar.com/) for an excellent way of spinning up a Lightning Network dev environment.

Running the server
------------------

LNbits uses [Flask](http://flask.pocoo.org/) as an application server.

```sh
$ pipenv run flask migrate
$ pipenv run flask run
```

There is an environment variable called `FLASK_ENV` that has to be set to `development`
if you want to run Flask in debug mode with autoreload

[pipenv]: https://pipenv.pypa.io/

Frontend
--------

The views are build using [Vue.js and Quasar](https://quasar.dev/start/how-to-use-vue).
