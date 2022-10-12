import base64
import hashlib
from typing import List, Set

from .core.b_dhke import verify
from .core.base import BlindedSignature
from .core.secp import PrivateKey, PublicKey
from .core.split import amount_split
from .models import BlindedMessage, Proof

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


# async required?
async def verify_proof(master_prvkey: str, proofs_used: Set[str], proof: Proof):
    """Verifies that the proof of promise was issued by this ledger."""
    if proof.secret in proofs_used:
        raise Exception(f"tokens already spent. Secret: {proof.secret}")

    secret_key = derive_keys(master_prvkey)[
        proof.amount
    ]  # Get the correct key to check against
    C = PublicKey(bytes.fromhex(proof.C), raw=True)
    secret = base64.standard_b64decode(proof.secret)
    print("### secret", secret)
    validMintSig = verify(secret_key, C, secret)
    if validMintSig != True:
        raise Exception(f"tokens not valid. Secret: {proof.secret}")


def verify_split_amount(amount: int):
    """Split amount like output amount can't be negative or too big."""
    try:
        verify_amount(amount)
    except:
        # For better error message
        raise Exception("invalid split amount: " + str(amount))


def verify_secret_criteria(proof: Proof):
    if proof.secret is None or proof.secret == "":
        raise Exception("no secret in proof.")
    return True


def verify_no_duplicates(proofs: List[Proof], outputs: List[BlindedMessage]):
    secrets = [p.secret for p in proofs]
    if len(secrets) != len(list(set(secrets))):
        return False
    B_s = [od.B_ for od in outputs]
    if len(B_s) != len(list(set(B_s))):
        return False
    return True


def verify_outputs(total: int, amount: int, outputs: List[BlindedMessage]):
    """Verifies the expected split was correctly computed"""
    frst_amt, scnd_amt = total - amount, amount  # we have two amounts to split to
    frst_outputs = amount_split(frst_amt)
    scnd_outputs = amount_split(scnd_amt)
    expected = frst_outputs + scnd_outputs
    given = [o.amount for o in outputs]
    return given == expected


def verify_amount(amount: int):
    """Any amount used should be a positive integer not larger than 2^MAX_ORDER."""
    valid = isinstance(amount, int) and amount > 0 and amount < 2**MAX_ORDER
    if not valid:
        raise Exception("invalid amount: " + str(amount))
    return amount


def verify_equation_balanced(proofs: List[Proof], outs: List[BlindedSignature]):
    """Verify that Σoutputs - Σinputs = 0."""
    sum_inputs = sum(verify_amount(p.amount) for p in proofs)
    sum_outputs = sum(verify_amount(p.amount) for p in outs)
    assert sum_outputs - sum_inputs == 0
