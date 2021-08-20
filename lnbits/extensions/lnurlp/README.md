# LNURLp

## Create a static QR code people can use to pay over Lightning Network

LNURL is a range of lightning-network standards that allow us to use lightning-network differently. An LNURL-pay is a link that wallets use to fetch an invoice from a server on-demand. The link or QR code is fixed, but each time it is read by a compatible wallet a new invoice is issued by the service and sent to the wallet.

[**Wallets supporting LNURL**](https://github.com/fiatjaf/awesome-lnurl#wallets)

## Usage

1. Create an LNURLp (New Pay link)\
   ![create lnurlp](https://i.imgur.com/rhUBJFy.jpg)

   - select your wallets
   - make a small description
   - enter amount
   - if _Fixed amount_ is unchecked you'll have the option to configure a Max and Min amount
   - you can set the currency to something different than sats. For example if you choose EUR, the satoshi amount will be calculated when a user scans the LNURLp
   - You can ask the user to send a comment that will be sent along with the payment (for example a comment to a blog post)
   - Webhook URL allows to call an URL when the LNURLp is paid
   - Success mesage, will send a message back to the user after a successful payment, for example a thank you note
   - Success URL, will send back a clickable link to the user. Access to some hidden content, or a download link

2. Use the shareable link or view the LNURLp you just created\
   ![LNURLp](https://i.imgur.com/C8s1P0Q.jpg)
   - you can now open your LNURLp and copy the LNURL, get the shareable link or print it\
     ![view lnurlp](https://i.imgur.com/4n41S7T.jpg)
