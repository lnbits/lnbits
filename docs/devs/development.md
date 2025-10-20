---
layout: default
title: For developers
nav_order: 4
has_children: true
---

# For developers

Thanks for contributing :)

# Run

Follow the [Option 2 (recommended): UV](https://docs.lnbits.org/guide/installation.html)
guide to install uv and other dependencies.

Then you can start LNbits uvicorn server with:

```bash
uv run lnbits
```

Or you can use the following to start uvicorn with hot reloading enabled:

```bash
make dev
# or
uv run lnbits --reload
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
uv sync --all-extras --dev
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
make mypy
```

Run everything:

```bash
make all
```
