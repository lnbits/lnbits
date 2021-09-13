<h1>Lightning Address</h1>
<h2>Rent Lightning Addresses on your domain</h2>
LNAddress extension allows for someone to rent users lightning addresses on their domain.

The extension is muted by default on the .env file and needs the admin of the LNbits instance to meet a few requirements on the server.

## Requirements

- Free Cloudflare account
- Cloudflare as a DNS server provider
- Cloudflare TOKEN and Cloudflare zone-ID where the domain is parked

The server must provide SSL/TLS certificates to domain owners. If using caddy, this can be easily achieved with the Caddyfife snippet:

```
:443 {
    reverse_proxy localhost:5000

    tls <your email>@example.com {
      on_demand
    }
}
```

fill in with your email.

Certbot is also a possibity.

## Usage

1. Before adding a domain, you need to add the domain to Cloudflare and get an API key and Secret key\
   ![add domain to Cloudflare](https://i.imgur.com/KTJK7uT.png)\
   You can use the _Edit zone DNS_ template Cloudflare provides.\
   ![DNS template](https://i.imgur.com/ciRXuGd.png)\
   Edit the template as you like, if only using one domain you can narrow the scope of the template\
   ![edit template](https://i.imgur.com/NCUF72C.png)

2. Back on LNbits, click "ADD DOMAIN"\
   ![add domain](https://i.imgur.com/9Ed3NX4.png)

3. Fill the form with the domain information\
   ![fill form](https://i.imgur.com/JMcXXbS.png)

   - select your wallet - add your domain
   - cloudflare keys
   - an optional webhook to get notified
   - the amount, in sats, you'll rent the addresses, per day

4. Your domains will show up on the _Domains_ section\
   ![domains card](https://i.imgur.com/Fol1Arf.png)\
   On the left side, is the link to share with users so they can rent an address on your domain. When someone creates an address, after pay, they will be shown on the _Addresses_ section\
   ![address card](https://i.imgur.com/judrIeo.png)

5. Addresses get automatically purged if expired or unpaid, after 24 hours. After expiration date, users will be granted a 24 hours period to renew their address!

6. On the user/buyer side, the webpage will present the _Create_ or _Renew_ address tabs. On the Create tab:\
   ![create address](https://i.imgur.com/lSYWGeT.png)
   - optional email
   - the alias or username they want on your domain
   - the LNbits URL, if not the same instance (for example the user has an LNbits wallet on https://s.lnbits.com and is renting an address from https://lnbits.com)
   - the _Admin key_ for the wallet
   - how many days to rent a username for - bellow shows the per day cost and total cost the user will have to pay
7. On the Renew tab:\
   ![renew address](https://i.imgur.com/rzU46ps.png)
   - enter the Alias/username
   - enter the wallet key
   - press the _GET INFO_ button to retrieve your address data
   - an expiration date will appear and the option to extend the duration of your address
