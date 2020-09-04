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

Going over the example extension's structure:
* views_api.py: This is where your public API would go. It will be exposed at "$DOMAIN/$PLUGIN/$ROUTE". For example: https://lnbits.com/mysuperplugin/api/v1/tools.
* views.py: The `/` path will show up as your plugin's home page in lnbits' UI. Other pages you can define yourself. The `templates` folder should explain itself in relation to this.
* migrations.py: Create database tables for your plugin. They'll be created automatically when you start lnbits.

... This document is a work-in-progress. Send pull requests if you get stuck, so others don't.


Adding new dependencies
-----------------------

If for some reason your extensions needs a new python package to work, you can add a new package using Pipenv:

```sh
$ pipenv install new_package_name
```

This will create a new entry in the `Pipenv` file.
**But we need an extra step to make sure LNbits doesn't break in production.**
All tests and deployments should run against the `requirements.txt` file so every time a new package is added
it is necessary to run the Pipenv `lock` command and manually update the requirements file:

```sh
$ pipenv lock -r
```
