from mock import AsyncMock
from lnbits import bolt11
from lnbits.wallets.base import (
    StatusResponse,
    InvoiceResponse,
    PaymentResponse,
    PaymentStatus,
    Wallet,
)
from lnbits.settings import WALLET

WALLET.status = AsyncMock(return_value=StatusResponse(
    "",# no error
    1000000,# msats
))
WALLET.create_invoice = AsyncMock(return_value=InvoiceResponse(
    True,# ok
    "6621aafbdd7709ca6eea6203f362d64bd7cb2911baa91311a176b3ecaf2274bd",# checking_id (i.e. payment_hash)
    "lntb1u1psezhgspp5vcs6477awuyu5mh2vgplxckkf0tuk2g3h253xydpw6e7etezwj7sdqqcqzpgxqyz5vqsp5dxpw8zs77hw5pla4wz4mfujllyxtlpu443auur2uxqdrs8q2h56q9qyyssq65zk30ylmygvv5y4tuwalnf3ttnqjn57ef6rmcqg0s53akem560jh8ptemjcmytn3lrlatw4hv9smg88exv3v4f4lqnp96s0psdrhxsp6pp75q",# payment_request
    "",# no error
))
def pay_invoice_side_effect(payment_request: str):
    invoice = bolt11.decode(payment_request)
    return PaymentResponse(
        True,# ok
        invoice.payment_hash,# checking_id (i.e. payment_hash)
        0,# fee_msat
        "",# no error
    )
WALLET.pay_invoice = AsyncMock(side_effect=pay_invoice_side_effect)
WALLET.get_invoice_status = AsyncMock(return_value=PaymentStatus(
    True,# paid
))
WALLET.get_payment_status = AsyncMock(return_value=PaymentStatus(
    True,# paid
))
