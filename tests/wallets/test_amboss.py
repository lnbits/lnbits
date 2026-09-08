from types import SimpleNamespace

import pytest

from lnbits.wallets import amboss as amboss_module
from lnbits.wallets.amboss import AmbossWallet


@pytest.fixture
def amboss_wallet(settings):
    settings.amboss_service_api_key = "test-key"
    settings.amboss_wallet_id = "test-wallet-id"
    return AmbossWallet()


@pytest.mark.anyio
async def test_pay_invoice_rejects_payment_request_hash_mismatch(
    amboss_wallet: AmbossWallet, mocker
):
    submitted = SimpleNamespace(payment_hash="a" * 64, amount_msat=1000)
    # rails handing back an invoice for a different payment_hash than the one
    # we submitted must never be paid.
    echoed = SimpleNamespace(payment_hash="b" * 64, amount_msat=1000)
    mocker.patch.object(amboss_module, "bolt11_decode", side_effect=[submitted, echoed])
    mocker.patch.object(
        amboss_wallet,
        "_send_context",
        return_value=("team-id", False, {"sockets": {"lnd": {"rest": "x"}}}, "mac"),
    )
    mocker.patch.object(
        amboss_wallet,
        "_gql",
        return_value={
            "payment": {
                "transaction": {
                    "create_send": {
                        "payment_hash": submitted.payment_hash,
                        "payment_request": "irrelevant, decode is mocked",
                    }
                }
            }
        },
    )
    pay_via_node = mocker.patch.object(amboss_wallet, "_pay_via_node")

    result = await amboss_wallet.pay_invoice("bolt11-string", fee_limit_msat=1000)

    assert result.ok is False
    pay_via_node.assert_not_called()


def test_map_tx_status_parses_fractional_sat_fee_and_preimage(
    amboss_wallet: AmbossWallet,
):
    # LND's fee_msat isn't always a multiple of 1000, so the sats fee rails
    # stores can be a fractional string (e.g. "1.234"); int() on that raises.
    status = amboss_wallet._map_tx_status(
        {"status": "COMPLETED", "fee": "1.234", "preimage": "deadbeef"}
    )

    assert status.paid is True
    assert status.fee_msat == 1234
    assert status.preimage == "deadbeef"
