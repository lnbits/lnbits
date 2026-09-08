import hashlib
from types import SimpleNamespace

import pytest
from pytest_httpserver import HTTPServer

from lnbits.wallets import amboss as amboss_module
from lnbits.wallets.amboss import AmbossWallet, _self_check


@pytest.fixture
def amboss_wallet(settings):
    settings.amboss_service_api_key = "test-key"
    settings.amboss_wallet_id = "test-wallet-id"
    return AmbossWallet()


@pytest.fixture
def gql_server():
    """A private server on an ephemeral port. Deliberately not the shared
    `httpserver` fixture: that one is session-scoped and `test_rest_wallets.py`
    pins it to port 8555, so borrowing it here would move it."""
    server = HTTPServer(host="127.0.0.1", port=0)
    server.start()
    yield server
    server.clear()
    server.stop()


@pytest.fixture
def http_wallet(settings, gql_server: HTTPServer):
    """A wallet pointed at a local mock server, so the tests below exercise the
    real httpx + `_gql` path instead of mocking `_gql` away."""
    settings.amboss_service_api_key = "test-key"
    settings.amboss_wallet_id = "test-wallet-id"
    settings.amboss_api_endpoint = gql_server.url_for("/graphql")
    return AmbossWallet()


# `_gql` posts to "", which httpx resolves against the base_url as a directory.
_GQL_URI = "/graphql/"


def _expect_gql(server: HTTPServer, response: dict, ordered: bool = False):
    expect = server.expect_ordered_request if ordered else server.expect_request
    expect(uri=_GQL_URI, method="POST").respond_with_json(response)


def _wallet_data(asset_type: str = "BASE_ASSET", balance: int = 55) -> dict:
    return {
        "data": {
            "payment": {
                "wallet": {
                    "find_one": {
                        "id": "test-wallet-id",
                        "balance": {"balance": balance},
                        "asset": {"type": asset_type},
                    }
                }
            }
        }
    }


def test_self_check():
    # Only wired up under `python -m lnbits.wallets.amboss` otherwise — this
    # is what actually proves the ported crypto in CI.
    _self_check()


@pytest.mark.anyio
async def test_pay_invoice_pre_dispatch_error_is_terminal(
    amboss_wallet: AmbossWallet, mocker
):
    # Nothing reaches rails on a bad bolt11 — must be ok=False, not pending.
    mocker.patch.object(amboss_module, "bolt11_decode", side_effect=ValueError("bad"))
    gql = mocker.patch.object(amboss_wallet, "_gql")

    result = await amboss_wallet.pay_invoice("not-a-bolt11", fee_limit_msat=1000)

    assert result.ok is False
    gql.assert_not_called()


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


@pytest.mark.anyio
async def test_status_maps_sats_balance_to_msat(
    http_wallet: AmbossWallet, gql_server: HTTPServer
):
    _expect_gql(gql_server, _wallet_data(balance=55))

    status = await http_wallet.status()

    assert status.error_message is None
    assert status.balance_msat == 55000


@pytest.mark.anyio
async def test_gql_raises_the_graphql_error_message(
    http_wallet: AmbossWallet, gql_server: HTTPServer
):
    # rails reports failures as a GraphQL `errors` array on an HTTP 200, so
    # raise_for_status alone would read this as success. Assert the message is
    # what propagates — a bare failure would also happen without this handling.
    _expect_gql(gql_server, {"errors": [{"message": "wallet not found"}]})

    with pytest.raises(ValueError, match="wallet not found"):
        await http_wallet._gql("query { x }", {})


@pytest.mark.anyio
async def test_create_invoice_rejects_taproot_asset_wallet(
    http_wallet: AmbossWallet, gql_server: HTTPServer
):
    # A Taproot Asset wallet's "1000" is 1000 USDTL, not 1000 sats — refuse it
    # before an invoice exists rather than letting lnbits book the wrong unit.
    # The second response is a *successful* create_receive, so this test fails
    # if the guard stops short-circuiting instead of passing on a side effect.
    _expect_gql(gql_server, _wallet_data(asset_type="TAPROOT_ASSET"), ordered=True)
    _expect_gql(
        gql_server,
        {
            "data": {
                "payment": {
                    "transaction": {
                        "create_receive": {"id": "tx-1", "payment_request": "lnbc1..."}
                    }
                }
            }
        },
        ordered=True,
    )

    invoice = await http_wallet.create_invoice(1000)

    assert invoice.ok is False
    assert invoice.checking_id is None


@pytest.mark.anyio
async def test_create_invoice_sends_lnurl_description_hash(
    http_wallet: AmbossWallet, gql_server: HTTPServer
):
    metadata = b'[["text/plain","zap me"]]'
    # First call is the asset check, second creates the invoice.
    _expect_gql(gql_server, _wallet_data(), ordered=True)
    _expect_gql(
        gql_server,
        {
            "data": {
                "payment": {
                    "transaction": {
                        "create_receive": {"id": "tx-1", "payment_request": "lnbc1..."}
                    }
                }
            }
        },
        ordered=True,
    )

    invoice = await http_wallet.create_invoice(
        1000, memo="ignored", unhashed_description=metadata
    )

    assert invoice.ok is True
    assert invoice.checking_id == "tx-1"
    # LUD-06 requires the invoice's description_hash to be sha256(metadata);
    # assert it went out on the wire, not just that the call succeeded.
    sent = gql_server.log[-1][0].get_json()["variables"]["input"]
    assert sent["bolt11"]["description_hash"] == hashlib.sha256(metadata).hexdigest()


@pytest.mark.anyio
async def test_get_payment_status_pending_while_tx_not_yet_in_ledger(
    http_wallet: AmbossWallet, gql_server: HTTPServer
):
    # find_one errors until the send is visible; that must read as pending, not
    # failed, or core would treat an in-flight payment as never sent.
    _expect_gql(gql_server, {"errors": [{"message": "Payments transaction not found"}]})

    status = await http_wallet.get_payment_status("00" * 32)

    assert status.paid is None
