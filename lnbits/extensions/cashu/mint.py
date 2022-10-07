
from .models import Cashu
from .mint_helper import derive_keys, derive_pubkeys


def get_pubkeys(xpriv: str):
    """Returns public keys for possible amounts."""
    
    keys = derive_keys(xpriv)
    pub_keys = derive_pubkeys(keys)

    return {a: p.serialize().hex() for a, p in pub_keys.items()}

# async def mint(self, B_s: List[PublicKey], amounts: List[int], payment_hash=None):
#     """Mints a promise for coins for B_."""
#     # check if lightning invoice was paid
#     if LIGHTNING:
#         try:
#             paid = await self._check_lightning_invoice(payment_hash)
#         except:
#             raise Exception("could not check invoice.")
#         if not paid:
#             raise Exception("Lightning invoice not paid yet.")

#     for amount in amounts:
#         if amount not in [2**i for i in range(MAX_ORDER)]:
#             raise Exception(f"Can only mint amounts up to {2**MAX_ORDER}.")

#     promises = [
#         await self._generate_promise(amount, B_) for B_, amount in zip(B_s, amounts)
#     ]
#     return promises