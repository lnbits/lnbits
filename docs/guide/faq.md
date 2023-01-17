---
layout: default
title: FAQ
nav_order: 5
---


Frequently  Asked Questions
===============

<details><summary>Where can I see payment details?</summary>
<p>
When you receive a payment in Lnbits, the transaction log will display only a resumed type of the transaction. Like this:

![lnbits-tx-log.png](https://i.postimg.cc/gk2FMFG9/lnbits-tx-log.png)

As you can see on the left side, there's a little green arrow for receiveing or red arrow for sending.
If you click on that arrow, will popup a screen with more details about the transaction, including the message and the name attached to the payment.
</p>
<p>
If the sender's LN wallet support [LUD-18](https://github.com/lnurl/luds) (nameDesc) will also insert an alias/pseudonym preceeding the comment. This optional and only if the sender want to send that name. It can be any name and not related to real names.
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

<details><summary>How someone can deposit to my LNbits using onchain TX?</summary>
<p>There are multiple ways to get sats from onchain into LN (LNbits). Depends on the case scenario you are in.</p>
<p>Here are some options:</p>
<p>A - Using a swap service like: [Boltz](https://boltz.exchange/) or [FixedFloat](https://fixedfloat.com/) or [DiamondHands](https://swap.diamondhands.technology/) or [ZigZag](https://zigzag.io/).</p>
<p>This is the case when you provide to the payer only a LNURL/LN invoice from your LNbits instance, but payer have only onchain sats. So will have to the swap first on his side.</p>
<p>The procedure is simple: user will send onchain to the swap service, then will provide the LNURL or LN invoice from LNbits as destination of the swap.</p>
<p>B - Using the Onchain LNbits extension.</p>
<p>Keep in mind that this would be a separate wallet, not the LNbits one (your LN node behind your LNbits). Is better to use a separate one. This onchain wallet can be used also with the LNbits Boltz or Deezy extension, for swaps from LN into onchain. If you have a webshop linked to your LNbits for LN payments, it is very handy to drain all the sats from LN into onchain at the end of the day or when you have too much payments received. In this way you have more space in your LN channels to receive more.</p>
<p>Procedure steps:</p>
<ul>
<li>Use Electrum or Sparrow wallet to create a new onchain wallet. Save the backup seed in a safe place.</li>
<li>Go to wallet information and copy the xpub.</li>
<li>Go to LNbits - Onchain extension and create a new watch-only wallet with that xpub.</li>
<li>Go to LNbits - Tipjar extension and create a new Tipjar. Select also the onchain option besides the LN wallet.</li>
<li>Optional - Go to LNbits - SatsPay extension and create a new charge. You can choose between onchain and LN or both. It will create a invoice charge that can be shared.</li>
<li>Optional - If you use your LNbits linked to a Wordpress + Woocommerce page, once you create a watch-only wallet in your LNbits, the customer will have the both options to pay onchain and LN, in the same screen.</li>
</ul>

</details>
