------
layout: default
title: FAQ
nav_order: 5
---



FAQ - Frequently Asked Questions on LNbits
==========================================

<h2>Install options</h2>
<ui><ul>
    <p>LNbits is not a node management software but a lightning only accounting system on top of a funding source.</p>
  
<details><summary>Funding my LNbits wallet from my node doesnt work.</summary>
<p>You will need to edit the lnd.conf file for this. The parameter to be included are <i>allow-circular-route=1 </i> respectively <i>allow_self_payment=1</i>. 
 </p>
 </details>
  
<details><summary>Funding source only available via tor (Umbrel, Citadel, ..)</summary>
    <ul><p>
        </p></ul>
    </details>
    
<details><summary>Funding source is in a cloud</summary>
    <ul><p>Voltage: lnd.conf cannot be edited atm
        </p></ul>
    </details>
    
<details><summary>LNbits via clearnet domain</summary>
    <ul><p>trezor hannes
        </p></ul>
</details>
    
<details><summary>Other funding sources (e.g bots)</summary>
    <ul>
 <p>The <a href="http://docs.lnbits.org/guide/wallets.html">new LNbits manual</a> shows you which sources you can use and how to configure each here</a>
        </p></ul>
</details>
    
<details><summary>Advanced setup options</summary>
    <ul><p>
      <details><summary>Can I prevent others from generating wallets on my node?</summary>
 <p>When you run your LNbits in clearnet basically everyone can generate a wallet on it. Since the funds of your node are bound to these wallets you might want to prevent that. There are two ways to do so
 <li>configure the allowed users / extensions <a href="https://github.com/lnbits/lnbits/blob/main/.env.example">in the .env file</a>
 <li>configure the allowed users / extensions <a href="https://github.com/lnbits/lnbits/tree/main/lnbits/extensions/usermanager">via the Usermanager-Extension</a>. You can find <a href="http://docs.lnbits.org/guide/admin_ui.html">more info about the superuser and the admin extension here</a>
 Please not that all entries in the .env file will not be the taken into account anylonger after you activated the admin extension.
 </p>
 </details>
  </ul>
    </p></ul>
</details>
</ui></ul>



<h2>Troubleshooting</h2>
<ui><ul>
  <details><summary>Message "https error" or network error" when scanning a QR made on LNbits</summary><ui>
<p>Bad news, this is a routing error that might have quite a lot of reasons. Lets try a few of the most possible problems and their solutions. </p>
  <p>A - LNbits is running behind Tor only, you can't open it on a public domain like lnbits.yourdomain.com</p>

    <li>Open your LNbits LNURL page using the .onion URI, so the QR is generated using an accessible .onion URI. Do not generate that QR from a .local URI, because it will not be visible over internet, only in your LAN.</li>
    <li>Open your LN wallet app that you use to scan that QR, using Tor connection. Otherwise your app cannot read that .onion URI. If the app it doesn't have integrated Tor, you can use Orbot (Android).</li>
  </ui>
  <p>B - If you run your LNbits over Tor and want to offer public LN services, you should consider to move it to a clearnet (domain/IP) access, with https SSL certificate.</p>
  <ul>
    <li>The easiest way (2 min setup) is to use Caddy. Just follow the instructions from <a href="https://docs.lnbits.org/guide/installation.html#reverse-proxy-with-automatic-https-using-caddy">here</a> and your LNbits will be accesible through clearnet https.
        You must have a domain and be able to configure in your DNS records a subdomain for your LNbits instance (eg. lnbits.mydomain.com).
        Also you need access to your internet router to open the port 443 and forward it your LNbits IP machine in your LAN.</li>
    <li>You can also use apache option, explained in the <a href="https://docs.lnbits.org/guide/installation.html#running-behind-an-apache2-reverse-proxy-over-https">LNbits installation manual</a>.</li>
    <li>If you LNbits run in a bundle node (Umbrel, Citadel, myNode, Embassy, Raspiblitz etc), you can follow <a href="https://github.com/TrezorHannes/vps-lnbits">this extensive guide</a> with many options to make your Tor only LNbits into a clearnet LNbits.
    </ui> </details>

  <details><summary>Wallet-URL deleted, are funds safu ?</summary>
    <ul>
      <p>
       <details><summary>Wallet on demo server legend.lnbits</summary><p>Always save a copy of your wallet-URL, Export2phone-QR or LNDhub for your own wallets in a safe place. LNbits CANNOT help you to recover them when lost.
      </details>     
      </p>
     
      <p>
      <details><summary>Wallet on your own funding source/node</summary><p>Always save a copy of your wallet-URL, Export2phone-QR or LNDhub for your own wallets in a safe place. You can find all LNbits wallet-IDs in your LNbits database. 
         </ul>
      </details> 
    </p></ul>
    
  </details></ul>
 
 
 

<h2>Building hardware tools</h2>
<ul>
  <p>LNbits has all sorts of open APIs and tools to program and connect to a lot of different devices for several use-cases. Let us know what you did with it ! Come to the <a href="https://t.me/makerbits">Makerbits Telegram Group</a> if you are interested in building with LNbits or if you need help with a projekt - we got you! </p>

 
 <details><summary>ATM - deposit and withdraw in your shop or at your meetup</summary>
    <ul><p>
        </p></ul>
</details>
  
<details><summary>POS Terminal - an offline terminal for merchants</summary>
    <ul><p>
        </p></ul>
    </details>
    
<details><summary>Hardware Wallet- build your own, stack harder</summary>
    <ul><p>
        </p></ul>
</details>
    
<details><summary>Bitcoin Switch - turn things on with bitcoin</summary>
    <ul><p>Candy dispenser, vending machines (online), grabbing machines, jukeboxes, bandits and <a href="https://github.com/cryptoteun/awesome-lnbits">all sorts of other things have already been build with LNbits´ tools</a>. 
        </p></ul>
</details>
    
<details><summary>Vending machine (offline)</summary>
    <ul><p>
        </p></ul>
    </details>

  <p><b>Ressources</b><ul>
  <li><a href="https://t.me/makerbits'">makerbits support Group</a></li>
  <li><a href="ereignishorizont.xyz/">Building Instructions by Axel</a></li>
  <li><a href="https://shop.lnbits.com/">LNbits shop</a></li>
  </ul></ul><p>



<h2>Use cases of LNbits</h2>
<ui><ul>
<details><summary>Merchant</summary>
    <ul><p>
        </p></ul>
</details>

<details><summary>Voucher</summary>
    <ul><p>
        </p></ul>
</details>
</ui>

<details><summary>NFC Cards, Badges, Rings etc.</summary>
    <ul><p>
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
        </p></ul>

      <p><b>Ressources</b><ul>
<li><a href="https://www.plebtag.com">PlebTag, infos, Lasercards, Badges</a></li>
<li><a href="https://www.boltcard.org">Coincorner Boltcard</a></li>
<li><a href="https://www.lasereyes.cards">Lasercards</a></li>
<li><a href="https://www.bitcoin-ring.com">Bitcoin Ring</a></li>
<li><a href="https://github.com/taxmeifyoucan/HCPP2021-Badge">Badge</a></li>
      </ul></ul><p>
  </details></ul>
</ui>


    
<h2>Developing for LNbits</h2>
<ui><ul>
<li><a href="http://docs.lnbits.org/devs/development.html">Making Estension / how to use Websockets / API reference</a></li>
  <li><a href="https://t.me/lnbits">Telegram LNbits Support Group</a></li></ul>
</ui>



<h2>Did you know?</h2>
<ul>
<details><summary>Where can I see payment details?</summary>
<p>
When you receive a payment in Lnbits, the transaction log will display only a resumed type of the transaction. Like this:

![lnbits-tx-log.png](https://i.postimg.cc/gk2FMFG9/lnbits-tx-log.png)

As you can see on the left side, there's a little green arrow for receiveing or red arrow for sending.
If you click on that arrow, will popup a screen with more details about the transaction, including the message and the name attached to the payment.
</p>
<p>
If the sender's LN wallet support <a href="https://github.com/lnurl/luds">LUD-18</a> (nameDesc) will also insert an alias/pseudonym preceeding the comment. This is optional and only if the sender want to send that name. It can be any name and not related to real names.
</p>

![lnbits-tx-details.png](https://i.postimg.cc/yYnvyK4w/lnbits-tx-details.png)

</details>

<details><summary>Can I receive a comment/message to my LNURL-p QR?</summary>
<p>
When you create a LNURL-p, by default the comment box is not filled. That means comments are not allowed to be attached to payments.
In order to allow comments, add the characters lenght of the box, from 1 to 250. Once you put a number there, the comment box will be displayed in the payment process. You can also edit a LNURL-p already created and add that number.

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
  </ul>
</details>

