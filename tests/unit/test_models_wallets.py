import json

import pytest

from lnbits.core.models import Wallet


@pytest.mark.parametrize("keep", [None, True, False])
def test_with_wallet_keys(keep: bool | None):
    wallet = Wallet(
        id="wallet-id",
        user="user-id",
        name="Wallet",
        adminkey="admin-key",
        inkey="invoice-key",
    )
    original = json.loads(wallet.json())

    result = (
        wallet.with_wallet_keys()
        if keep is None
        else wallet.with_wallet_keys(keep=keep)
    )

    assert result is wallet
    expected = original
    if keep is False:
        expected = {k: v for k, v in original.items() if k not in {"adminkey", "inkey"}}
        assert not hasattr(wallet, "adminkey")
        assert not hasattr(wallet, "inkey")
        assert wallet.with_wallet_keys(keep=False) is wallet
    else:
        assert wallet.adminkey == original["adminkey"]
        assert wallet.inkey == original["inkey"]
    assert json.loads(wallet.json()) == expected
