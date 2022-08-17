---
layout: default
parent: For developers
title: Making extensions
nav_order: 2
---


Making extensions
=================

Start off by copying the example extension in `lnbits/extensions/example` into your own:
```sh
cp lnbits/extensions/example lnbits/extensions/mysuperplugin -r # Let's not use dashes or anything; it doesn't like those.
cd lnbits/extensions/mysuperplugin
find . -type f -print0 | xargs -0 sed -i 's/example/mysuperplugin/g' # Change all occurrences of 'example' to your plugin name 'mysuperplugin'.
```
- if you are on macOS and having difficulty with 'sed', consider `brew install gnu-sed` and use 'gsed', without -0 option after xargs.

Going over the example extension's structure:
* views_api.py: This is where your public API would go. It will be exposed at "$DOMAIN/$PLUGIN/$ROUTE". For example: https://lnbits.com/mysuperplugin/api/v1/tools.
* views.py: The `/` path will show up as your plugin's home page in lnbits' UI. Other pages you can define yourself. The `templates` folder should explain itself in relation to this.
* migrations.py: Create database tables for your plugin. They'll be created automatically when you start lnbits.

... This document is a work-in-progress. Send pull requests if you get stuck, so others don't.


Adding new dependencies
-----------------------

If for some reason your extensions needs a new python package to work, you can add a new package using `venv`, or `poerty`:

```sh
$ poetry add <package>
# or
$ ./venv/bin/pip install <package>
```

**But we need an extra step to make sure LNbits doesn't break in production.**
Dependencies need to be added to `pyproject.toml` and `requirements.txt`, then tested by running on `venv` and `poetry`.
`nix` compatability can be tested with `nix build .#checks.x86_64-linux.vmTest`.


SQLite to PostgreSQL migration
-----------------------

LNbits currently supports SQLite and PostgreSQL databases. There is a migration script `tools/conv.py` that helps users migrate from SQLite to PostgreSQL. This script also copies all extension databases to the new backend.

### Adding mock data to `mock_data.zip`

`mock_data.zip` contains a few lines of sample SQLite data and is used in automated GitHub test to see whether your migration in `conv.py` works. Run your extension and save a few lines of data into a SQLite `your_extension.sqlite3` file. Unzip `tests/data/mock_data.zip`, add `your_extension.sqlite3`, updated `database.sqlite3` and zip it again. Add the updated `mock_data.zip` to your PR.

### running migration locally
you will need a running postgres database

#### create lnbits user for migration database
```console
sudo su - postgres -c "psql -c 'CREATE ROLE lnbits LOGIN PASSWORD 'lnbits';'"
```
#### create migration database
```console
sudo su - postgres -c "psql -c 'CREATE DATABASE migration;'"
```
#### run the migration
```console
make test-migration
```
sudo su - postgres -c "psql -c 'CREATE ROLE lnbits LOGIN PASSWORD 'lnbits';'"
#### clean migration database afterwards, fails if you try again
```console
sudo su - postgres -c "psql -c 'DROP DATABASE IF EXISTS migration;'"
```
