# Split Payments

## Have payments split between multiple wallets

LNBits Split Payments extension allows for distributing payments across multiple wallets. Set it and forget it. It will keep splitting your payments across wallets forever.

## Usage

1. After enabling the extension, choose the source wallet that will receive and distribute the Payments

![choose wallet](https://i.imgur.com/nPQudqL.png)

2. Add the wallet or wallets info to split payments to

![split wallets](https://i.imgur.com/5hCNWpg.png) - get the wallet id, or an invoice key from a different wallet. It can be a completely different user as long as it's under the same LNbits instance/domain. You can get the wallet information on the API Info section on every wallet page\
 ![wallet info](https://i.imgur.com/betqflC.png) - set a wallet _Alias_ for your own identification\

- set how much, in percentage, this wallet will receive from every payment sent to the source wallets

3. When done, click "SAVE TARGETS" to make the splits effective

4. You can have several wallets to split to, as long as the sum of the percentages is under or equal to 100%

5. When the source wallet receives a payment, the extension will automatically split the corresponding values to every wallet\
   - on receiving a 20 sats payment\
     ![get 20 sats payment](https://i.imgur.com/BKp0xvy.png)
   - source wallet gets 18 sats\
     ![source wallet](https://i.imgur.com/GCxDZ5s.png)
   - Ben's wallet (the wallet from the example) instantly, and feeless, gets the corresponding 10%, or 2 sats\
     ![ben wallet](https://i.imgur.com/MfsccNa.png)

## Sponsored by

[![](https://cdn.shopify.com/s/files/1/0826/9235/files/cryptograffiti_logo_clear_background.png?v=1504730421)](https://cryptograffiti.com/)
