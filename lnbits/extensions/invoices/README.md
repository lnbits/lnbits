<h1>Invoices Extension</h1>
<h2>*Create invoices for your clients*</h2>
This is an extension that allows you to create invoices that you can send to your client to pay online over Lightning.

<img src="https://imgur.com/a/L0JOj4T.png">

<h2>API Endpoints</h2>

<code>curl -H "Content-type: application/json" -X POST https://YOUR-LNBITS/YOUR-EXTENSION/api/v1/EXAMPLE -d '{"amount":"100","memo":"example"}' -H "X-Api-Key: YOUR_WALLET-ADMIN/INVOICE-KEY"</code>
