## Nostr Diagon Alley protocol (for resilient marketplaces)

#### Original protocol https://github.com/lnbits/Diagon-Alley

> The concepts around resilience in Diagon Alley helped influence the creation of the NOSTR protocol, now we get to build Diagon Alley on NOSTR!

In Diagon Alley, `merchant` and `customer` communicate via NOSTR relays, so loss of money, product information, and reputation become far less likely if attacked.

A `merchant` and `customer` both have a NOSTR key-pair that are used to sign notes and subscribe to events. 

#### For further information about NOSTR, see https://github.com/nostr-protocol/nostr


## Terms

* `merchant` - seller of products with NOSTR key-pair
* `customer` - buyer of products with NOSTR key-pair
* `product` - item for sale by the `merchant`
* `stall` - list of products controlled by `merchant` (a `merchant` can have multiple stalls)
* `marketplace` - clientside software for searching `stalls` and purchasing `products`

## Diagon Alley Clients

### Merchant admin

Where the `merchant` creates, updates and deletes `stalls` and `products`, as well as where they manage sales, payments and communication with `customers`. 

The `merchant` admin software can be purely clientside, but for `convenience` and uptime, implementations will likely have a server listening for NOSTR events.

### Marketplace

`Marketplace` software should be entirely clientside, either as a stand-alone app, or as a purely frontend webpage. A `customer` subscribes to different merchant NOSTR public keys, and those `merchants` `stalls` and `products` become listed and searchable. The marketplace client is like any other ecommerce site, with basket and checkout. `Marketplaces` may also wish to include a `customer` support area for direct message communication with `merchants`.

## `Merchant` publishing/updating products (event)

NIP-01 https://github.com/nostr-protocol/nips/blob/master/01.md uses the basic NOSTR event type.

The `merchant` event that publishes and updates product lists

The below json goes in `content` of NIP-01.

Data from newer events should replace data from older events.  

`action` types (used to indicate changes):
* `update` element has changed
* `delete` element should be deleted
* `suspend` element is suspended
* `unsuspend` element is unsuspended


```
{
    "name": <String, name of merchant>,
    "description": <String, description of merchant>,
    "currency": <Str, currency used>,
    "action": <String, optional action>,
    "shipping": [
        {
            "id": <String, UUID derived from stall ID>,
            "zones": <String, CSV of countries/zones>,
            "price": <int, cost>,
        },
        {
            "id": <String, UUID derived from stall ID>,
            "zones": <String, CSV of countries/zones>,
            "price": <int, cost>,
        },
        {
            "id": <String, UUID derived from stall ID>,
            "zones": <String, CSV of countries/zones>,
            "price": <int, cost>,
        }
    ],
    "stalls": [
        {
            "id": <UUID derived from merchant public-key>,
            "name": <String, stall name>,
            "description": <String, stall description>,
            "categories": <String, CSV of voluntary categories>,
            "shipping": <String, CSV of shipping ids>,
            "action": <String, optional action>,
            "products": [
                {
                    "id": <String, UUID derived from stall ID>,
                    "name": <String, name of product>,
                    "description": <String, product description>,
                    "categories": <String, CSV of voluntary categories>,
                    "amount": <Int, number of units>,
                    "price": <Int, cost per unit>,
                    "images": [
                        {
                            "id": <String, UUID derived from product ID>,
                            "name": <String, image name>,
                            "link": <String, URL or BASE64>
                        }
                    ],
                    "action": <String, optional action>,
                },
                {
                    "id": <String, UUID derived from stall ID>,
                    "name": <String, name of product>,
                    "description": <String, product description>,
                    "categories": <String, CSV of voluntary categories>,
                    "amount": <Int, number of units>,
                    "price": <Int, cost per unit>,
                    "images": [
                        {
                            "id": <String, UUID derived from product ID>,
                            "name": <String, image name>,
                            "link": <String, URL or BASE64>
                        },
                        {
                            "id": <String, UUID derived from product ID>,
                            "name": <String, image name>,
                            "link": <String, URL or BASE64>
                        }
                    ],
                    "action": <String, optional action>,
                },
            ]
        },
        {
            "id": <UUID derived from merchant public_key>,
            "name": <String, stall name>,
            "description": <String, stall description>,
            "categories": <String, CSV of voluntary categories>,
            "shipping": <String, CSV of shipping ids>,
            "action": <String, optional action>,
            "products": [
                {
                    "id": <String, UUID derived from stall ID>,
                    "name": <String, name of product>,
                    "categories": <String, CSV of voluntary categories>,
                    "amount": <Int, number of units>,
                    "price": <Int, cost per unit>,
                    "images": [
                        {
                            "id": <String, UUID derived from product ID>,
                            "name": <String, image name>,
                            "link": <String, URL or BASE64>
                        }
                    ],
                    "action": <String, optional action>,
                }
            ]
        }
    ]
}

```

As all elements are optional, an `update` `action` to a `product` `image`, may look as simple as:

```
{
    "stalls": [
        {
            "id": <UUID derived from merchant public-key>,
            "products": [
                {
                    "id": <String, UUID derived from stall ID>,
                    "images": [
                        {
                            "id": <String, UUID derived from product ID>,
                            "name": <String, image name>,
                            "link": <String, URL or BASE64>
                        }
                    ],
                    "action": <String, optional action>,
                },
            ]
        }
    ]
}

```


## Checkout events

NIP-04 https://github.com/nostr-protocol/nips/blob/master/04.md, all checkout events are encrypted

The below json goes in `content` of NIP-04.

### Step 1: `customer` order (event)


```
{
    "id": <String, UUID derived from sum of product ids + timestamp>,
    "name": <String, name of customer>,
    "description": <String, description of customer>,
    "address": <String, postal address>,
    "message": <String, special request>,
    "contact": [
        "nostr": <String, NOSTR public key>,
        "phone": <String, phone number>,
        "email": <String, email address>
    ],
    "items": [
        {
            "id": <String, product ID>,
            "quantity": <String, stall name>,
            "message": <String, special request>
        },
        {
            "id": <String, product ID>,
            "quantity": <String, stall name>,
            "message": <String, special request>
        },
        {
            "id": <String, product ID>,
            "quantity": <String, stall name>,
            "message": <String, special request>
        }
    
}

```

Merchant should verify the sum of product ids + timestamp.

### Step 2: `merchant` request payment (event)

Sent back from the merchant for payment. Any payment option is valid that the merchant can check.

The below json goes in `content` of NIP-04.

`payment_options`/`type` include:
* `url` URL to a payment page, stripe, paypal, btcpayserver, etc
* `btc` onchain bitcoin address
* `ln` bitcoin lightning invoice
* `lnurl` bitcoin lnurl-pay  

```
{
    "id": <String, UUID derived from sum of product ids + timestamp>,
    "message": <String, message to customer>,
    "payment_options": [
        {
            "type": <String, option type>,
            "link": <String, url, btc address, ln invoice, etc>
        },
        {
            "type": <String, option type>,
            "link": <String, url, btc address, ln invoice, etc>
        },
                {
            "type": <String, option type>,
            "link": <String, url, btc address, ln invoice, etc>
        }
}

```

### Step 3: `merchant` verify payment/shipped (event)

Once payment has been received and processed.

The below json goes in `content` of NIP-04.

```
{
    "id": <String, UUID derived from sum of product ids + timestamp>,
    "message": <String, message to customer>,
    "paid": <Bool, true/false has received payment>,
    "shipped": <Bool, true/false has been shipped>,
}

```

## Customer support events

Customer support is handle over whatever communication method was specified. If communicationg via nostr, NIP-04 is used https://github.com/nostr-protocol/nips/blob/master/04.md.

## Additional

Standard data models can be found here <a href="models.json">here</a>



