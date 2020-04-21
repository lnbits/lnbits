from typing import Optional, Tuple

from lnbits.bolt11 import decode as bolt11_decode
from lnbits.settings import WALLET

from .crud import create_payment
from .models import Wallet


def create_invoice(*, wallet_id: str, amount: int, memo: str) -> Tuple[str, str]:
    try:
        ok, checking_id, payment_request, error_message = WALLET.create_invoice(amount=amount, memo=memo)
    except Exception as e:
        ok, error_message = False, str(e)

    if not ok:
        raise Exception(error_message or "Unexpected backend error.")

    amount_msat = amount * 1000
    create_payment(wallet_id=wallet_id, checking_id=checking_id, amount=amount_msat, memo=memo)

    return checking_id, payment_request


def pay_invoice(*, wallet: Wallet, bolt11: str, max_sat: Optional[int] = None) -> str:
    try:
        invoice = bolt11_decode(bolt11)
        ok, checking_id, fee_msat, error_message = WALLET.pay_invoice(bolt11)

        if invoice.amount_msat == 0:
            raise ValueError("Amountless invoices not supported.")

        if max_sat and invoice.amount_msat > max_sat * 1000:
            raise ValueError("Amount in invoice is too high.")

        if invoice.amount_msat > wallet.balance_msat:
            raise PermissionError("Insufficient balance.")

        if ok:
            create_payment(
                wallet_id=wallet.id, checking_id=checking_id, amount=-invoice.amount_msat, memo=invoice.description
            )

    except Exception as e:
        ok, error_message = False, str(e)

    if not ok:
        raise Exception(error_message or "Unexpected backend error.")

    return checking_id


def check_payment(*, checking_id: str) -> str:
    pass
