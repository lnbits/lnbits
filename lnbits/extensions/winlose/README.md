<h1>WinLose Extension</h1>
<h2>Game Credits, Satoshi payout system</h2>
Win/Lose is a game credit system that uses lnbits accounts to receive sats for credits. The system can register users with LNURL-Auth or by existing user ID's. Each user can receive payouts in sats, which can be withdrawn.

<img src="/img/wl_createuser.png">
<img src="/img/wl_usertable.png">
<img src="/img/wl_logs.png">


<h2>API endpoints - see app</h2>

<code>curl -H "Content-type: application/json" -X POST https://YOUR-LNBITS/winlose/api/v1/win -d '{"amount":"100","memo":"winlose"}' -H "X-Api-Key: YOUR_WALLET-ADMIN/INVOICE-KEY"</code>
