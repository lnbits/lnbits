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
location /.well-known/nostr.json {
   proxy_pass https://{your_lnbits}/nostrnip5/api/v1/domain/{domain_id}/nostr.json;
   proxy_set_header Host {your_lnbits};
   proxy_ssl_server_name on;
}
```