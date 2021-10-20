# SatsPay Server

## Create onchain and LN charges. Includes webhooks!

Easilly create invoices that support Lightning Network and on-chain BTC payment.

1. Create a "NEW CHARGE"\
   ![new charge](https://i.imgur.com/fUl6p74.png)
2. Fill out the invoice fields
   - set a descprition for the payment
   - the amount in sats
   - the time, in minutes, the invoice is valid for, after this period the invoice can't be payed
   - set a webhook that will get the transaction details after a successful payment
   - set to where the user should redirect after payment
   - set the text for the button that will show after payment (not setting this, will display "NONE" in the button)
   - select if you want onchain payment, LN payment or both
   - depending on what you select you'll have to choose the respective wallets where to receive your payment\
     ![charge form](https://i.imgur.com/F10yRiW.png)
3. The charge will appear on the _Charges_ section\
   ![charges](https://i.imgur.com/zqHpVxc.png)
4. Your costumer/payee will get the payment page
   - they can choose to pay on LN\
     ![offchain payment](https://i.imgur.com/4191SMV.png)
   - or pay on chain\
     ![onchain payment](https://i.imgur.com/wzLRR5N.png)
5. You can check the state of your charges in LNBits\
   ![invoice state](https://i.imgur.com/JnBd22p.png)
