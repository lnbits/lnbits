<h1>Subdomains Extension</h1>

So the goal of the extension is to allow the owner of a domain to sell their subdomain to the anyone who is willing to pay some money for it.   

## Requirements
- Free cloudflare account
- Cloudflare as a dns server provider
- Cloudflare TOKEN and Cloudflare zone-id where the domain is parked

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