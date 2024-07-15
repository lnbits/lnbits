---
layout: default
title: FAQ
nav_order: 5
---

# FAQ - Frequently Asked Questions

## Install options

<ul><p>LNbits is not a node management software but a ⚡️LN only accounting system on top of a funding source.</p>

<details><summary>Funding my LNbits wallet from my node it doesn't work.</summary>
<p>If you want to send sats from the same node that is the funding source of your LNbits, you will need to edit the lnd.conf file. The parameters to be included are:</p>

```
allow-circular-route=1
allow-self-payment=1
```

</details>

<details><summary>Funding source only available via tor (e.g. Start9 or Umbrel)</summary>
  <p>If you want your setup to stay behind tor then only apps, pos and wallets that have tor activated can communicate with your wallets. Most likely you will have trouble when people try to redeem your voucher through onion or when importing your lnbits wallets into a wallet-app that doesnt support tor. If you plan to let LNbits wallets interact with plain internet shops and services you should consider <a href="https://github.com/TrezorHannes/Dual-LND-Hybrid-VPS">setting up hybrid mode for your node</a>.</p>
</details>

<details><summary>Funding source is in a cloud</summary>
  <p>This means that you might not have access to some files which would allow certain administrative functions. E.g. on <a href="https://voltage.cloud/">Voltage</a> lnd.conf can not be edited. Payments from your node to LNbits wallets can therefore not be configurated in this case atm so you will need to take an extra wallet to send from funding source->wallet x->LNbits wallet (only) for the initial funding of the wallet.</p>
</details>

<details><summary>LNbits via clearnet domain</summary>
  <p><a href="https://github.com/TrezorHannes/Dual-LND-Hybrid-VPS">Step by step guide how to convert your Tor only node</a> into a clearnet node to make apps like LNbits accessible via https.</p>
</details>

<details><summary>Which funding sources can I use for LNbits?</summary>
  <p>There are several ways to run a LNbits instance funded from different sources. It is important to choose a source that has a good liquidity and good peers connected. If you use LNbits for public services your users´ payments can then flow happily in both directions. If you would like to fund your LNbits wallet via btc please see section Troubleshooting.</p>
  <p>The <a href="https://docs.lnbits.org/guide/wallets.html">LNbits manual</a> shows you which sources can be used and how to configure each.</p>
</details>

<!--Later to be added
<details><summary>Advanced setup options</summary>
  <p>more text coming soon...</p>
</details>
-->

<details><summary>Can I prevent others from generating wallets on my node?</summary>
  <p>When you run your LNbits in clearnet basically everyone can generate a wallet on it. Since the funds of your node are bound to these wallets you might want to prevent that. There are two ways to do so:</p>
  <ul>
   <li>Configure allowed users & extensions <a href="https://github.com/lnbits/lnbits/blob/main/.env.example">in the .env file</a></li>
   <li>Configure allowed users & extensions <a href="https://github.com/lnbits/usermanager">via the Usermanager-Extension</a>. You can find <a href="https://docs.lnbits.org/guide/admin_ui.html">more info about the superuser and the admin extension here</a></li>
  </ul>
  <p>Please note that all entries in the .env file will not be the taken into account once you activated the admin extension.</p>
</details>
  </ul>

## Troubleshooting

<ul><details><summary>Message "https error" or network error" when scanning a LNbits QR</summary>
<p>Bad news, this is a routing error that might have quite a lot of reasons. Let´s try a few of the most possible problems and their solutions. First choose your setup</p>
  <ul>
    <li>
      <details><summary>LNbits is running via Tor only, you can't open it on a public domain like lnbits.yourdomain.com</summary>
        <ul>
        <li>Given that you want your setup to stay like this open your LNbits wallet using the .onion URI and create it again. In this way the QR is generated to be accessible via this .onion URI so via tor only. Do not generate that QR from a .local URI, because it will not be reachable via internet - only from within your home-LAN.</li>
        <li>Open your LN wallet app that you used to scan that QR and this time by using tor (see wallet app settings).
          If the app doesn't offer tor, you can use Orbot (Android) instead. See section Installation->Clearnet for detailed instructions.</li>
        </ul>
      </details>
    </li>
    <li>
      <details><summary>LNbits is running via Tor only, you want to offer public LN services via https</summary>
       <ul>
       <li>For this we need to partially open LNbits to a clearnet (domain/IP) through a https SSL certificate. Follow the instructions from <a href="https://docs.lnbits.org/guide/installation.html#reverse-proxy-with-automatic-https-using-caddy">this LNbits caddy installation instruction</a>.
        You need to have a domain and to be able to configure a CNAME for your DNS record as well as generate a subdomain dedicated to your LNbits instance like eg. lnbits.yourdomain.com.
        You also need access to your internet router to open the https port (usually 443) and forward it your LNbits IP within your LAN (usually 80). The ports might depend on your node implementation if those ports do not work please ask for them in a help group of your node supplier.</li>
       <li>You can also follow the Apache installation option, explained in the <a href="https://docs.lnbits.org/guide/installation.html#running-behind-an-apache2-reverse-proxy-over-https">LNbits installation manual</a>.</li>
       <li>If you run LNbits from a bundle node (myNode, Start9, Umbrel,Raspiblitz etc), you can follow <a href="https://github.com/TrezorHannes/vps-lnbits">this extensive guide</a> with many options to switch your Tor only LNbits into a clearnet LNbits. For Citadel there is a HTTPS Option in your manual to activate https for LNbits in the newest version.</li>
       </ul>
    </details>
   </li>
   </ul>
</details>

<details><summary>Wallet-URL deleted, are my funds safu ?</summary>
    <ul>
      <li>
        <details><summary>Wallet on demo server demo.lnbits.com</summary>
        <p>Always save a copy of your wallet-URL, Export2phone-QR or LNDhub for your own wallets in a safe place. LNbits CANNOT help you to recover them when lost.</p>
        </details>
      </li>
      <li>
        <details><summary>Wallet on your own funding source/node</summary>
        <p>Always save a copy of your wallet-URL, Export2phone-QR or LNDhub for your own wallets in a safe place.
           You can find all LNbits users and wallet-IDs in your LNbits user manager extension or in your sqlite database.
           To edit or read the LNbits database, go to the LNbits /data folder and look for the file called sqlite.db.
           You can open and edit it with excel or with a dedicated SQL-Editor like <a href="https://sqlitebrowser.org/">SQLite browser</a>.</p>
        </details>
      </li>
    </ul>
</details>

<details><summary>Configure a comment that people see when paying to my LNURLp QR</summary>
  <p>When you create a LNURL-p, by default the comment box is not filled. That means comments are not allowed to be attached to payments.<p>
  <p>In order to allow comments, add the characters length of the box, from 1 to 250. Once you put a number there,
     the comment box will be displayed in the payment process. You can also edit a LNURL-p already created and add that number.</p>

![lnbits-lnurl-comment.png](https://i.postimg.cc/HkJQ9xKr/lnbits-lnurl-comment.png)

</details>

<details><summary>Can I deposit onchain BTC to LNbits ?</summary>
  <p>There are multiple ways to exchange sats from onchain btc to LN btc (resp. to LNbits).</p>
  <ul>
    <li>
      <details><summary>A - Via an external swap service</summary>
        <p>If the user do not have full access of your LNbits, is just an external user, can use swap services like <a href="https://boltz.exchange/">Boltz</a>, <a href="https://fixedfloat.com/">FixedFloat</a>, <a href="https://swap.diamondhands.technology/">DiamondHands</a> or <a href="https://zigzag.io/">ZigZag</a>.</p>
        <p>This is useful if you provide only LNURL/LN invoices from your LNbits instance, but a payer only has onchain sats so
           they will have to the swap those sats first on their side.</p>
        <p>The procedure is simple: user sends onchain btc to the swap service and provides the LNURL / LN invoice from LNbits as destination of the swap.</p>
      </details>
    </li>
    <li>
      <details><summary>B - Using the Onchain LNbits extension</summary>
        <p>Keep in mind that this is a separate wallet, not the LN btc one that is represented by LNbits as "your wallet" upon your LN funding source.
           This onchain wallet can be used also to swap LN btc to (e.g. your hardwarewallet) by using the LNbits Boltz or Deezy extension.
           If you run a webshop that is linked to your LNbits for LN payments, it is very handy to regularly drain all the sats from LN into onchain.
           This leads to more space in your LN channels to be able to receive new fresh sats.</p>
        <p>Procedure:</p>
          <ul>
          <li>Use Electrum or Sparrow wallet to create a new onchain wallet and save the backup seed in a safe place</li>
          <li>Go to wallet information and copy the xpub</li>
          <li>Go to LNbits - Onchain extension and create a new watch-only wallet with that xpub</li>
          <li>Go to LNbits - Tipjar extension and create a new Tipjar. Select also the onchain option besides the LN wallet.</li>
          <li>Optional - Go to LNbits - SatsPay extension and create a new charge for onchain btc.
              You can choose between onchain and LN or both. It will then create    an invoice that can be shared.</li>
          <li>Optional - If you use your LNbits linked to a Wordpress + Woocommerce page, once you create/link a watch-only wallet to your LN btc shop wallet,
              the customer will have both options to pay on the same screen.</li>
          </ul>
        </details>
    </li>
  </ul>
</details>

<details><summary>Where can I see payment details?</summary>
  <p>When you receive a payment in LNbits, the transaction log will display only a resumed type of the transaction.

![lnbits-tx-log.png](https://i.postimg.cc/gk2FMFG9/lnbits-tx-log.png)

  <p>In your transaction overview you will find a little green arrow for received and a red arrow for sended funds.<p>
  <p>If you click on those arrows, a details popup shows attached messages as well as the sender´s name if given.</p>
</details>

  <details><summary>Can I configure a name to the payments i make?</summary>
  <p>In LNbits this is currently not possible to do - but to receive. This is only possible if the sender's LN wallet supports <a href="https://github.com/lnurl/luds">LUD-18</a> (nameDesc) like e.g. <a href="https://darthcoin.substack.com/p/obw-open-bitcoin-wallet">Open Bitcoin Wallet - OBW</a> does. You will then see an alias/pseudonym in the details section of your LNbits transactions (click the arrows). Note that you can give any name there and it might not be related to the real sender´s name(!) if your receive such.</p>
![lnbits-tx-details.png](https://i.postimg.cc/yYnvyK4w/lnbits-tx-details.png)
  </p>
  </details>

<details><summary>How can I use a LNbits lndhub account in other wallet apps?</summary>
  <p>Open your LNbits with the account / wallet you want to use, go to "manage extensions" and activate the <a href="https://github.com/lnbits/lndhub">LNDHUB extension</a>.</p>
  <p>Then open the LNDHUB extension, choose the wallet you want to use and scan the QR code you want to use: "admin" or "invoice only", depending on the security level you want for that wallet.</p>
  <p>You can use <a href="https://zeusln.app">Zeus</a> or <a href="https://bluewallet.io">Bluewallet</a> as wallet apps for a lndhub account.</p>
  <p>Keep in mind: if your LNbits instance is Tor only, you must use also those apps behind Tor and open the LNbits page through your Tor .onion address.</p>
</details>
</ul>
  </ul>

## Building hardware tools

<ul>  <p>LNbits has all sorts of open APIs and tools to program and connect to a lot of different devices for a gazillion of use-cases. Let us know what you did with it ! Come to the <a href="https://t.me/makerbits">Makerbits Telegram Group</a> if you are interested in building or if you need help with a project - we got you!</p>

<details><summary>ATM - deposit and withdraw in your shop or at your meetup</summary>
  <p>This is a do-it-yourself project consisting of a mini-computer (Raspberry Pi Zero), a coin acceptor, a display, a 3D printed case, and a Bitcoin Lightning wallet as a funding source. It exchanges fiat coins for valuable Bitcoin Lightning ⚡ Satoshis. The user can pick up the Satoshis via QR code (LNURL-withdraw) on a mobile phone wallet. You can get the components as individual parts and build the case yourself e.g. from <a href="https://www.Fulmo.org">Fulmo</a> who also made a <a href="https://blog.fulmo.org/the-lightningatm-pocket-edition/">guide</a> on it. The shop offers payments in Bitcoin and Lightning ⚡. The code can be found on <a href="https://github.com/21isenough/LightningATM">the ATM github project page></a>.</p>
</details>

<details><summary>POS Terminal - an offline terminal for merchants</summary>
  <p>The LNpos is a self-sufficient point of sale terminal which allows offline onchain payments and an offline Lightning ATM for withdrawals. Free and open source software, free from intermediaries, with integrated battery, WLAN, DIY. You can get the 3D print as well as the whole kit from the LNbits shop from 👇 Resources. It allows
    <li>LNPoS Online interactive Lightning payments</li>
    <li>LNURLPoS Offline Lightning Payments. Passive interaction, sharing a secret as evidence</li>
    <li>OnChain For onchain payments. Generates an address and displays a link for verification</li>
    <li>LNURLATM Offline Lightning Payouts. Generates LNURLw link to do withdrawals</li>
    <p>
      <img width="285" alt="Bildschirm­foto 2023-01-20 um 18 09 34" src="https://user-images.githubusercontent.com/63317640/213761202-4c4d8531-7184-4e53-8645-fe0f08ac7d17.png">
      </p>
</p>
</details>

<details><summary>Hardware Wallet- build your own, stack harder</summary>
<p>The hardwarewallet is a very cheap solution for builders. The projects´ <a hrel="https://github.com/lnbits/hardware-wallet">code and installation instructions for the LNbits hardware wallet can be found on github</a></p>
  <p>
    <img width="546" alt="Bildschirm­foto 2023-01-20 um 18 08 37" src="https://user-images.githubusercontent.com/63317640/213760948-38fd77b0-9247-4505-9433-f5af1b223527.png">
  </p>
</details>

<details><summary>Bitcoin Switch - turn things on with bitcoin</summary>
  <p>Candy dispenser, vending machines (online), grabbing machines, jukeboxes, bandits and <a href="https://github.com/cryptoteun/awesome-lnbits">all sorts of other things have already been build with LNbits´ tools</a>. Further info see 👇 Resources.</p>
<p>
  <img width="549" alt="Bildschirm­foto 2023-01-20 um 18 11 55" src="https://user-images.githubusercontent.com/63317640/213761646-d25d4745-e50d-4389-98e5-f83237a8cf6b.png">
  </p>
</details>

<details><summary>Vending machine (offline)</summary>
<p>This code works similar to the LNpos. Note that the <a href=" https://www.youtube.com/watch?v=Fg0UuuzsYXc&t=762s">setup-video for the vending machine</a> misses the new way of installing it via the new LNURLdevices extension. The <a href="https://github.com/arcbtc/LNURLVend">vending machine project code resides on github</a>.</p>
  <p>
    <img width="753" alt="Bildschirm­foto 2023-01-20 um 18 13 22" src="https://user-images.githubusercontent.com/63317640/213761946-5025a7b8-c6d4-40cf-a6d3-d298593e79f6.png">
    </p>
</details>

<details><summary><b>Resources - Building hardware tools</b></summary>
  <ul>
  <li><a href="https://t.me/makerbits'">MakerBits</a> - Telegram support group</li>
  <li><a href="https://ereignishorizont.xyz/">Instructions for LNpos, Switch, ATM, BTCticker</a> - guides in DE & EN</li>
  <li><a href="https://shop.lnbits.com/">LNbits shop</a> - readymade hardware gimmicks from the community</li>
  <li><a href="https://github.com/cryptoteun/awesome-lnbits#hardware-projects-utilizing-lnbits">Collection of hardware projects using LNbits</a></li>
  </ul>
</details>
  </ul>

## Use cases of LNbits

<ul><details><summary>Merchant</summary>
  <p>LNbits is a powerful solution for merchants, due to the easy setup with various extensions, that can be used for many scenarios.</p>
  <p><a href="https://darthcoin.substack.com/p/lnbits-for-small-merchants">Here is an overview of the LNbits tools available for a small restaurant as well as a hotel</a></p>
</details>

<details><summary>Swapping ⚡️LN BTC to a BTC address</summary>
  <p>LNbits has two swap extensions integrated: <a href="https://github.com/lnbits/boltz-extension/">Boltz</a> and <a href="hhttps://github.com/lnbits/deezy">Deezy</a>.</p>
  <p>For a merchant that uses LNbits to receive BTC payments through LN, this is very handy to move the received sats from LN channels into onchain wallets. It not only helps you HODLing but is also freeing up "space in your channels" so you are ready to receive more sats.</p>
  <p>Boltz has an option to setup an automated swap triggered by a certain amount received.</p>
</details>

<details><summary>Voucher</summary>
  <p>Printed voucher links or tippingcards</p>
  <p>To generate voucher you will need LNbits to be available in clearnet. Please consider running your own LNbits instance for this.</p>
  <p>LNURLw are strings that represent a faucet-link to a wallet. By scanning it, everyone will be able to withdraw sats from it. A LNURLw can be either a QR that leads to a static link or to one that responds with new invoices every time it is scanned (click "no assmilking"). You can create these QR by adding the LNURLw extension and generate the vouchertype you need.</p>
  <ul>
    <li>Voucher can as well be printed directly from LNbits. After you created it, click the "eye" next to the link. By pressing the printer-button you print the plain QR but you could as well integrate it into a nice tippincard or voucher template by choosing "Advanced voucher" -> "Use custom voucher design". We collected some designs as well as templates to make your own ones under <a href="https://youtu.be/c5EV9UNgVqk">this LNbits voucher video-guide.</a>. You will be able to create and print as much voucher as you like with it. Happy orangepilling!</li>
    <li> Note that your LNbits needs to be reachable in clearnet to offer vouchers to others.</li>
  </ul>
</details>

<details><summary>NFC Cards, Badges, Rings etc.</summary>
  <p>Creating a NFC card for a wallet</p>
  <p>To generate links for your cards you will need LNbits to be available in clearnet. Please consider running your own LNbits instance for this.</p>
  <ul>
    <li>On top to just printing voucher for your wallet you can also <a href="https://youtu.be/CQz1ILcK0PY">write these LNURLw to a simple NFC card fromon NTAG216</a> by not clicking the printer but the NFC symbol on android/chrome and tapping your card against the device. This will enable the cardholder to directly spend those sats at a tpos, pos or wallet-app another one uses that can handle lightning payments via NFC. </li>
    <li>If you run an event and want to hand out bigger amounts of cards with simple voucher links on consider this <a hrel="nfc-brrr.com/">NFC-brrr batch tool</a> as well as using NTAG424 cards, so that your customers can rewrite them later with an own wallet and the boltcard service (see ff)</li>
    <li>For bigger amounts the Boltcard-Extension should be used. It will generate a link that sends a new invoice every time it is used for payments and keeps track too if the allowed card-ID is redeeming funds. Hence the setup of Boltcards is a bit safer but it needs some additional tools. You can find <a href="https://plebtag.com/write-tags/">further infos on creating or updating boltcards here</a>.</li>
  </ul><p>
<ul><details><summary>Resources - NFC & LNbits</summary>
  <ul>
     <li><a href="https://www.boltcard.org">Coincorner Boltcard</a></li>
     <li><a href="https://www.plebtag.com">PlebTag (infos, Lasercards, Badges)</a></li>
     <li><a href="https://www.lasereyes.cards">Lasercards</a></li>
     <li><a href="https://www.bitcoin-ring.com">Bitcoin Ring</a></li>
     <li><a href="https://github.com/taxmeifyoucan/HCPP2021-Badge">Badge</a></li>
     <li><a href="https://github.com/cryptoteun/awesome-lnbits#powered-by-lnbits">Powered by LNbits examples</a></li>
  </ul>
  </ul>
  </p>
</details>
  </details>

</ul>

## Developing for LNbits

 <ul>
    <li><a href="https://docs.lnbits.org/devs/development.html">Making extensions / How to use Websockets / API reference</a></li>
    <li><a href="https://t.me/lnbits">Telegram LNbits Support Group</a></li></ul>
</ul>
