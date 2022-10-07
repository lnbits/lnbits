import hashlib
from typing import List, Set

from .core.b_dhke import verify
from .core.secp import PrivateKey, PublicKey
from .models import Proof

# todo: extract const
MAX_ORDER = 64


def derive_keys(master_key: str):
    """Deterministic derivation of keys for 2^n values."""
    return {
        2
        ** i: PrivateKey(
            hashlib.sha256((str(master_key) + str(i)).encode("utf-8"))
            .hexdigest()
            .encode("utf-8")[:32],
            raw=True,
        )
        for i in range(MAX_ORDER)
    }


def derive_pubkeys(keys: List[PrivateKey]):
    return {amt: keys[amt].pubkey for amt in [2**i for i in range(MAX_ORDER)]}


async def verify_proof(master_prvkey: str, proofs_used: Set[str], proof: Proof):
    """Verifies that the proof of promise was issued by this ledger."""
    if proof.secret in proofs_used:
        raise Exception(f"tokens already spent. Secret: {proof.secret}")

    secret_key = derive_keys(master_prvkey)[
        proof.amount
    ]  # Get the correct key to check against
    C = PublicKey(bytes.fromhex(proof.C), raw=True)
    validMintSig = verify(secret_key, C, proof.secret)
    if validMintSig != True:
         raise Exception(f"tokens not valid. Secret: {proof.secret}")
