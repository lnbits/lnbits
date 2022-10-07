from typing import List

from .core.b_dhke import step2_bob
from .core.base import BlindedSignature
from .core.secp import PublicKey
from .mint_helper import derive_key, derive_keys, derive_pubkeys

# todo: extract const
MAX_ORDER = 64


def get_pubkeys(xpriv: str):
    """Returns public keys for possible amounts."""

    keys = derive_keys(xpriv)
    pub_keys = derive_pubkeys(keys)

    return {a: p.serialize().hex() for a, p in pub_keys.items()}


async def generate_promises(
    master_prvkey: str, amounts: List[int], B_s: List[PublicKey]
):
    """Mints a promise for coins for B_."""

    for amount in amounts:
        if amount not in [2**i for i in range(MAX_ORDER)]:
            raise Exception(f"Can only mint amounts up to {2**MAX_ORDER}.")

    promises = [
        await generate_promise(master_prvkey, amount, B_)
        for B_, amount in zip(B_s, amounts)
    ]
    return promises


async def generate_promise(master_prvkey: str, amount: int, B_: PublicKey):
    """Generates a promise for given amount and returns a pair (amount, C')."""
    secret_key = derive_key(master_prvkey, amount)  # Get the correct key
    C_ = step2_bob(B_, secret_key)
    return BlindedSignature(amount=amount, C_=C_.serialize().hex())
