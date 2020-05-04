---
layout: default
parent: For developers
title: Installation
nav_order: 1
---


Installation
============

LNbits uses [Flask](http://flask.pocoo.org/).


Application dependencies
------------------------

The application uses [Pipenv][pipenv] to manage Python packages.
While in development, you will need to install all dependencies (includes packages like `black` and `flake8`):

    $ pipenv shell
    $ pipenv install --dev


Running the server
------------------

    $ flask run

There is an environment variable called `FLASK_ENV` that has to be set to `development`
if you want to run Flask in debug mode with autoreload


[pipenv]: https://docs.pipenv.org/#install-pipenv-today
