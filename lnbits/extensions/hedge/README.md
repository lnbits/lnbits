<h1>Hedge Extension</h1>

<h2>Create synthetic stables automatically!</h2>

The HedgedWallet extension allows you to integrate [Kollider Hedge Service](https://github.com/standardsats/kollider-hedge) with LNBits.

Kollider client works with Postgres so it is good to have LNBits instance running on Postgres too.

<h2>How to set it up</h2>

1. Simply bind any available wallet in the extension menu
2. Make sure you have funds on your account
3. It will request to open new short position on every incoming payment for binded wallet and request for long position when sats are spent from the same wallet.

