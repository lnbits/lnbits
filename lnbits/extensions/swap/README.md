<h1>Swap</h1>
<h2>Onchain <-> Offchain swaps</h2>
Swap extension allows for sending offchain funds to an onchain address and vice-versa.

You can move your Lightning Network funds to your onchain wallet or fund an Lnbits wallet with an onchain transaction.

The extension uses [Etleneum's](etleneum.com) Chainmarket contract.

## Usage

### Swap Out - _offchain -> onchain_

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
   . Every time a Swap Out is made, either manually or automatically triggered, it will show on the _Swap Outs_ section\
   ![swapout card](https://i.imgur.com/etLVT54.png)

**Fee notes on Swap Out**:

- Only one recurrent swap can be created per wallet.
- When selecting an amount/threshold take into consideration the dust limits or you'll be stuck with unusable bitcoin.
- The _Fee_ is an incentive for someone that will collect your offchain funds and send an onchain transaction to the specified address. If it's set too low there's no incentive for someone to do it. Consider something above 10/20 sats.
- If you use the same onchain address for all your Swap Outs, both the amount and fees will be added up, on that address and fees, on Chainmarket until someone takes your offer.

### Swap In - _onchain -> offchain_

Swap In allows you to fund your LNbits wallet with an onchain transaction.

1. On the extension click "CREATE SWAP OUT"\
   ![create swap in](https://i.imgur.com/dibf4iQ.png)

2. Fill the form with the requested details\
   ![fill form](https://i.imgur.com/P4FQzTS.png)

   - select the wallet to send funds
   - click the "LNURL AUTH" button to authenticate with etleneum
   - choose which offers you want to take
   - click "RESERVE", there's a fee to make the reserve, an invoice will pop up
   - you'll see a list of the addresses and values for which you'll need to make a tx, or batch tx in case you've chosen more than one offer
   - after you've made the transaction and broadcasted it to the network, add the transaction id and click "SEND TXID"
   - after 3 confirmations, the balance will be available for withdraw, LNbits will try to withdraw the balance automatically
   - a "BUMP" and a "WITHDRAW" buttons will show, you can use "BUMP" to check if the balance is ready

3. You'll be able to check, or edit if it's not finalized, your Swap Ins in the _Swap Ins_ section\
   ![swapin section](https://i.imgur.com/DMA2C5v.png)

4. The satoshis will be added to your wallet balance\
   ![balance](https://i.imgur.com/XKfMRas.png)
