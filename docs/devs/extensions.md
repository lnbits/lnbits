---
layout: default
parent: For developers
title: Making extensions
nav_order: 2
---

# Extension set up

Start off by creating a fork of the [example extension](https://github.com/lnbits/example) into own GitHub repository and rename the repository to `mysuperplugin`:

```sh
cd [my-working-folder]
git clone https://github.com/[my-user-name]/mysuperplugin.git --depth=1 # Let's not use dashes or anything; it doesn't like those.
cd mysuperplugin
rm -rf .git/
find . -type f -print0 | xargs -0 sed -i 's/example/mysuperplugin/g' # Change all occurrences of 'example' to your plugin name 'mysuperplugin'.
mv templates/example templates/mysuperplugin # Rename templates folder.
```

- if you are on macOS and having difficulty with 'sed', consider `brew install gnu-sed` and use 'gsed', without -0 option after xargs.

1. Edit `manifest.json` and change the organisation name to your GitHub username.
1. Push your changes to GitHub.
1. In GitHub create a new release for your extension repo. Tag the release with `0.0.1`
1. Copy the URL of the extension's raw `manifest.json` URL `https://raw.githubusercontent.com/[my-user-name]/mysuperplugin/master/manifest.json`
1. If you are using the LMNbits Admin UI, go to the Admin UI > Server > Extension Sources, click "Add", paste the URL, then click "Save"
1. If you are configuring LNbits via environment variables, add the URL to the .env file's `LNBITS_EXTENSIONS_MANIFESTS` variable. Restart the LNbits python process
1. You will now see your extension in the LNbits > Extensions list. Click "Enable" to enable it.
1. ...
1. Profit!!!

## Extension structure explained

- views_api.py: This is where your public API would go. It will be exposed at "$DOMAIN/$PLUGIN/$ROUTE". For example: https://lnbits.com/mysuperplugin/api/v1/tools.
- views.py: The `/` path will show up as your plugin's home page in lnbits' UI. Other pages you can define yourself. The `templates` folder should explain itself in relation to this.
- migrations.py: Create database tables for your plugin. They'll be created automatically when you start lnbits.

... This document is a work-in-progress. Send pull requests if you get stuck, so others don't.

## Adding new dependencies

DO NOT ADD NEW DEPENDENCIES. Try to use the dependencies that are available in `pyproject.toml`. Getting the LNbits project to accept a new dependency is time consuming and uncertain, and may result in your extension NOT being made available to others.

If for some reason your extensions must have a new python package to work, and its nees are not met in `pyproject.toml`, you can add a new package using `poerty` or `uv`:

**But we need an extra step to make sure LNbits doesn't break in production.**
Dependencies need to be added to `pyproject.toml`, then tested by running on `uv` and `poetry` compatibility can be tested with `nix build .#checks.x86_64-linux.vmTest`.

## SQLite to PostgreSQL migration

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
