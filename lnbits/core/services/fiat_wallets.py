from decimal import Decimal
from hashlib import sha256

from sqlalchemy.exc import IntegrityError

from lnbits.core.crud.payments import create_payment, get_standalone_payment
from lnbits.core.models import CreatePayment, Payment, PaymentState, Wallet
from lnbits.core.models.payments import CreateCashPayment
from lnbits.core.services.fiat_providers import handle_fiat_payment_confirmation
from lnbits.utils.exchange_rates import fiat_amount_as_satoshis


async def validate_cash_payment(wallet: Wallet, data: CreateCashPayment) -> Payment:
    if not wallet.is_fiat_wallet:
        raise ValueError("Cash payments require a fiat wallet.")
    if data.unit != wallet.currency:
        raise ValueError("Cash payment currency must match the wallet currency.")

    checking_id = f"internal_cash_{wallet.id}_{data.request_id.hex}"
    payment = await get_standalone_payment(checking_id, wallet_id=wallet.id)
    if not payment:
        amount_sat = await fiat_amount_as_satoshis(float(data.amount), data.unit)
        if amount_sat <= 0:
            raise ValueError("Cash payment amount is too small.")
        try:
            payment = await create_payment(
                checking_id=checking_id,
                data=CreatePayment(
                    wallet_id=wallet.id,
                    payment_hash=sha256(checking_id.encode()).hexdigest(),
                    bolt11="",
                    amount_msat=amount_sat * 1000,
                    memo=data.memo,
                    extra={
                        "fiat_method": "cash",
                        "wallet_fiat_currency": data.unit,
                        "wallet_fiat_amount": str(data.amount),
                    },
                ),
            )
        except (IntegrityError, ValueError):
            payment = await get_standalone_payment(checking_id, wallet_id=wallet.id)
            if not payment:
                raise

    if (
        payment.status == PaymentState.DELETED
        or payment.extra.get("wallet_fiat_currency") != data.unit
        or Decimal(str(payment.extra.get("wallet_fiat_amount"))) != data.amount
        or payment.memo != data.memo
    ):
        raise ValueError("This cash request ID has already been used.")
    await handle_fiat_payment_confirmation(payment)
    return payment
