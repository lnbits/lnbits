# LNbits BETA

[![license-badge]](LICENSE)
[![docs-badge]][docs]

![Lightning network wallet](https://i.imgur.com/EHvK6Lq.png)

# Free and Open-Source Lightning Wallet Accounts System

(Join us on [https://t.me/lnbits](https://t.me/lnbits))

LNbits is beta, for responsible disclosure of any concerns please contact lnbits@pm.me

Use [legend.lnbits.com](https://legend.lnbits.com), or run your own LNbits server!

LNbits is a Python server that sits on top of any funding source. It can be used as:

- Accounts system to mitigate the risk of exposing applications to your full balance via unique API keys for each wallet
- Extendable platform for exploring Lightning network functionality via the LNbits extension framework
- Part of a development stack via LNbits API
- Fallback wallet for the LNURL scheme
- Instant wallet for LN demonstrations

LNbits can run on top of any Lightning funding source. It currently supports the following, but more and more are added regularly:
- LND (REST and gRPC)
- Core Lightning aka CLN (gRPC, REST and Spark)
- Eclair
- LNPay
- LNbits
- OpenNode
- Alby
- ZBD
- LightningTipBot
- Breez SDK (Greenlight)

See [LNbits manual](https://docs.lnbits.org/guide/wallets.html) for more detailed documentation about each funding source.

Checkout the LNbits [YouTube](https://www.youtube.com/playlist?list=PLPj3KCksGbSYG0ciIQUWJru1dWstPHshe) video series.

LNbits is inspired by all the great work of [opennode.com](https://www.opennode.com/), and in particular [lnpay.co](https://lnpay.co/). Both work as funding sources for LNbits.

## Running LNbits

See the [install guide](https://github.com/lnbits/lnbits/blob/main/docs/guide/installation.md) for details on installation and setup.

## LNbits as an account system

LNbits is packaged with tools to help manage funds, such as a table of transactions, line chart of spending, export to csv + more to come..

![Lightning network wallet](https://i.imgur.com/w8jdGpF.png)

Each wallet also comes with its own API keys, to help partition the exposure of your funding source.

(LNbits M5StackSats available here https://github.com/arcbtc/M5StackSats)

![lnurl ATM](https://i.imgur.com/WfCg8wY.png)

## LNbits as an LNURL-withdraw fallback

LNURL has a fallback scheme, so if scanned by a regular QR code reader it can default to a URL. LNbits exploits this to generate an instant wallet using the [LNURL-withdraw](https://github.com/btcontract/lnurl-rfc/blob/master/lnurl-withdraw.md).

![lnurl fallback](https://i.imgur.com/CPBKHIv.png)

Using **lnbits.com/?lightning="LNURL-withdraw"** will trigger a withdraw that builds an LNbits wallet.
Example use would be an ATM, which utilizes LNURL, if the user scans the QR with a regular QR code scanner app, they will still be able to access the funds.

![lnurl ATM](https://i.imgur.com/Gi6bn3L.jpg)

## LNbits as an instant wallet

Wallets can be easily generated and given out to people at events. "Go to this website", has a lot less friction than "Download this app".

![lnurl ATM](https://i.imgur.com/xFWDnwy.png)

## Tip us

If you like this project [send some tip love](https://legend.lnbits.com/paywall/GAqKguK5S8f6w5VNjS9DfK)!

[docs]: https://github.com/lnbits/lnbits/wiki
[docs-badge]: https://img.shields.io/badge/docs-lnbits.org-673ab7.svg
[github-mypy]: https://github.com/lnbits/lnbits/actions?query=workflow%3Amypy
[github-mypy-badge]: https://github.com/lnbits/lnbits/workflows/mypy/badge.svg
[github-tests]: https://github.com/lnbits/lnbits/actions?query=workflow%3Atests
[github-tests-badge]: https://github.com/lnbits/lnbits/workflows/tests/badge.svg
[codecov]: https://codecov.io/gh/lnbits/lnbits
[codecov-badge]: https://codecov.io/gh/lnbits/lnbits/branch/master/graph/badge.svg
[license-badge]: https://img.shields.io/badge/license-MIT-blue.svg
