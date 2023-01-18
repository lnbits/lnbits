---
layout: default
title: FAQ
nav_order: 5
---


Frequently  Asked Questions
===============

<details><summary>"Network error" when scanning a QR. What can I do?</summary>
  <p>A - If your LNbits is running only behind Tor (so if you can't see it on clearnet), you have to:</p>
  <ul>
    <li>Open your LNbits using the .onion URI, so the QR is generated using an accessible .onion URI. Do not generate that QR from a .local URI, because it will not be visible on the internet, only in your home LAN.</li>
    <li>Open your LN wallet app that you use to scan that QR and configure it to use Tor to be able to read that .onion URI. If the app doesn't have a Tor option, you can use Orbot (Android).</li>
  </ul>
  <p>B - If you run LNbits over Tor and want to offer public LN services, you should consider opening it to the clearnet (domain/IP) via a https SSL certificate.</p>
  <ul>
    <li>The easiest way (2 min setup) to do so is to use Caddy. Just follow the instructions from <a href="https://docs.lnbits.org/guide/installation.html#reverse-proxy-with-automatic-https-using-caddy">here</a> and your LNbits will be accesible through https clearnet.
        You need to have a domain and to be able to configure a subdomain for your LNbits instance in your DNS records as CNAME like e.g. lnbits.mydomain.com.
        Also you need access to your internet router to open the port 443 and forward requests to your LNbits IP within your LAN.</li>
    <li>You can also use the apache option, explained in the <a href="https://docs.lnbits.org/guide/installation.html#running-behind-an-apache2-reverse-proxy-over-https">LNbits installation manual</a>.</li>
    <li>If you run LNbits via a bundle node (Umbrel, Citadel, myNode, Embassy, Raspiblitz etc), you can follow <a href="https://github.com/TrezorHannes/vps-lnbits">this extensive guide</a> with many options to switch your Tor only LNbits into a clearnet LNbits.
  
</details>

<details><summary>Where can I see payment details?</summary>
<p>
When you receive a payment in Lnbits, the transactions will display only a resumed type of the transaction. Like this:

![lnbits-tx-log.png](https://i.postimg.cc/gk2FMFG9/lnbits-tx-log.png)

As you can see on the left side, there's a little green arrow for receiving and a red arrow for sending.
If you click that arrow, a screen will pop up with more details about the tx, including the message and the name attached to it.
</p>
<p>
If the sender's LN wallet supports <a href="https://github.com/lnurl/luds">LUD-18</a> (nameDesc) you will also be shown an alias/pseudonym preceeding the comment here. This is optional and only if the sender wants to send that name. Pls be aware that these names are not verified and can be freely chosen! It can be any name and is not at all related a real name possibly.
</p>

![lnbits-tx-details.png](https://i.postimg.cc/yYnvyK4w/lnbits-tx-details.png)

</details>

<details><summary>Can I receive a comment/message for deposits made to my LNURLp QRs?</summary>
<p>
When you create a LNURLp, by default the comment box is not filled resp. the amount of characters is set to 0. That means comments are not allowed to be attached to payments. In order to allow comments, add the characters length within a range of 1 to 250. Once you put a number there, the comment box will be displayed to your customers in the payment process. You can also edit a LNURLp already created and add that number later.

![lnbits-lnurl-comment.png](https://i.postimg.cc/HkJQ9xKr/lnbits-lnurl-comment.png)

</p>
</details>

<details><summary>Can i deposit onchain btc to LNbits ?</summary>
<p>There are multiple ways to exchange sats from onchain btc to LN btc (resp. to LNbits).</p>
<p>A - Via a swap service like <a href="https://boltz.exchange/">Boltz</a>, <a href="https://fixedfloat.com/">FixedFloat</a>, <a href="https://swap.diamondhands.technology/">DiamondHands</a> or <a href="https://zigzag.io/">ZigZag</a>.</p>
<p>This is useful if you provide only LNURL/LN invoices from your LNbits instance, but a payer only has onchain sats so 
  they will have to the swap those sats first on their side.</p>
<p>The procedure is simple: user sends onchain btc to the swap service and provides the LNURL / LN invoice from LNbits as destination of the swap.</p>
<p>B - Using the Onchain LNbits extension</p>
<p>Keep in mind that this is a separate wallet, not the LN btc one that is represented by LNbits as "your wallet" upon your LN funding source. This onchain wallet can be used also to swap LN btc to (e.g. your hardwarewallet) by using the LNbits Boltz or Deezy extension. If you run a webshop that is linked to your LNbits for LN payments, it is very handy to regularily drain all the sats from LN into onchain. This leads to more space in your LN channels to be able to receive new fresh sats.</p>
<p>Procedure </p>
<ul>
<li>Use Electrum or Sparrow wallet to create a new onchain wallet and save the backup seed in a safe place</li>
<li>Go to wallet information and copy the xpub</li>
<li>Go to LNbits - Onchain extension and create a new watch-only wallet with that xpub</li>
<li>Go to LNbits - Tipjar extension and create a new Tipjar. Select also the onchain option besides the LN wallet.</li>
<li>Optional - Go to LNbits - SatsPay extension and create a new charge for onchain btc. You can choose between onchain and LN or both. It will then create an invoice that can be shared.</li>
<li>Optional - If you use your LNbits linked to a Wordpress + Woocommerce page, once you create/link a watch-only wallet to your LN btc shop wallet, the customer will have both options to pay on the same screen.</li>
</ul>

</details>

<details><summary>I lost my Wallet-URL. Are my funds gone?</summary>
<p>A - LNbits non-custodian, you own the funding source</p>
 <ul>
    <li>No. LNbits is a frontend for your Node / funding source. All transactions and invoices are just transported to you by LNbits and it holds no separate funds. The wallets and configurations you created might be gone if you did not backup your LNbits database but funds will never be held bei LNbits itself. </li>
  <ul>
<p>B - Lnbits custodian, you used legend.lnbits or similar</p>
 <ul>
    <li>Yes, possibly. On a funding source with lots of wallets it will be impossible to find yours back in the database. Remember to not store a lot of sats on custodian nodes - run your own node and LNbits.</p>
</details>	


<details><summary>Printed voucher links or tippingcards</summary>
<p>To write cards you will need LNbits to be available in clearnet. Please consider running your own LNbits instance for this.</p>
 <ul>
LNURLw are strings that represent a faucet-link to a wallet. By scanning it, everyone will be able to withdraw sats from it. A LNURLw can be either a QR that leads to a static link or to one that responds with new invoices every time it is scanned (click "no assmilking"). You can create these QR by adding the LNURLw extension and generate the vouchertype you need. <ul>
    <li>Voucher can as well be printed directly from LNbits. After you created it, click the "eye" next to the link. By pressing the printer-button you print the plain QR but you could as well integrate it into a nice tippincard or voucher template by choosing "Advanced voucher" -> "Use custom voucher design". We collected some designs as well as templates to make your own ones under <href="https://youtu.be/c5EV9UNgVqk">this LNbits voucher video-guide.</a>. You will be able to create and print as much voucher as you like with it. Happy orangepilling!</li>
  <li>  Note that your LNbits needs to be reachable in clearnet to offer vouchers to others. </li>
  </details>
  
  <details><summary>Creating a NFC card for a wallet</summary>
 <p>To write cards you will need LNbits to be available in clearnet. Please consider running your own LNbits instance for this.</p>
    <li>On top to just printing voucher for your wallet you can also <a href="https://youtu.be/CQz1ILcK0PY">write these LNURLw to a simple NFC card fromon NTAG216</a> by not clicking the printer but the NFC symbol on android/chrome and tapping your card against the device. This will enable the cardholder to directly spend those sats at a tpos, pos or wallet-app another one uses that can handle lightning payments via NFC. </li>
    <li>If you run an event and want to hand out bigger amounts of cards with simple voucher links on consider this <a hrel="nfc-brrr.com/">NFC-brrr batch tool</a> as well as using NTAG424 cards, so that your customers can rewrite them later with an own wallet and the boltcard service (see ff)</li>
<li>For bigger amounts the Boltcard-Extension should be used. It will generate a link that sends a new invoice every time it is used for payments and keeps track too if the allowed card-ID is redeeming funds. Hence the setup of Boltcards is a bit safer but it needs some additional tools. You can find <a href="https://plebtag.com/write-tags/">further infos on creating or updating boltcards here</a>.
  </details>


  <details><summary>Building with LNbits</summary>
 <p>LNbits has all sorts of open APIs and tools to program and connect to a lot of different devices for several use-cases.</p>
 <li>Hardware Wallet - build your own, stack harder</li>
 <li>Bitcoin Switch - turn things on with bitcoin</li>
 <li>ATM - deposit and withdraw in your shop or at your meetup</li>
 <li>LNpos - a offline hardware device for merchants</li>
 <li>LNvend - offline vending machine</li>
 <p>Grabbing machines, jukeboxes, bandits, candy cispenser, beertaps and <a href="https://github.com/cryptoteun/awesome-lnbits">all sorts of other things have already been build with these LNbits tools</a>. Let us know what you did with it ! Come to the <a href="https://t.me/makerbits">Makerbits Telegram Group</a> if you are interested in building with LNbits or if you need help with a projekt - we got you! </details>
 

<details><summary>Can I prevent others from generating wallets on my node?</summary>
 <p>When you run your LNbits in clearnet basically everyone can generate a wallet on it. Since the funds of your node are bound to these wallets you might want to prevent that. There are two ways to do so
 <li>configure the allowed users / extensions <a href="https://github.com/lnbits/lnbits/blob/main/.env.example">in the .env file</a><li>
 <li>configure the allowed users / extensions <a href="https://github.com/lnbits/lnbits/tree/main/lnbits/extensions/usermanager">via the Usermanager-Extension</a>. You can find <a href="http://docs.lnbits.org/guide/admin_ui.html">more info about the superuser and the admin extension here</a>
 Please not that all entries in the .env file will not be the taken into account anylonger after you activated the admin extension.
 </p>
 </details>
 
 <details><summary>Which funding sources except my node can i use ?</summary>
 <p>The <a href="http://docs.lnbits.org/guide/wallets.html">new LNbits manual</a> will show you which sources you can use and how to configure each here</a>
</p>
 </details>

 <details><summary>Funding my LNbits wallet from my node doesnt work.</summary>
<p>You will need to edit the lnd.conf file for this. The parameter to be included are allow-circular-route=1 respectively allow_self_payment=1. 
 </p>
 </details>
