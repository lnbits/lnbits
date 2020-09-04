from typing import Optional, Tuple, Dict

try:
    from typing import TypedDict  # type: ignore
except ImportError:  # pragma: nocover
    from typing_extensions import TypedDict

from lnbits import bolt11
from lnbits.helpers import urlsafe_short_hash
from lnbits.settings import WALLET
from lnbits.wallets.base import PaymentStatus

from .crud import get_wallet, create_payment, delete_payment, check_internal, update_payment_status, get_wallet_payment


def create_invoice(
    *,
    wallet_id: str,
    amount: int,
    memo: str,
    description_hash: Optional[bytes] = None,
    extra: Optional[Dict] = None,
) -> Tuple[str, str]:
    invoice_memo = None if description_hash else memo
    storeable_memo = memo

    ok, checking_id, payment_request, error_message = WALLET.create_invoice(
        amount=amount, memo=invoice_memo, description_hash=description_hash
    )
    if not ok:
        raise Exception(error_message or "Unexpected backend error.")

    invoice = bolt11.decode(payment_request)

    amount_msat = amount * 1000
    create_payment(
        wallet_id=wallet_id,
        checking_id=checking_id,
        payment_request=payment_request,
        payment_hash=invoice.payment_hash,
        amount=amount_msat,
        memo=storeable_memo,
        extra=extra,
    )

    return invoice.payment_hash, payment_request


def pay_invoice(
    *, wallet_id: str, payment_request: str, max_sat: Optional[int] = None, extra: Optional[Dict] = None
) -> str:
    temp_id = f"temp_{urlsafe_short_hash()}"
    internal_id = f"internal_{urlsafe_short_hash()}"

    invoice = bolt11.decode(payment_request)
    if invoice.amount_msat == 0:
        raise ValueError("Amountless invoices not supported.")
    if max_sat and invoice.amount_msat > max_sat * 1000:
        raise ValueError("Amount in invoice is too high.")

    # put all parameters that don't change here
    PaymentKwargs = TypedDict(
        "PaymentKwargs",
        {
            "wallet_id": str,
            "payment_request": str,
            "payment_hash": str,
            "amount": int,
            "memo": str,
            "extra": Optional[Dict],
        },
    )
    payment_kwargs: PaymentKwargs = dict(
        wallet_id=wallet_id,
        payment_request=payment_request,
        payment_hash=invoice.payment_hash,
        amount=-invoice.amount_msat,
        memo=invoice.description or "",
        extra=extra,
    )

    # check_internal() returns the checking_id of the invoice we're waiting for
    internal = check_internal(invoice.payment_hash)
    if internal:
        # create a new payment from this wallet
        create_payment(checking_id=internal_id, fee=0, pending=False, **payment_kwargs)
    else:
        # create a temporary payment here so we can check if
        # the balance is enough in the next step
        fee_reserve = max(1000, int(invoice.amount_msat * 0.01))
        create_payment(checking_id=temp_id, fee=-fee_reserve, **payment_kwargs)

    # do the balance check
    wallet = get_wallet(wallet_id)
    assert wallet, "invalid wallet id"
    if wallet.balance_msat < 0:
        raise PermissionError("Insufficient balance.")

    if internal:
        # mark the invoice from the other side as not pending anymore
        # so the other side only has access to his new money when we are sure
        # the payer has enough to deduct from
        update_payment_status(checking_id=internal, pending=False)
    else:
        # actually pay the external invoice
        ok, checking_id, fee_msat, error_message = WALLET.pay_invoice(payment_request)
        if ok:
            create_payment(checking_id=checking_id, fee=fee_msat, **payment_kwargs)
            delete_payment(temp_id)

    if not ok:
        raise Exception(error_message or "Unexpected backend error.")

    return invoice.payment_hash


def check_invoice_status(wallet_id: str, payment_hash: str) -> PaymentStatus:
    payment = get_wallet_payment(wallet_id, payment_hash)
    if not payment:
        return PaymentStatus(None)

    return WALLET.get_invoice_status(payment.checking_id)
