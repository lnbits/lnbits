# Bolt cards (NXP NTAG) Extension

This extension allows you to link your Bolt card with a LNbits instance and use it more securely then just with a static LNURLw on it. A technology called [Secure Unique NFC](https://mishka-scan.com/blog/secure-unique-nfc) is utilized in this workflow. 

***In order to use this extension you need to be able setup your card first.*** There's a [guide](https://www.whitewolftech.com/articles/payment-card/) to set it up with your computer. Or it can be done with [https://play.google.com/store/apps/details?id=com.nxp.nfc.tagwriter](TagWriter app by NXP) Android app.

## Setting the outside the extension - android
- Write tags
- New Data Set > Link
- Set URI type to Custom URL
- URL should look like lnurlw://YOUR_LNBITS_DOMAIN/boltcards/api/v1/scane?e=00000000000000000000000000000000&c=0000000000000000
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

## Setting the outside the extension - computer

Follow the guide. 

The URI should be `lnurlw://YOUR-DOMAIN.COM/boltcards/api/v1/scane/?e=00000000000000000000000000000000&c=0000000000000000`

(At this point the link is common to all cards. So the extension grabs one by one every added card's key and tries to decrypt the e parameter until there's a match.)

Choose and note your Meta key and File key. 

## Adding the into the extension

Create a withdraw link within the LNURLw extension before adding a card. Enable the `Use unique withdraw QR codes to reduce 'assmilking'` option. 

The card UID can be retrieve with `NFC TagInfo` mobile app or from `NXP TagXplorer` log. Use the keys you've set before. You can leave the counter zero, it gets synchronized with the first use. 