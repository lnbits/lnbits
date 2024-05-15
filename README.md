<picture >
  <source media="(prefers-color-scheme: dark)" srcset="https://i.imgur.com/QE6SIrs.png"  style="width:300px">
  <img src="https://i.imgur.com/fyKPgVT.png" style="width:300px">
</picture>

![phase: beta](https://img.shields.io/badge/phase-beta-C41E3A) [![license-badge]](LICENSE) [![docs-badge]][docs] ![PRs: welcome](https://img.shields.io/badge/PRs-Welcome-08A04B) [<img src="https://img.shields.io/badge/community_chat-Telegram-24A1DE">](https://t.me/lnbits) [<img src="https://img.shields.io/badge/supported_by-%3E__OpenSats-f97316">](https://opensats.org)
![Lightning network wallet](https://i.imgur.com/DeIiO0y.png)

# The world's most powerful suite of bitcoin tools.

## Run for yourself, for others, or as part of a stack.

LNbits is beta, for responsible disclosure of any concerns please contact an admin in the community chat.

LNbits is a Python server that sits on top of any funding source. It can be used as:

- Accounts system to mitigate the risk of exposing applications to your full balance via unique API keys for each wallet
- Extendable platform for exploring Lightning network functionality via the LNbits extension framework
- Part of a development stack via LNbits API
- Fallback wallet for the LNURL scheme
- Instant wallet for LN demonstrations

LNbits can run on top of almost all Lightning funding sources.

See [LNbits manual](https://docs.lnbits.org/guide/wallets.html) for more detailed documentation about each funding source.

Checkout the LNbits [YouTube](https://www.youtube.com/playlist?list=PLPj3KCksGbSYG0ciIQUWJru1dWstPHshe) video series.

LNbits is inspired by all the great work of [opennode.com](https://www.opennode.com/), and in particular [lnpay.co](https://lnpay.co/). Both work as funding sources for LNbits.

## Running LNbits

Test on our demo server [demo.lnbits.com](https://demo.lnbits.com), or on [lnbits.com](https://lnbits.com) software as a service, where you can spin up an LNbits instance for 21sats per hr.

See the [install guide](https://github.com/lnbits/lnbits/blob/main/docs/guide/installation.md) for details on installation and setup.

## LNbits account system

LNbits is packaged with tools to help manage funds, such as a table of transactions, line chart of spending, export to csv. Each wallet also comes with its own API keys, to help partition the exposure of your funding source.

<img src="https://i.imgur.com/w8jdGpF.png" style="width:800px">

## LNbits extension universe

Extend YOUR LNbits to meet YOUR needs.

All non-core features are installed as extensions, reducing your code base and making your LNbits unique to you. Extend your LNbits install in any direction, and even create and share your own extensions.

<img src="https://i.imgur.com/aEBpwJF.png" style="width:800px">

## LNbits API

LNbits has a powerful API, many projects use LNbits to do the heavy lifting for their bitcoin/lightning services.

<img src="https://i.imgur.com/V742sb9.png" style="width:800px">

## LNbits node manager

LNbits comes packaged with a light node management UI, to make running your node that much easier.

<img src="https://i.imgur.com/TYqIK60.png" style="width:800px">

## LNbits across all your devices

As well as working great in a browser, LNbits has native IoS and Android apps as well as a chrome extension. So you can enjoy the same UI across ALL your devices.

<img src="https://i.imgur.com/J96EbRf.png" style="width:800px">

## Tip us

If you like this project [send some tip love](https://demo.lnbits.com/lnurlp/link/fH59GD)!

[docs]: https://github.com/lnbits/lnbits/wiki
[docs-badge]: https://img.shields.io/badge/docs-lnbits.org-673ab7.svg
[github-mypy]: https://github.com/lnbits/lnbits/actions?query=workflow%3Amypy
[github-mypy-badge]: https://github.com/lnbits/lnbits/workflows/mypy/badge.svg
[github-tests]: https://github.com/lnbits/lnbits/actions?query=workflow%3Atests
[github-tests-badge]: https://github.com/lnbits/lnbits/workflows/tests/badge.svg
[codecov]: https://codecov.io/gh/lnbits/lnbits
[codecov-badge]: https://codecov.io/gh/lnbits/lnbits/branch/master/graph/badge.svg
[license-badge]: https://img.shields.io/badge/license-MIT-blue.svg
