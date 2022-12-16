# DJ Livestream

## Help DJ's and music producers conduct music livestreams

LNbits Livestream extension produces a static QR code that can be shown on screen while livestreaming a DJ set for example. If someone listening to the livestream likes a song and want to support the DJ and/or the producer he can scan the QR code with a LNURL-pay capable wallet.

When scanned, the QR code sends up information about the song playing at the moment (name and the producer of that song). Also, if the user likes the song and would like to support the producer, he can send a tip and a message for that specific track. If the user sends an amount over a specific threshold they will be given a link to download it (optional).

The revenue will be sent to a wallet created specifically for that producer, with optional revenue splitting between the DJ and the producer.

[**Wallets supporting LNURL**](https://github.com/fiatjaf/awesome-lnurl#wallets)

[![video tutorial livestream](http://img.youtube.com/vi/zDrSWShKz7k/0.jpg)](https://youtu.be/zDrSWShKz7k 'video tutorial offline shop')

## Usage

1. Start by adding a track\
   ![add new track](https://i.imgur.com/Cu0eGrW.jpg)
   - set the producer, or choose an existing one
   - set the track name
   - define a minimum price where a user can download the track
   - set the download URL, where user will be redirected if he tips the livestream and the tip is equal or above the set price\
     ![track settings](https://i.imgur.com/HTJYwcW.jpg)
2. Adjust the percentage of the pay you want to take from the user's tips. 10%, the default, means that the DJ will keep 10% of all the tips sent by users. The other 90% will go to an auto generated producer wallet\
   ![adjust percentage](https://i.imgur.com/9weHKAB.jpg)
3. For every different producer added, when adding tracks, a wallet is generated for them\
   ![producer wallet](https://i.imgur.com/YFIZ7Tm.jpg)
4. On the bottom of the LNbits DJ Livestream extension you'll find the static QR code ([LNURL-pay](https://github.com/lnbits/lnbits/blob/master/lnbits/extensions/lnurlp/README.md)) you can add to the livestream or if you're a street performer you can print it and have it displayed
5. After all tracks and producers are added, you can start "playing" songs\
   ![play tracks](https://i.imgur.com/7ytiBkq.jpg)
6. You'll see the current track playing and a green icon indicating active track also\
   ![active track](https://i.imgur.com/W1vBz54.jpg)
7. When a user scans the QR code, and sends a tip, you'll receive 10%, in the example case, in your wallet and the producer's wallet will get the rest. For example someone tips 100 sats, you'll get 10 sats and the producer will get 90 sats
   - producer's wallet receiving 18 sats from 20 sats tips\
     ![producer wallet](https://i.imgur.com/OM9LawA.jpg)

## Use cases

You can print the QR code and display it on a live gig, a street performance, etc... OR you can use the QR as an overlay in an online stream of you playing music, doing a DJ set, making a podcast.

You can use the extension's API to trigger updates for the current track, update fees, add tracks...

## Sponsored by

[![](https://cdn.shopify.com/s/files/1/0826/9235/files/cryptograffiti_logo_clear_background.png?v=1504730421)](https://cryptograffiti.com/)
