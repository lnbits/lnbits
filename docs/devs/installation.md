---
layout: default
parent: For developers
title: Installation
nav_order: 1
---

# Installation

This guide has been moved to the [installation guide](../guide/installation.md). 
To install the developer packages for running tests etc before pr'ing, use `./venv/bin/pip install pytest pytest-asyncio pytest-cov requests mock black mypy isort`.

## Notes:

* We recommend using <a href="https://caddyserver.com/docs/install#debian-ubuntu-raspbian">Caddy</a> for a reverse-proxy if you want to serve your install through a domain, alternatively you can use [ngrok](https://ngrok.com/).
* <a href="https://linuxize.com/post/how-to-use-linux-screen/#starting-linux-screen">Screen</a> works well if you want LNbits to continue running when you close your terminal session.
