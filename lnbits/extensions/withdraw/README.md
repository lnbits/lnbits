# LNURLw
## Withdraw link maker
LNURL withdraw is a very powerful tool and should not have his use limited to just faucet applications. With LNURL withdraw, you have the ability to give someone the right to spend a range, once or multiple times. This functionality has not existed in money before.
https://github.com/btcontract/lnurl-rfc/blob/master/spec.md#3-lnurl-withdraw

With this extension to can create/edit LNURL withdraws, set a min/max amount, set time (useful for subscription services)

![lnurl](https://i.imgur.com/qHi7ExL.png)


## API endpoint - /withdraw/api/v1/lnurlmaker
Easily fetch one-off LNURL

    curl -H "Content-type: application/json" -X POST https://YOUR-LNBITS/withdraw/api/v1/lnurlmaker -d '{"amount":"100","memo":"ATM"}' -H "Grpc-Metadata-macaroon: YOUR-WALLET-ADMIN-KEY"
