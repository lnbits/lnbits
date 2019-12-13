# LNbits
Free and open-source lightning wallet

LNbits is a simple, free and open-source lightning-network wallet for bits and bobs. You can run it on your own server, or use this one.

The wallet can be used in a variety of ways, an instant wallet for LN demonstrations, a fallback wallet for the LNURL scheme, an accounts system to mitigate the risk of exposing applications to your full balance.

The wallet can run on top of LND, lntxbot, paywall, opennode

Please note that although one of the aims of this wallet is to mitigate exposure of all your funds, it’s still very BETA and may in fact do the opposite!

## LNbits as an LNURL-withdraw fallback

![lnurl fallback](https://i.imgur.com/CPBKHIv.png)
https://github.com/btcontract/lnurl-rfc/blob/master/spec.md

Adding **/lnurlwallet?lightning="LNURL-WITHDRAW"** will trigger a withdraw that builds an LNbits wallet. 
An example use would be an ATM, which utilises LNURL, if the user scans the QR with a regular QR code scanner app, they will stilll be able to access the funds.

![lnurl ATM](https://i.imgur.com/Gi6bn3L.jpg)

# Tip me
If you like this project and might even use or extend it, why not send some tip love!
https://paywall.link/to/f4e4e
