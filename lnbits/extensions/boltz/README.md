# Swap on [Boltz](https://boltz.exchange)
providing **trustless** and **account-free** swap services since **2018.**
move **IN** and **OUT** of the **lightning network** and remain in control of your bitcoin, at all times.
* [Lightning Node](https://amboss.space/node/026165850492521f4ac8abd9bd8088123446d126f648ca35e60f88177dc149ceb2)
* [Documentation](https://docs.boltz.exchange/en/latest/)
* [Discord](https://discord.gg/d6EK85KK)
* [Twitter](https://twitter.com/Boltzhq)
* [FAQ](https://www.notion.so/Frequently-Asked-Questions-585328ae43944e2eba351050790d5eec) very cool!

# usage
This extension lets you create swaps, reverse swaps and in the case of failure refund your onchain funds.

## create normal swap (Onchain -> Lightning)
1. click on "Swap (IN)" button to open following dialog, select a wallet, choose a proper amount in the min-max range and choose a onchain address to do your refund to if the swap fails after you already commited onchain funds.
---
![create swap](https://imgur.com/OyOh3Nm.png)
---
2. after you confirm your inputs, following dialog with the QR code for the onchain transaction, onchain- address and amount, will pop up.
---
![pay onchain tx](https://imgur.com/r2UhwCY.png)
---
3. after you pay this onchain address with the correct amount, boltz will see it and will pay your invoice and the sats will appear on your wallet.

if anything goes wrong when boltz is trying to pay your invoice, the swap will fail and you will need to refund your onchain funds after the timeout block height hit. (if boltz can pay the invoice, it wont be able to redeem your onchain funds either).

## create reverse swap (Lightning -> Onchain)
1. click on "Swap (OUT)" button to open following dialog, select a wallet, choose a proper amount in the min-max range and choose a onchain address to receive your funds to. Instant settlement: means that LNbits will create the onchain claim transaction if it sees the boltz lockup transaction in the mempool, but it is not confirmed yet. it is advised to leave this checked because it is faster and the longer is takes to settle, the higher the chances are that the lightning invoice expires and the swap fails.
---
![reverse swap](https://imgur.com/UEAPpbs.png)
---
if this swap fails, boltz is doing the onchain refunding, because they have to commit onchain funds.

# refund locked onchain funds from a normal swap (Onchain -> Lightning)
if for some reason the normal swap fails and you already paid onchain, you can easily refund your btc.
this can happen if boltz is not able to pay your lightning invoice after you locked up your funds.
in case that happens, there is a info icon in the Swap (In) List which opens following dialog.
---
![refund](https://imgur.com/pN81ltf.png)
----
if the timeout block height is exceeded you can either press refund and lnbits will do the refunding to the address you specified when creating the swap. Or download the refundfile so you can manually refund your onchain directly on the boltz.exchange website.
if you think there is something wrong and/or you are unsure, you can ask for help either in LNbits telegram or in Boltz [Discord](https://discord.gg/d6EK85KK).
In a recent update we made *automated check*, every 15 minutes, to check if LNbits can refund your failed swap.
