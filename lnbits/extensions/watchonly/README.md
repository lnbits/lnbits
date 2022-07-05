# Onchain Wallet (watch-only)

## Monitor an onchain wallet and generate addresses for onchain payments

Monitor an extended public key and generate deterministic fresh public keys with this simple watch only wallet. Invoice payments can also be generated, both through a publically shareable page and API.

You can now use this wallet on the LNBits [SatsPayServer](https://github.com/lnbits/lnbits/blob/master/lnbits/extensions/satspay/README.md) extension

### Wallet Account
 - a user can add one or more `xPubs` or `descriptors`
   - the `xPub` fingerprint must be unique per user
   - such and entry is called an `Wallet Account`
   - the addresses in a `Wallet Account` are split into `Receive Addresses` and `Change Address`
   - the user interacts directly only with the `Receive Addresses` (by sharing them)
   - see [BIP44](https://github.com/bitcoin/bips/blob/master/bip-0044.mediawiki#account-discovery) for more details
   - same `xPub` will always generate the same addresses (deterministic)
 - when a `Wallet Account` is created, there are generated `20 Receive Addresses` and `5 Change Address`
   -  the limits can be change from the `Config` page (see `screenshot 1`)
   - regular wallets only scan up to `20` empty receive addresses. If the user generates addresses beyond this limit a warning is shown (see `screenshot 4`)

### Scan Blockchain
 - when the user clicks `Scan Blockchain`, the wallet will loop over the all addresses (for each account)
   - if funds are found, then the list is extended
   -  will scan addresses for all wallet accounts
 - the search is done on the client-side (using the `mempool.space` API). `mempool.space` has a limit on the number of req/sec, therefore it is expected for the scanning to start fast, but slow down as more HTTP requests have to be retried
 - addresses can also be rescanned individually form the `Address Details` section (`Addresses` tab) of each address
 
### New Receive Address
 - the `New Receive Address` button show the user the NEXT un-used address
   - un-used means funds have not already been sent to that address AND the address has not already been shared
   - internally there is a counter that keeps track of the last shared address
   - it is possible to add a `Note` to each address in order to remember when/with whom it was shared
   - mind the gap (`screenshot 4`)

### Addresses Tab
- the `Addresses` tab contains a list with the addresses for all the `Wallet Accounts`
   - only one entry per address will be shown (even if there are multiple UTXOs at that address)
   - several filter criteria can be applied
   - unconfirmed funds are also taken into account
   - `Address Details` can be viewed by clicking the `Expand` button

### History Tap
 - shows the chronological order of transactions
 - it shows unconfirmed transactions at the top
 - it can be exported as CSV file

###  Coins Tab
 - shows the UTXOs for all wallets
 - there can be multiple UTXOs for the same address

### Make Payment
 - create a new `Partially Signed Bitcoin Transaction`
 - multiple `Send Addresses` can be added
   -  the `Max` button next to an address is for sending the remaining funds to this address (no change)
 - the user can select the inputs (UTXOs) manually, or it can use of the basic selection algorithms
    - amounts have to be provided for the `Send Addresses` beforehand (so the algorithm knows the amount to be selected)
 - `Show Advanced` allows to (see `screenshot 2`):
    - select from which account the change address will be selected (defaults to the first one)
    - select the `Fee Rate`
       - it defaults to the `Medium` value at the moment the `Make Payment` button was clicked
       - it can be refreshed
       - warnings are shown if the fee is too Low or to High

### Create PSBT
 - based on the Inputs & Outputs selected by the user a PSBT will be generated
 - this wallet is watch-only, therefore does not support signing
 - it is not mandatory for the `Selected Amount` to be grater than `Payed Amount`
   - the generated PSBT can be combined with other PSBTs that add more inputs.
 - the generated PSBT can be imported for signing into different wallets like Electrum
   - import the PSBT into Electrum and check the In/Outs/Fee (see `screenshot 3`)

## Screensots
- screenshot 1:
![image](https://user-images.githubusercontent.com/2951406/177181611-eeeac70c-c245-4b45-b80b-8bbb511f6d1d.png)

- screenshot 2:
![image](https://user-images.githubusercontent.com/2951406/177331468-f9b43626-548a-4608-b0d0-44007f402404.png)

- screenshot 3:
![image](https://user-images.githubusercontent.com/2951406/177333755-4a9118fb-3eaf-43d6-bc7e-c3d8c80bc61e.png)

- screenshot 4:
![image](https://user-images.githubusercontent.com/2951406/177337474-bfcf7a7c-501a-4ebb-916e-ca391e63f6a7.png)


