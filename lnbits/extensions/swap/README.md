<h1>Swap</h1>
<h2>Onchain <-> Offchain swaps</h2>
Swap extension allows for sending offchain funds to an onchain address and vice-versa.

You can move your Lightning Network funds to your onchain wallet or fund an Lnbits wallet with an onchain transaction. 

The extension uses [Etleneum's](etleneum.com) Chainmarket contract.

## Usage
### Swap Out - *offchain -> onchain*

You can either make a one-time, manual, Swap Out or instruct LNbits to make this a recurrent operation every time your balance hits a defined threshold. You can also connect the Swap Out to the Watch-Only extension to pull a fresh BTC onchain address every time it makes a Swap.

1. On the extension click "CREATE SWAP OUT"\
   ![create swap out](https://i.imgur.com/aVntJ1I.png)

2. Fill the form with the requested details\
   ![fill form](https://i.imgur.com/y371eGM.png)

   - select the wallet to send funds
   - select how much to send or the threshold that will trigger a Swap Out
   - fill a fee in satoshis
   - select the onchain address you want to send to, or
   - use the Watch-Only extension to generate addresses
   - choose if you'd rather make this Swap Out recurrent

3. If you selected to make the Swap Out recurrent, the Swap will only happen when your wallet balance reaches the specified threshold. A new section with your recurrent payment will show with the information about your recurrent Swap\
   ![recurrent card](https://i.imgur.com/ORLYnvO.png)\
   . Every time a Swap Out is made, either manually or automatically triggered, it will show on the *Swap Outs* section\
   ![swapout card](https://i.imgur.com/etLVT54.png)

**Fee notes on Swap Out**: 
- Only one recurrent swap can be created per wallet. 
- When selecting an amount/threshold take into consideration the dust limits or you'll be stuck with unusable bitcoin.
- The *Fee* is an incentive for someone that will collect your offchain funds and send an onchain transaction to the specified address. If it's set too low there's no incentive for someone to do it. Consider something above 10/20 sats.
- If you use the same onchain address for all your Swap Outs, both the amount and fees will be added up, on that address and fees, on Chainmarket until someone takes your offer.

### Swap In - *onchain -> offchain*
Swap In allows you to fund your LNbits wallet with an onchain transaction.

Not implemented yet!
