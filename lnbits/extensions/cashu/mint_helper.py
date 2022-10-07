import hashlib
from typing import List

from .core.secp import PrivateKey

# todo: extract const
MAX_ORDER = 64


def derive_keys(master_key: str):
    """Deterministic derivation of keys for 2^n values."""
    return {2**i: derive_key(master_key, i) for i in range(MAX_ORDER)}


def derive_key(master_key: str, i: int):
    """Deterministic derivation of keys for a particular value."""
    return PrivateKey(
        hashlib.sha256((str(master_key) + str(i)).encode("utf-8"))
        .hexdigest()
        .encode("utf-8")[:32],
        raw=True,
    )


def derive_pubkeys(keys: List[PrivateKey]):
    return {amt: keys[amt].pubkey for amt in [2**i for i in range(MAX_ORDER)]}
