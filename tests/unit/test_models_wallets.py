import json

import pytest

from lnbits.core.models import Wallet


@pytest.mark.parametrize(
    "wallet_type, can_send, can_receive",
    [
        ("lightning", True, True),
        ("fiat", False, True),
        ("receive-only", False, True),
        ("onchain", False, False),
        ("liquid", False, False),
    ],
)
def test_wallet_type_payment_permissions(wallet_type, can_send, can_receive):
    wallet = Wallet(
        id="wallet-id",
        user="user-id",
        name="Wallet",
        adminkey="admin-key",
        inkey="invoice-key",
        wallet_type=wallet_type,
    )
    assert wallet.can_view_payments
    assert wallet.can_send_payments is can_send
    assert wallet.can_receive_payments is can_receive


@pytest.mark.parametrize("keep", [None, True, False])
def test_copy_with_keys(keep: bool | None):
    wallet = Wallet(
        id="wallet-id",
        user="user-id",
        name="Wallet",
        adminkey="admin-key",
        inkey="invoice-key",
    )
    original = json.loads(wallet.json())

    result = (
        wallet.copy_with_keys() if keep is None else wallet.copy_with_keys(keep=keep)
    )

    assert isinstance(result, Wallet)
    assert result is not wallet
    assert json.loads(wallet.json()) == original
    expected = original
    if keep is False:
        expected = {**original, "adminkey": "*" * 32, "inkey": "*" * 32}
    assert json.loads(result.json()) == expected
    assert Wallet(**result.dict()) == result
