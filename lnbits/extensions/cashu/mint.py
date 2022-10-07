import math
from typing import List, Set

from lnbits import bolt11
from lnbits.core.services import check_transaction_status, fee_reserve, pay_invoice
from lnbits.extensions.cashu.models import Cashu
from lnbits.wallets.base import PaymentStatus

from .core.b_dhke import step2_bob
from .core.base import BlindedSignature, Proof
from .core.secp import PublicKey
from .crud import get_proofs_used, invalidate_proof
from .mint_helper import derive_keys, derive_pubkeys, verify_proof

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
    secret_key = derive_keys(master_prvkey)[amount]  # Get the correct key
    C_ = step2_bob(B_, secret_key)
    return BlindedSignature(amount=amount, C_=C_.serialize().hex())


async def melt(cashu: Cashu, proofs: List[Proof], invoice: str):
    """Invalidates proofs and pays a Lightning invoice."""
    # Verify proofs
    proofs_used: Set[str] = set(await get_proofs_used(cashu.id))
    # if not all([verify_proof(cashu.prvkey, proofs_used, p) for p in proofs]):
    #     raise Exception("could not verify proofs.")
    for p in proofs:
        await verify_proof(cashu.prvkey, proofs_used, p)    

    total_provided = sum([p["amount"] for p in proofs])
    invoice_obj = bolt11.decode(invoice)
    amount = math.ceil(invoice_obj.amount_msat / 1000)

    fees_msat = await check_fees(cashu.wallet, invoice_obj)
    assert total_provided >= amount + fees_msat / 1000, Exception(
        "provided proofs not enough for Lightning payment."
    )

    await pay_invoice(
        wallet_id=cashu.wallet,
        payment_request=invoice,
        description=f"pay cashu invoice",
        extra={"tag": "cashu", "cahsu_name": cashu.name},
    )

    status: PaymentStatus = await check_transaction_status(
        cashu.wallet, invoice_obj.payment_hash
    )
    if status.paid == True:
        await invalidate_proofs(cashu.id, proofs)
        return status.paid, status.preimage
    return False, ""


async def check_fees(wallet_id: str, decoded_invoice):
    """Returns the fees (in msat) required to pay this pr."""
    amount = math.ceil(decoded_invoice.amount_msat / 1000)
    status: PaymentStatus = await check_transaction_status(
        wallet_id, decoded_invoice.payment_hash
    )
    fees_msat = fee_reserve(amount * 1000) if status.paid != True else 0
    return fees_msat

async def invalidate_proofs(cashu_id: str, proofs: List[Proof]):
    """Adds secrets of proofs to the list of knwon secrets and stores them in the db."""
    for p in proofs:
        await invalidate_proof(cashu_id, p)