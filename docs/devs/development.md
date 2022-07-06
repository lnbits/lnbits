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
./venv/bin/pip install pytest pytest-asyncio pytest-cov requests mock
```

Then to run the tests:
```bash
make test
```
