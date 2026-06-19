---
layout: default
parent: For developers
title: Webhooks
nav_order: 4
---

# Webhooks

When you create an invoice you can pass a `webhook` URL. As soon as the invoice
is paid, LNbits sends a `POST` request with the `application/json` body of the
payment to that URL.

## Verifying the signature

To let a receiver verify that a webhook really originated from your LNbits
instance, LNbits signs the request body with the wallet's `webhook_secret`
(found under _Node URL, API keys and API docs_ in the wallet view). The
signature is sent in the `LNbits-Signature` header, using the same scheme as
Stripe:

```
LNbits-Signature: t=<unix_timestamp>,v1=<hmac_sha256_hex>
```

The signed payload is `"{timestamp}.{raw_body}"`, hashed with HMAC-SHA256 using
the `webhook_secret` as the key. Verify it on the receiving side by recomputing
the HMAC over the **raw** request body (do not re-serialize the JSON) and
comparing in constant time. The timestamp lets you reject replayed requests
outside a tolerance window.

Signing is enabled by default (`LNBITS_WEBHOOK_SIGNING_ENABLED`). New wallets
get a secret on creation. Wallets created before this feature have no secret
until you reset it in the wallet view ("Reset Webhook Secret"); their webhooks
are sent unsigned until then.

Example verification (Python):

```python
import hashlib
import hmac
import time


def verify_lnbits_webhook(
    raw_body: bytes,
    signature_header: str,
    secret: str,
    tolerance_seconds: int = 300,
) -> bool:
    items = dict(i.split("=", 1) for i in signature_header.split(","))
    timestamp = int(items["t"])
    if abs(time.time() - timestamp) > tolerance_seconds:
        return False
    signed_payload = f"{timestamp}.{raw_body.decode()}"
    expected = hmac.new(
        key=secret.encode(),
        msg=signed_payload.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, items["v1"])
```
