import hashlib
from typing import List, Set

from .models import BlindedMessage, BlindedSignature, Invoice, Proof
from secp256k1 import PublicKey, PrivateKey

from fastapi import Query
from .crud import get_cashu
from lnbits.core.services import check_transaction_status, create_invoice

def _derive_keys(master_key: str, cashu_id: str = Query(None)):
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

def _derive_pubkeys(keys: List[PrivateKey], cashu_id: str = Query(None)):
    return {amt: keys[amt].pubkey for amt in [2**i for i in range(MAX_ORDER)]}

async def _generate_promises(amounts: List[int], B_s: List[str], cashu_id: str = Query(None)):
    """Generates promises that sum to the given amount."""
    return [
        await self._generate_promise(amount, PublicKey(bytes.fromhex(B_), raw=True))
        for (amount, B_) in zip(amounts, B_s)
    ]

async def _generate_promise(amount: int, B_: PublicKey, cashu_id: str = Query(None)):
    """Generates a promise for given amount and returns a pair (amount, C')."""
    secret_key = self.keys[amount]  # Get the correct key
    C_ = step2_bob(B_, secret_key)
    await store_promise(
        amount, B_=B_.serialize().hex(), C_=C_.serialize().hex()
    )
    return BlindedSignature(amount=amount, C_=C_.serialize().hex())

def _check_spendable(proof: Proof, cashu_id: str = Query(None)):
    """Checks whether the proof was already spent."""
    return not proof.secret in self.proofs_used

def _verify_proof(proof: Proof, cashu_id: str = Query(None)):
    """Verifies that the proof of promise was issued by this ledger."""
    if not self._check_spendable(proof):
        raise Exception(f"tokens already spent. Secret: {proof.secret}")
    secret_key = self.keys[proof.amount]  # Get the correct key to check against
    C = PublicKey(bytes.fromhex(proof.C), raw=True)
    return verify(secret_key, C, proof.secret)

def _verify_outputs(total: int, amount: int, output_data: List[BlindedMessage], cashu_id: str = Query(None)):
    """Verifies the expected split was correctly computed"""
    fst_amt, snd_amt = total - amount, amount  # we have two amounts to split to
    fst_outputs = amount_split(fst_amt)
    snd_outputs = amount_split(snd_amt)
    expected = fst_outputs + snd_outputs
    given = [o.amount for o in output_data]
    return given == expected

def _verify_no_duplicates(proofs: List[Proof], output_data: List[BlindedMessage], cashu_id: str = Query(None)):
    secrets = [p.secret for p in proofs]
    if len(secrets) != len(list(set(secrets))):
        return False
    B_s = [od.B_ for od in output_data]
    if len(B_s) != len(list(set(B_s))):
        return False
    return True

def _verify_split_amount(amount: int, cashu_id: str = Query(None)):
    """Split amount like output amount can't be negative or too big."""
    try:
        self._verify_amount(amount)
    except:
        # For better error message
        raise Exception("invalid split amount: " + str(amount))

def _verify_amount(amount: int, cashu_id: str = Query(None)):
    """Any amount used should be a positive integer not larger than 2^MAX_ORDER."""
    valid = isinstance(amount, int) and amount > 0 and amount < 2**MAX_ORDER
    if not valid:
        raise Exception("invalid amount: " + str(amount))
    return amount

def _verify_equation_balanced(proofs: List[Proof], outs: List[BlindedMessage], cashu_id: str = Query(None)):
    """Verify that Σoutputs - Σinputs = 0."""
    sum_inputs = sum(self._verify_amount(p.amount) for p in proofs)
    sum_outputs = sum(self._verify_amount(p.amount) for p in outs)
    assert sum_outputs - sum_inputs == 0

def _get_output_split(amount: int, cashu_id: str):
    """Given an amount returns a list of amounts returned e.g. 13 is [1, 4, 8]."""
    self._verify_amount(amount)
    bits_amt = bin(amount)[::-1][:-2]
    rv = []
    for (pos, bit) in enumerate(bits_amt):
        if bit == "1":
            rv.append(2**pos)
    return rv

async def _invalidate_proofs(proofs: List[Proof], cashu_id: str = Query(None)):
    """Adds secrets of proofs to the list of knwon secrets and stores them in the db."""
    # Mark proofs as used and prepare new promises
    proof_msgs = set([p.secret for p in proofs])
    self.proofs_used |= proof_msgs
    # store in db
    for p in proofs:
        await invalidate_proof(p)

def get_pubkeys(cashu_id: str = Query(None)):
    """Returns public keys for possible amounts."""
    return {a: p.serialize().hex() for a, p in self.pub_keys.items()}

async def request_mint(amount, cashu_id: str = Query(None)):
    cashu = await get_cashu(cashu_id)
    if not cashu:
        raise Exception(f"Could not find Cashu")

    """Returns Lightning invoice and stores it in the db."""
    payment_hash, payment_request = await create_invoice(
        wallet_id=cashu.wallet,
        amount=amount,
        memo=cashu.name,
        unhashed_description=cashu.name.encode("utf-8"),
        extra={
            "tag": "Cashu"
        },
    )

    invoice = Invoice(
        amount=amount, pr=payment_request, hash=payment_hash, issued=False
    )
    if not payment_request or not payment_hash:
        raise Exception(f"Could not create Lightning invoice.")
    return payment_request, payment_hash

async def mint(B_s: List[PublicKey], amounts: List[int], payment_hash: str = Query(None), cashu_id: str = Query(None)):
    cashu = await get_cashu(cashu_id)
    if not cashu:
        raise Exception(f"Could not find Cashu")

    """Mints a promise for coins for B_."""
    # check if lightning invoice was paid
    if payment_hash: 
        if not await check_transaction_status(wallet_id=cashu.wallet, payment_hash=payment_hash):
            raise Exception("Lightning invoice not paid yet.")

    for amount in amounts:
        if amount not in [2**i for i in range(MAX_ORDER)]:
            raise Exception(f"Can only mint amounts up to {2**MAX_ORDER}.")

    promises = [
        await self._generate_promise(amount, B_) for B_, amount in zip(B_s, amounts)
    ]
    return promises

async def melt(proofs: List[Proof], amount: int, invoice: str, cashu_id: str = Query(None)):
    cashu = await get_cashu(cashu_id)
    if not cashu:
        raise Exception(f"Could not find Cashu")    
    
    """Invalidates proofs and pays a Lightning invoice."""
    # if not LIGHTNING:
    total = sum([p["amount"] for p in proofs])
    # check that lightning fees are included
    assert total + fee_reserve(amount * 1000) >= amount, Exception(
        "provided proofs not enough for Lightning payment."
    )

    status, payment_hash = await pay_invoice(
        wallet_id=link.wallet,
        payment_request=invoice,
        max_sat=amount,
        extra={"tag": "Ecash melt"},
    )

    if status == True:
        await self._invalidate_proofs(proofs)
    return status, payment_hash

async def check_spendable(proofs: List[Proof], cashu_id: str = Query(None)):
    cashu = await get_cashu(cashu_id)
    if not cashu:
        raise Exception(f"Could not find Cashu")

    """Checks if all provided proofs are valid and still spendable (i.e. have not been spent)."""
    return {i: self._check_spendable(p) for i, p in enumerate(proofs)}

async def split(proofs: List[Proof], amount: int, output_data: List[BlindedMessage], cashu_id: str = Query(None)):
    cashu = await get_cashu(cashu_id)
    if not cashu:
        raise Exception(f"Could not find Cashu")

    """Consumes proofs and prepares new promises based on the amount split."""
    self._verify_split_amount(amount)
    # Verify proofs are valid
    if not all([self._verify_proof(p) for p in proofs]):
        return False

    total = sum([p.amount for p in proofs])

    if not self._verify_no_duplicates(proofs, output_data):
        raise Exception("duplicate proofs or promises")
    if amount > total:
        raise Exception("split amount is higher than the total sum")
    if not self._verify_outputs(total, amount, output_data):
        raise Exception("split of promises is not as expected")

    # Mark proofs as used and prepare new promises
    await self._invalidate_proofs(proofs)

    outs_fst = amount_split(total - amount)
    outs_snd = amount_split(amount)
    B_fst = [od.B_ for od in output_data[: len(outs_fst)]]
    B_snd = [od.B_ for od in output_data[len(outs_fst) :]]
    prom_fst, prom_snd = await self._generate_promises(
        outs_fst, B_fst
    ), await self._generate_promises(outs_snd, B_snd)
    self._verify_equation_balanced(proofs, prom_fst + prom_snd)
    return prom_fst, prom_snd


async def fee_reserve(amount_msat: int, cashu_id: str = Query(None)):
    cashu = await get_cashu(cashu_id)
    if not cashu:
        raise Exception(f"Could not find Cashu")    
    
    """Function for calculating the Lightning fee reserve"""
    return max(
        int(LIGHTNING_RESERVE_FEE_MIN), int(amount_msat * LIGHTNING_FEE_PERCENT / 100.0)
    )

async def amount_split(amount, cashu_id: str):
    cashu = await get_cashu(cashu_id)
    if not cashu:
        raise Exception(f"Could not find Cashu")    
    
    """Given an amount returns a list of amounts returned e.g. 13 is [1, 4, 8]."""
    bits_amt = bin(amount)[::-1][:-2]
    rv = []
    for (pos, bit) in enumerate(bits_amt):
        if bit == "1":
            rv.append(2**pos)
    return rv

async def hash_to_point(secret_msg, cashu_id: str = Query(None)):
    cashu = await get_cashu(cashu_id)
    if not cashu:
        raise Exception(f"Could not find Cashu")    
    
    """Generates x coordinate from the message hash and checks if the point lies on the curve.
    If it does not, it tries computing again a new x coordinate from the hash of the coordinate."""
    point = None
    msg = secret_msg
    while point is None:
        _hash = hashlib.sha256(msg).hexdigest().encode("utf-8")
        try:
            # We construct compressed pub which has x coordinate encoded with even y
            _hash = list(_hash[:33])  # take the 33 bytes and get a list of bytes
            _hash[0] = 0x02  # set first byte to represent even y coord
            _hash = bytes(_hash)
            point = PublicKey(_hash, raw=True)
        except:
            msg = _hash

    return point


async def step1_alice(secret_msg, cashu_id: str = Query(None)):
    cashu = await get_cashu(cashu_id)
    if not cashu:
        raise Exception(f"Could not find Cashu")

    secret_msg = secret_msg.encode("utf-8")
    Y = hash_to_point(secret_msg)
    r = PrivateKey()
    B_ = Y + r.pubkey
    return B_, r

async def step2_bob(B_, a, cashu_id: str = Query(None)):
    cashu = await get_cashu(cashu_id)
    if not cashu:
        raise Exception(f"Could not find Cashu")   

    C_ = B_.mult(a)
    return C_


async def step3_alice(C_, r, A, cashu_id: str = Query(None)):
    cashu = await get_cashu(cashu_id)
    if not cashu:
        raise Exception(f"Could not find Cashu")

    C = C_ - A.mult(r)
    return C


async def verify(a, C, secret_msg, cashu_id: str = Query(None)):
    cashu = await get_cashu(cashu_id)
    if not cashu:
        raise Exception(f"Could not find Cashu")

    Y = hash_to_point(secret_msg.encode("utf-8"))
    return C == Y.mult(a)
