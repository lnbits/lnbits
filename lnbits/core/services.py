from typing import Optional, Tuple

from lnbits.bolt11 import decode as bolt11_decode # type: ignore
from lnbits.helpers import urlsafe_short_hash
from lnbits.settings import WALLET

from .crud import get_wallet, create_payment, delete_payment, check_internal, update_payment_status


def create_invoice(*, wallet_id: str, amount: int, memo: str) -> Tuple[str, str]:
    try:
        ok, checking_id, payment_request, error_message = WALLET.create_invoice(amount=amount, memo=memo)
    except Exception as e:
        ok, error_message = False, str(e)

    if not ok:
        raise Exception(error_message or "Unexpected backend error.")
    invoice = bolt11_decode(payment_request)

    amount_msat = amount * 1000
    create_payment(wallet_id=wallet_id, checking_id=checking_id, payment_hash=invoice.payment_hash, amount=amount_msat, memo=memo)

    return checking_id, payment_request


def pay_invoice(*, wallet_id: str, bolt11: str, max_sat: Optional[int] = None) -> str:
    temp_id = f"temp_{urlsafe_short_hash()}"
    try:
        invoice = bolt11_decode(bolt11)
        print(invoice.payment_hash)
        internal = check_internal(invoice.payment_hash)

        if invoice.amount_msat == 0:
            raise ValueError("Amountless invoices not supported.")

        if max_sat and invoice.amount_msat > max_sat * 1000:
            raise ValueError("Amount in invoice is too high.")
        
        fee_reserve = max(1000, int(invoice.amount_msat * 0.01))
        
        if not internal:
            create_payment(
                wallet_id=wallet_id,
                checking_id=temp_id,
                payment_hash=invoice.payment_hash,
                amount=-invoice.amount_msat,
                fee=-fee_reserve,
                memo=temp_id,
            )
        wallet = get_wallet(wallet_id)
        assert wallet, "invalid wallet id"
        if wallet.balance_msat < 0:
            raise PermissionError("Insufficient balance.")
        print(internal)
        if internal:
            create_payment(
                wallet_id=wallet_id,
                checking_id=temp_id,
                payment_hash=invoice.payment_hash,
                amount=-invoice.amount_msat,
                fee=0,
                pending=False,
                memo=invoice.description,
            )
            update_payment_status(checking_id=internal, pending=False)
            return temp_id

        ok, checking_id, fee_msat, error_message = WALLET.pay_invoice(bolt11)
        if ok:
            create_payment(
                wallet_id=wallet_id,
                checking_id=checking_id,
                payment_hash=invoice.payment_hash,
                amount=-invoice.amount_msat,
                fee=fee_msat,
                memo=invoice.description,
            )

    except Exception as e:
        ok, error_message = False, str(e)

    delete_payment(temp_id)

    if not ok:
        raise Exception(error_message or "Unexpected backend error.")

    return checking_id


def check_payment(*, checking_id: str) -> str:
    pass
