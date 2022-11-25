from .models import Charges


def public_charge(charge: Charges):
    c = {
        "id": charge.id,
        "description": charge.description,
        "onchainaddress": charge.onchainaddress,
        "payment_request": charge.payment_request,
        "payment_hash": charge.payment_hash,
        "time": charge.time,
        "amount": charge.amount,
        "balance": charge.balance,
        "paid": charge.paid,
        "timestamp": charge.timestamp,
        "time_elapsed": charge.time_elapsed,
        "time_left": charge.time_left,
        "paid": charge.paid,
    }

    if charge.paid:
        c["completelink"] = charge.completelink

    return c
