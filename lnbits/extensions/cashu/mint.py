import math
from typing import List, Set

from lnbits import bolt11
from lnbits.core.services import check_transaction_status, fee_reserve, pay_invoice
from lnbits.wallets.base import PaymentStatus

from .core.b_dhke import step2_bob
from .core.base import BlindedMessage, BlindedSignature, Proof
from .core.secp import PublicKey
from .core.split import amount_split
from .crud import get_proofs_used, invalidate_proof
from .mint_helper import (
    derive_keys,
    derive_pubkeys,
    verify_equation_balanced,
    verify_no_duplicates,
    verify_outputs,
    verify_proof,
    verify_secret_criteria,
    verify_split_amount,
)
from .models import Cashu

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
    for p in proofs:
        await verify_proof(cashu.prvkey, proofs_used, p)

    total_provided = sum([p["amount"] for p in proofs])
    invoice_obj = bolt11.decode(invoice)
    amount = math.ceil(invoice_obj.amount_msat / 1000)

    fees_msat = await check_fees(cashu.wallet, invoice_obj)
    assert total_provided >= amount + fees_msat / 1000, Exception(
        f"Provided proofs (${total_provided} sats) not enough for Lightning payment ({amount + fees_msat} sats)."
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


async def split(
    cashu: Cashu, proofs: List[Proof], amount: int, outputs: List[BlindedMessage]
):
    """Consumes proofs and prepares new promises based on the amount split."""
    total = sum([p.amount for p in proofs])

    # verify that amount is kosher
    verify_split_amount(amount)
    # verify overspending attempt
    if amount > total:
        raise Exception(
            f"split amount ({amount}) is higher than the total sum ({total})."
        )

    # Verify secret criteria
    if not all([verify_secret_criteria(p) for p in proofs]):
        raise Exception("secrets do not match criteria.")
    # verify that only unique proofs and outputs were used
    if not verify_no_duplicates(proofs, outputs):
        raise Exception("duplicate proofs or promises.")
    # verify that outputs have the correct amount
    if not verify_outputs(total, amount, outputs):  # ?
        raise Exception("split of promises is not as expected.")
    # Verify proofs
    # Verify proofs
    proofs_used: Set[str] = set(await get_proofs_used(cashu.id))
    for p in proofs:
        await verify_proof(cashu.prvkey, proofs_used, p)

    # Mark proofs as used and prepare new promises
    await invalidate_proofs(cashu.id, proofs)

    outs_fst = amount_split(total - amount)
    outs_snd = amount_split(amount)
    B_fst = [
        PublicKey(bytes.fromhex(od.B_), raw=True) for od in outputs[: len(outs_fst)]
    ]
    B_snd = [
        PublicKey(bytes.fromhex(od.B_), raw=True) for od in outputs[len(outs_fst) :]
    ]
    # PublicKey(bytes.fromhex(payload.B_), raw=True)
    prom_fst, prom_snd = await generate_promises(
        cashu.prvkey, outs_fst, B_fst
    ), await generate_promises(cashu.prvkey, outs_snd, B_snd)
    # verify amounts in produced proofs
    verify_equation_balanced(proofs, prom_fst + prom_snd)
    return prom_fst, prom_snd


async def invalidate_proofs(cashu_id: str, proofs: List[Proof]):
    """Adds secrets of proofs to the list of knwon secrets and stores them in the db."""
    for p in proofs:
        await invalidate_proof(cashu_id, p)
