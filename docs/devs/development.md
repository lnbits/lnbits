---
layout: default
title: For developers
nav_order: 4
has_children: true
---


For developers
==============

Thanks for contributing :)


Tests
=====

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

pre-commit hooks
================

LNbits includes [pre-commit](https://pre-commit.com) hooks that can be run locally and via a GitHub action.

Enable the hook:
```bash
make install-pre-commit-hook
```

This will install a hook to your to `.git/hooks/pre-commit` and run on each commit. Note that git auto runs the hooks on staged files only.

To run manually:
```bash
make pre-commit
```
This will run on **all** files in the folder that are not excluded.

To disable the hook:
```bash
pre-commit uninstall
```

If the hook fails during a commit, the commit will not be executed. Pre-commit will auto fix formatting issues or print the location of the errors.


### Included hooks
The config can be viewed in the `.pre-commit-config.yaml` file. More hooks are [available](https://pre-commit.com/hooks.html) and can be enabled upon request.

The pre-commit runs the following hooks for us:
* some hooks included in pre-commit
* black
* isort
* prettier
* mypy
