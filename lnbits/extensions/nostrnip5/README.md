# Nostr NIP-05

## Allow users to NIP-05 verify themselves at a domain you control

This extension allows users to sell NIP-05 verification to other nostr users on a domain they control.

## Usage

1. Create a Domain by clicking "NEW DOMAIN"\
2. Fill the options for your DOMAIN
   - select the wallet
   - select the fiat currency the invoice will be denominated in
   - select an amount in fiat to charge users for verification
   - enter the domain (or subdomain) you want to provide verification for
      - Note, you must own this domain and have access to a web server
3. You can then use share your signup link with your users to allow them to sign up


## Installation

In order for this to work, you need to have ownership of a domain name, and access to a web server that this domain is pointed to. 

Then, you'll need to set up a proxy that points `https://{your_domain}/.well-known/nostr.json` to `https://{your_lnbits}/nostrnip5/api/v1/domain/{domain_id}/nostr.json`

Example nginx configuration

```
## Proxy Server Caching
proxy_cache_path /tmp/nginx_cache keys_zone=nip5_cache:5m levels=1:2 inactive=300s max_size=100m use_temp_path=off;

location /.well-known/nostr.json {
   proxy_pass https://{your_lnbits}/nostrnip5/api/v1/domain/{domain_id}/nostr.json;
   proxy_set_header Host {your_lnbits};
   proxy_ssl_server_name on;

   expires 5m;
   add_header Cache-Control "public, no-transform";

   proxy_cache nip5_cache;
   proxy_cache_lock on;
   proxy_cache_valid 200 300s;
   proxy_cache_use_stale error timeout invalid_header updating http_500 http_502 http_503 http_504;
}
```