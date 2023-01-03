from lnbits.bolt11 import Invoice


def to_buffer(payment_hash: str):
    return {"type": "Buffer", "data": [b for b in bytes.fromhex(payment_hash)]}


def decoded_as_lndhub(invoice: Invoice):
    return {
        "destination": invoice.payee,
        "payment_hash": invoice.payment_hash,
        "num_satoshis": invoice.amount_msat / 1000,
        "timestamp": str(invoice.date),
        "expiry": str(invoice.expiry),
        "description": invoice.description,
        "fallback_addr": "",
        "cltv_expiry": invoice.min_final_cltv_expiry,
        "route_hints": "",
    }
