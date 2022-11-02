from .models import Charges


def compact_charge(charge: Charges):
    return {
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
        "completelink": charge.completelink,  # should be secret?
    }
