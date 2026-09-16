---
layout: default
parent: For developers
title: API reference
nav_order: 3
---

# API reference

[Swagger Docs](https://demo.lnbits.com/docs)

## Paying an invoice or offer

Send a `POST /api/v1/payments` request with the wallet's admin key in the
`X-Api-Key` header and a JSON body:

```json
{"out": true, "payment_request": "<BOLT11 invoice>"}
```

For a BOLT12 offer, also provide the amount in satoshis:

```json
{"out": true, "payment_request": "<BOLT12 offer>", "amount": 21, "unit": "sat"}
```

The legacy `bolt11` input is still accepted. If both `payment_request` and `bolt11`
have non-empty values, they must match; conflicting values cause a validation error.
