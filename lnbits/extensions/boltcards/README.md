# Bolt cards (NXP NTAG) Extension

This extension allows you to link your Bolt Card (or other compatible NXP NTAG device) with a LNbits instance and use it in a more secure way than a static LNURLw. A technology called [Secure Unique NFC](https://mishka-scan.com/blog/secure-unique-nfc) is utilized in this workflow. 

<a class="text-secondary" href="https://www.youtube.com/watch?v=wJ7QLFTRjK0">Tutorial</a>

**Disclaimer:** ***Use this only if you either know what you are doing or are a reckless lightning pioneer. Only you are responsible for all your sats, cards and other devices. Always backup all your card keys!***


***In order to use this extension you need to be able to setup your own card.*** That means writing a URL template pointing to your LNbits instance, configuring some SUN (SDM) settings and optionally changing the card's keys. There's a [guide](https://www.whitewolftech.com/articles/payment-card/) to set it up with a card reader connected to your computer. It can be done (without setting the keys) with [TagWriter app by NXP](https://play.google.com/store/apps/details?id=com.nxp.nfc.tagwriter) Android app. Last but not least, an OSS android app by name [Boltcard NFC Card Creator](https://github.com/boltcard/bolt-nfc-android-app) is being developed for these purposes. It's available from Google Play [here](https://play.google.com/store/apps/details?id=com.lightningnfcapp).

## About the keys

Up to five 16-byte keys can be stored on the card, numbered from 00 to 04. In the empty state they all should be set to zeros (00000000000000000000000000000000). For this extension only two keys need to be set, but for the security reasons all five keys should be changed from default (empty) state. The keys directly needed by this extension are: 

- One for encrypting the card UID and the counter (p parameter), let's called it meta key, key #01 or K1.

- One for calculating CMAC (c parameter), let's called it file key, key #02 or K2.

The key #00, K0 (also know as auth key) is used as authentification key. It is not directly needed by this extension, but should be filled in order to write the keys in cooperation with Boltcard NFC Card Creator. In this case also K3 is set to same value as K1 and K4 as K2, so all keys are changed from default values. Keep that in your mind in case you ever need to reset the keys manually.

***Always backup all keys that you're trying to write on the card. Without them you may not be able to change them in the future!***


## Setting the card - Boltcard NFC Card Creator (easy way)
Updated for v0.1.3

- Add new card in the extension. 
    - Set a max sats per transaction. Any transaction greater than this amount will be rejected.
    - Set a max sats per day. After the card spends this amount of sats in a day, additional transactions will be rejected.
    - Set a card name. This is just for your reference inside LNbits.
    - Set the card UID. This is the unique identifier on your NFC card and is 7 bytes.
        - If on an Android device with a newish version of Chrome, you can click the icon next to the input and tap your card to autofill this field.
        - Otherwise read it with the Android app (Advanced -> Read NFC) and paste it to the field.
    - Advanced Options
        - Card Keys (k0, k1, k2) will be automatically generated if not explicitly set.
            - Set to 16 bytes of 0s (00000000000000000000000000000000) to leave the keys in default (empty) state (this is unsecure).
            - GENERATE KEY button fill the keys randomly.  
    - Click CREATE CARD button
- Click the QR code button next to a card to view its details. Backup the keys now! They'll be comfortable in your password manager.
    - Now you can scan the QR code with the Android app (Create Bolt Card -> SCAN QR CODE). 
    - Or you can Click the "KEYS / AUTH LINK" button to copy the auth URL to the clipboard. Then paste it into the Android app (Create Bolt Card -> PASTE AUTH URL).
- Click WRITE CARD NOW and approach the NFC card to set it up. DO NOT REMOVE THE CARD PREMATURELY! 

## Erasing the card - Boltcard NFC Card Creator
Updated for v0.1.3

Since v0.1.2 of Boltcard NFC Card Creator it is possible not only reset the keys but also disable the SUN function and do the complete erase so the card can be use again as a static tag (or set as a new Bolt Card, ofc).

- Click the QR code button next to a card to view its details and select WIPE 
- OR click the red cross icon on the right side to reach the same 
- In the android app (Advanced -> Reset Keys)
    - Click SCAN QR CODE to scan the QR
    - Or click WIPE DATA in LNbits to copy and paste in to the app (PASTE KEY JSON)
- Click RESET CARD NOW and approach the NFC card to erase it. DO NOT REMOVE THE CARD PREMATURELY! 
- Now if there is all success the card can be safely delete from LNbits (but keep the keys backuped anyway; batter safe than brick).

If you somehow find yourself in some non-standard state (for instance only k3 and k4 remains filled after previous unsuccessful reset), then you need edit the key fields manually (for instance leave k0-k2 to zeroes and provide the right k3 and k4).  

## Setting the card - computer (hard way)

Follow the guide. 

The URI should be `lnurlw://YOUR-DOMAIN.COM/boltcards/api/v1/scan/{YOUR_card_external_id}?p=00000000000000000000000000000000&c=0000000000000000`

Then fill up the card parameters in the extension. Card Auth key (K0) can be filled in the extension just for the record. Initical counter can be 0.

## Setting the card - android NXP app (hard way)
- If you don't know the card ID, use NXP TagInfo app to find it out.
- In the TagWriter app tap Write tags
- New Data Set > Link
- Set URI type to Custom URL
- URL should look like lnurlw://YOUR_LNBITS_DOMAIN/boltcards/api/v1/scan/{YOUR_card_external_id}?p=00000000000000000000000000000000&c=0000000000000000
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

This app afaik cannot change the keys. If you cannot change them any other way, leave them empty in the extension dialog and remember you're not secured. Card Auth key (K0) can be omitted anyway. Initical counter can be 0.
