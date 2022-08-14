# Bolt cards (NXP NTAG) Extension

This extension allows you to link your Bolt card with a LNbits instance and use it more securely then just with a static LNURLw on it. A technology called [Secure Unique NFC](https://mishka-scan.com/blog/secure-unique-nfc) is utilized in this workflow. 

**Disclaim:** ***Use this only if you either know what you are doing or are enough reckless lightning pioneer. Only you are responsible for all your sats, cards and other devices. Always backup all your card keys!***

***In order to use this extension you need to be able setup your card.*** That is writting on the URL template pointing to your LNBits instance, configure some SUN (SDM) setting and optionaly changing the card keys. There's a [guide](https://www.whitewolftech.com/articles/payment-card/) to set it up with a card reader connected to your computer. It can be done (without setting the keys) with [TagWriter app by NXP](https://play.google.com/store/apps/details?id=com.nxp.nfc.tagwriter) Android app. Last but not least, an OSS android app by name [bolt-nfc-android-app](https://github.com/boltcard/bolt-nfc-android-app) is being developed for these purposes.

## About the keys

Up to five 16bytes keys can be stored on the card, numbered from 00 to 04. In the empty state they all should be set to zeros (00000000000000000000000000000000). For this extension only two keys need to be set:

One for encrypting the card UID and the counter (p parameter), let's called it meta key, key #01or K1.

One for calculating CMAC (c parameter), let's called it file key, key #02 or K2.

The key #00, K0 or also auth key is skipped to be use as authentification key. Is not needed by this extension, but can be filled in order to write the keys in cooperation with bolt-nfc-android-app. 

***Always backup all keys that you're trying to write on the card. Without them you may not be able to change them in the future!***

## LNURLw 
Create a withdraw link within the LNURLw extension before adding a card. Enable the `Use unique withdraw QR codes to reduce 'assmilking'` option. 

## Setting the card - bolt-nfc-android-app (easy way)
So far, regarding the keys, the app can only write a new key set on an empty card (with zero keys). **When you write non zero (and 'non debug') keys, they can't be rewrite with this app.** You have to do it on your computer. 

- Read the card with the app. Note UID so you can fill it in the extension later.
- Write the link on  the card. It shoud be like `YOUR_LNBITS_DOMAIN/boltcards/api/v1/scan`
- Add new card in the extension. 
    - Leaving any key array empty means that key is 16bytes of zero (00000000000000000000000000000000). 
    - GENERATE KEY button fill the keys randomly. If there is "debug" in the card name, a debug set of keys is filled instead.
    - Leaving initial counter empty means zero. 
- Open the card details. **Backup the keys.** Scan the QR with the app to write the keys on the card.

## Setting the card - computer (hard way)

Follow the guide. 

The URI should be `lnurlw://YOUR-DOMAIN.COM/boltcards/api/v1/scan?p=00000000000000000000000000000000&c=0000000000000000`

Then fill up the card parameters in the extension. Card Auth key (K0) can be omitted. Initical counter can be 0.

## Setting the card - android NXP app (hard way)
- If you don't know the card ID, use NXP TagInfo app to find it out.
- In the TagWriter app tap Write tags
- New Data Set > Link
- Set URI type to Custom URL
- URL should look like lnurlw://YOUR_LNBITS_DOMAIN/boltcards/api/v1/scan?p=00000000000000000000000000000000&c=0000000000000000
- click Configure mirroring options
- Select Card Type NTAG 424 DNA
- Check Enable SDM Mirroring
- Select SDM Meta Read Access Right to 01
- Check Enable UID Mirroring
- Check Enable Counter Mirroring
- Set SDM Counter Retrieval Key to 0E
- Set PICC Data Offset to immediately after e=
- Set Derivation Key for CMAC Calculation to 00
- Set SDM MAC Input Offset to immediately after c=
- Set SDM MAC Offset to immediately after c=
- Save & Write
- Scan with compatible Wallet

This app afaik cannot change the keys. If you cannot change them any other way, leave them empty in the extension dialog and remember you're not secure. Card Auth key (K0) can be omitted anyway. Initical counter can be 0.
