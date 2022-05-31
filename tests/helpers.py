import hashlib
import secrets
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
        memo="",
        amount=amount,# msat
        pending=False,# not pending, so it will increase the wallet's balance
    )
