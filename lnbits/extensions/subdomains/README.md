<h1>Subdomains Extension</h1>

So the goal of the extension is to allow the owner of a domain to sell their subdomain to the anyone who is willing to pay some money for it.

## Requirements

- Free cloudflare account
- Cloudflare as a dns server provider
- Cloudflare TOKEN and Cloudflare zone-id where the domain is parked

## Usage

1. Register at cloudflare and setup your domain with them. (Just follow instructions they provide...)
2. Change DNS server at your domain registrar to point to cloudflare's
3. Get Cloudflare zoneID for your domain
   <img src="https://i.imgur.com/xOgapHr.png">
4. get Cloudflare API TOKEN
   <img src="https://i.imgur.com/BZbktTy.png">  
   <img src="https://i.imgur.com/YDZpW7D.png">
5. Open the lnbits subdomains extension and register your domain with lnbits
6. Click on the button in the table to open the public form that was generated for your domain

- Extension also supports webhooks so you can get notified when someone buys a new domain
  <img src="https://i.imgur.com/hiauxeR.png">

## API Endpoints

- **Domains**
  - GET /api/v1/domains
  - POST /api/v1/domains
  - PUT /api/v1/domains/<domain_id>
  - DELETE /api/v1/domains/<domain_id>
- **Subdomains**
  - GET /api/v1/subdomains
  - POST /api/v1/subdomains/<domain_id>
  - GET /api/v1/subdomains/<payment_hash>
  - DELETE /api/v1/subdomains/<subdomain_id>

## Useful

### Cloudflare

- Cloudflare offers programmatic subdomain registration... (create new A record)
- you can keep your existing domain's registrar, you just have to transfer dns records to the cloudflare (free service)
- more information:
  - https://api.cloudflare.com/#getting-started-requests
  - API endpoints needed for our project:
    - https://api.cloudflare.com/#dns-records-for-a-zone-list-dns-records
    - https://api.cloudflare.com/#dns-records-for-a-zone-create-dns-record
    - https://api.cloudflare.com/#dns-records-for-a-zone-delete-dns-record
    - https://api.cloudflare.com/#dns-records-for-a-zone-update-dns-record
- api can be used by providing authorization token OR authorization key
  - check API Tokens and API Keys : https://api.cloudflare.com/#getting-started-requests
- Cloudflare API postman collection: https://support.cloudflare.com/hc/en-us/articles/115002323852-Using-Cloudflare-API-with-Postman-Collections
