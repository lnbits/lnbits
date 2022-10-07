
from .models import Cashu
from .mint_helper import derive_keys, derive_pubkeys


def get_pubkeys(xpriv: str):
    """Returns public keys for possible amounts."""
    
    keys = derive_keys(xpriv)
    pub_keys = derive_pubkeys(keys)

    return {a: p.serialize().hex() for a, p in pub_keys.items()}

async def request_mint(mint: Cashu, amount):
    """Returns Lightning invoice and stores it in the db."""
    payment_request, checking_id = await self._request_lightning_invoice(amount)
    invoice = Invoice(
        amount=amount, pr=payment_request, hash=checking_id, issued=False
    )
    if not payment_request or not checking_id:
        raise Exception(f"Could not create Lightning invoice.")
    await store_lightning_invoice(invoice, db=self.db)
    return payment_request, checking_id