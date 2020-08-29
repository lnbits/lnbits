from typing import Optional, Tuple

from lnbits.bolt11 import decode as bolt11_decode  # type: ignore
from lnbits.helpers import urlsafe_short_hash
from lnbits.settings import WALLET

from .crud import get_wallet, create_payment, delete_payment


def create_invoice(*, wallet_id: str, amount: int, memo: str, description_hash: bytes) -> Tuple[str, str]:

    try:
        ok, checking_id, payment_request, error_message = WALLET.create_invoice(
            amount=amount, memo=memo, description_hash=description_hash
        )
    except Exception as e:
        ok, error_message = False, str(e)

    if not ok:
        raise Exception(error_message or "Unexpected backend error.")

    amount_msat = amount * 1000
    create_payment(wallet_id=wallet_id, checking_id=checking_id, amount=amount_msat, memo=memo)

    return checking_id, payment_request


def pay_invoice(*, wallet_id: str, bolt11: str, max_sat: Optional[int] = None) -> str:
    temp_id = f"temp_{urlsafe_short_hash()}"
    try:
        invoice = bolt11_decode(bolt11)

        if invoice.amount_msat == 0:
            raise ValueError("Amountless invoices not supported.")

        if max_sat and invoice.amount_msat > max_sat * 1000:
            raise ValueError("Amount in invoice is too high.")

        fee_reserve = max(1000, int(invoice.amount_msat * 0.01))
        create_payment(
            wallet_id=wallet_id, checking_id=temp_id, amount=-invoice.amount_msat, fee=-fee_reserve, memo=temp_id,
        )

        wallet = get_wallet(wallet_id)
        assert wallet, "invalid wallet id"
        if wallet.balance_msat < 0:
            raise PermissionError("Insufficient balance.")

        ok, checking_id, fee_msat, error_message = WALLET.pay_invoice(bolt11)

        if ok:
            create_payment(
                wallet_id=wallet_id,
                checking_id=checking_id,
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
