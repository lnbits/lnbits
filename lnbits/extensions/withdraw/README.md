# LNURLw

## Create a static QR code people can use to withdraw funds from a Lightning Network wallet

LNURL is a range of lightning-network standards that allow us to use lightning-network differently. An LNURL withdraw is the permission for someone to pull a certain amount of funds from a lightning wallet.

The most common use case for an LNURL withdraw is a faucet, although it is a very powerful technology, with much further reaching implications. For example, an LNURL withdraw could be minted to pay for a subscription service. Or you can have a LNURLw as an offline Lightning wallet (a pre paid "card"), you use to pay for something without having to even reach your smartphone.

LNURL withdraw is a **very powerful tool** and should not have his use limited to just faucet applications. With LNURL withdraw, you have the ability to give someone the right to spend a range, once or multiple times. **This functionality has not existed in money before**.

[**Wallets supporting LNURL**](https://github.com/fiatjaf/awesome-lnurl#wallets)

## Usage

#### Quick Vouchers

LNbits Quick Vouchers allows you to easily create a batch of LNURLw's QR codes that you can print and distribute as rewards, onboarding people into Lightning Network, gifts, etc...

1. Create Quick Vouchers\
   ![quick vouchers](https://i.imgur.com/IUfwdQz.jpg)
   - select wallet
   - set the amount each voucher will allow someone to withdraw
   - set the amount of vouchers you want to create - _have in mind you need to have a balance on the wallet that supports the amount \* number of vouchers_
2. You can now print, share, display your LNURLw links or QR codes\
   ![lnurlw created](https://i.imgur.com/X00twiX.jpg)
   - on details you can print the vouchers\
     ![printable vouchers](https://i.imgur.com/2xLHbob.jpg)
   - every printed LNURLw QR code is unique, it can only be used once
3. Bonus: you can use an LNbits themed voucher, or use a custom one. There's a _template.svg_ file in `static/images` folder if you want to create your own.\
   ![voucher](https://i.imgur.com/qyQoHi3.jpg)

#### Advanced

1. Create the Advanced LNURLw\
   ![create advanced lnurlw](https://i.imgur.com/OR0f885.jpg)
   - set the wallet
   - set a title for the LNURLw (it will show up in users wallet)
   - define the minimum and maximum a user can withdraw, if you want a fixed amount set them both to an equal value
   - set how many times can the LNURLw be scanned, if it's a one time use or it can be scanned 100 times
   - LNbits has the "_Time between withdraws_" setting, you can define how long the LNURLw will be unavailable between scans
   - you can set the time in _seconds, minutes or hours_
   - the "_Use unique withdraw QR..._" reduces the chance of your LNURL withdraw being exploited and depleted by one person, by generating a new QR code every time it's scanned
2. Print, share or display your LNURLw link or it's QR code\
   ![lnurlw created](https://i.imgur.com/X00twiX.jpg)

**LNbits bonus:** If a user doesn't have a Lightning Network wallet and scans the LNURLw QR code with their smartphone camera, or a QR scanner app, they can follow the link provided to claim their satoshis and get an instant LNbits wallet!

![](https://i.imgur.com/2zZ7mi8.jpg)
