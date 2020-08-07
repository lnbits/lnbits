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
* migrations.py: Create database tables for your plugin. They'll be created when you run `pipenv run flask migrate`.

... This document is a work-in-progress. Send pull requests if you get stuck, so others don't.
