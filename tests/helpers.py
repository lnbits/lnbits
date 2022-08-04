import hashlib
import random
import secrets
import string

from lnbits.core.crud import create_payment


async def credit_wallet(wallet_id: str, amount: int):
    preimage = secrets.token_hex(32)
    m = hashlib.sha256()
    m.update(f"{preimage}".encode())
    payment_hash = m.hexdigest()
    await create_payment(
        wallet_id=wallet_id,
        payment_request="",
        payment_hash=payment_hash,
        checking_id=payment_hash,
        preimage=preimage,
        memo=f"funding_test_{get_random_string(5)}",
        amount=amount,  # msat
        pending=False,  # not pending, so it will increase the wallet's balance
    )


def get_random_string(N=10):
    return "".join(
        random.SystemRandom().choice(string.ascii_uppercase + string.digits)
        for _ in range(10)
    )


async def get_random_invoice_data():
    return {"out": False, "amount": 10, "memo": f"test_memo_{get_random_string(10)}"}
