<h1>Bolt cards (NXP NTAG) Extension</h1>

This extension allows you to link your Bolt card with a LNbits instance and use it more securely then just with a static LNURLw on it. A technology called [Secure Unique NFC](https://mishka-scan.com/blog/secure-unique-nfc) is utilized in this workflow. 

**In order to use this extension you need to be able setup your card first.** There's a [guide](https://www.whitewolftech.com/articles/payment-card/) to set it up with your computer. Hopefully a mobile app is to come to do this. 

<h2>Setting the outside the extension</h2>

The URI should be `lnurlw://YOUR-DOMAIN.COM/boltcards/api/v1/scane/?e=00000000000000000000000000000000&c=0000000000000000`

(At this point the link is common to all cards. So the extension grabs one by one every added card's key and tries to decrypt the e parameter until there's a match.)

Choose and note your Meta key and File key. 

<h2>Adding the into the extension</h2>

Create a withdraw link within the LNURLw extension before adding a card. Enable the `Use unique withdraw QR codes to reduce 'assmilking'` option. 

The card UID can be retrieve with `NFC TagInfo` mobile app or from `NXP TagXplorer` log. Use the keys you've set before. You can leave the counter zero, it gets synchronized with the first use. 
