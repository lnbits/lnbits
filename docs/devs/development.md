---
layout: default
title: For developers
nav_order: 4
has_children: true
---

# For developers

Thanks for contributing :)

# Run

Follow the [Basic installation: Option 1 (recommended): poetry](https://docs.lnbits.org/guide/installation.html#option-1-recommended-poetry)
guide to install poetry and other dependencies.

Then you can start LNbits uvicorn server with:

```bash
poetry run lnbits
```

Or you can use the following to start uvicorn with hot reloading enabled:

```bash
make dev
# or
poetry run lnbits --reload
```

You might need the following extra dependencies on clean installation of Debian:

```
sudo apt install nodejs
sudo apt install npm
npm install
sudo apt-get install autoconf libtool libpg-dev
```

# Precommit hooks

This ensures that all commits adhere to the formatting and linting rules.

```bash
make install-pre-commit-hook
```

# Tests

This project has unit tests that help prevent regressions. Before you can run the tests, you must install a few dependencies:

```bash
poetry install
npm i
```

Then to run the tests:

```bash
make test
```

Run formatting:

```bash
make format
```

Run mypy checks:

```bash
poetry run mypy
```

Run everything:

```bash
make all
```
