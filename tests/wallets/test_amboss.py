import hashlib
from types import SimpleNamespace

import pytest
from pytest_httpserver import HTTPServer

from lnbits.wallets import amboss as amboss_module
from lnbits.wallets.amboss import (
    _BASE_ASSET_ONLY,
    AmbossApiError,
    AmbossWallet,
    _pick_rest_socket,
    _self_check,
)


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

# A decodable bolt11, so pay_invoice gets past bolt11_decode.
_BOLT11 = (
    "lnbc5550n1pnq9jg3sp52rvwstvjcypjsaenzdh0h30jazvzsf8aaye0julprtth9kysxtuspp5e5s3"
    "z7felv4t9zrcc6wpn7ehvjl5yzewanzl5crljdl3jgeffyhqdq2f38xy6t5wvxqzjccqpjrzjq0yzeq"
    "76ney45hmjlnlpvu0nakzy2g35hqh0dujq8ujdpr2e42pf2rrs6vqpgcsqqqqqqqqqqqqqqeqqyg9qx"
    "pqysgqwftcx89k5pp28435pgxfl2vx3ksemzxccppw2j9yjn0ngr6ed7wj8ztc0d5kmt2mvzdlcgrlu"
    "dhz7jncd5l5l9w820hc4clpwhtqj3gq62g66n"
)


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
    # Pre-satisfy the asset check: it shares the `_gql` mock below, which is
    # shaped as a create_send response, so leaving it unset makes pay_invoice
    # fail on a KeyError before it ever reaches the guard under test.
    amboss_wallet._asset_verified = True
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
    assert (
        result.error_message == "payment_request does not match the submitted invoice"
    )
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


def test_pick_rest_socket_prefers_litd():
    sockets = {"lnd": {"rest": "https://lnd:8080"}, "litd": {"rest": "https://litd:80"}}

    assert _pick_rest_socket(sockets) == "https://litd:80"


def test_pick_rest_socket_skips_plaintext_litd_for_usable_lnd():
    # The macaroon travels on this socket, so a plaintext litd endpoint must not
    # win — and must not hide the https lnd socket on the same node either.
    sockets = {"lnd": {"rest": "https://lnd:8080"}, "litd": {"rest": "http://litd:80"}}

    assert _pick_rest_socket(sockets) == "https://lnd:8080"


def test_pick_rest_socket_rejects_plaintext_only_node():
    assert _pick_rest_socket({"lnd": {"rest": "http://lnd:8080"}}) is None
    assert _pick_rest_socket({"litd": None, "lnd": None}) is None


def _node_permissions(*nodes: dict) -> dict:
    return {
        "payment": {
            "wallet": {
                "find_one": {
                    "asset": {"type": "BASE_ASSET"},
                    "node_permissions": {
                        "encrypted_symmetric_key": "enc-sym",
                        "nodes": list(nodes),
                    },
                }
            }
        }
    }


@pytest.mark.anyio
async def test_resolve_node_skips_plaintext_node_for_a_later_https_one(
    amboss_wallet: AmbossWallet, mocker
):
    # The socket predicate is unit-tested above; this covers the composition
    # through _resolve_node's next(...), i.e. that an unusable node does not
    # end the search and take a usable later node down with it.
    amboss_wallet.team_password = "CorrectHorseBatteryStaple"
    # These two differ on exactly one axis: the scheme. Same macaroon, same
    # socket kind. Vary anything else and a predicate keyed off that other axis
    # — the macaroon, or "is it litd" — passes while ignoring the scheme, which
    # is the one property this policy exists to enforce. litd-over-lnd
    # preference is pinned by the _pick_rest_socket tests above instead.
    plaintext = {
        "encrypted_macaroon": "enc-mac",
        "sockets": {"litd": {"rest": "http://a"}},
    }
    usable = {
        "encrypted_macaroon": "enc-mac",
        "sockets": {"litd": {"rest": "https://b"}},
    }
    mocker.patch.object(
        amboss_module,
        "create_master_password_hash",
        return_value=("master-key", "password-hash"),
    )
    mocker.patch.object(
        amboss_wallet, "_gql", return_value=_node_permissions(plaintext, usable)
    )
    mocker.patch.object(amboss_module, "nip44_decrypt", side_effect=["sym-key", "00ff"])

    node, macaroon_hex = await amboss_wallet._resolve_node("team-id")

    assert node is usable
    assert macaroon_hex == "00ff"


@pytest.mark.anyio
async def test_resolve_node_rejects_a_wallet_with_only_plaintext_nodes(
    amboss_wallet: AmbossWallet, mocker
):
    amboss_wallet.team_password = "CorrectHorseBatteryStaple"
    plaintext = {
        "encrypted_macaroon": "enc-mac",
        "sockets": {"litd": {"rest": "http://a"}},
    }
    mocker.patch.object(
        amboss_module,
        "create_master_password_hash",
        return_value=("master-key", "password-hash"),
    )
    mocker.patch.object(
        amboss_wallet, "_gql", return_value=_node_permissions(plaintext)
    )

    with pytest.raises(ValueError, match="no https"):
        await amboss_wallet._resolve_node("team-id")


@pytest.mark.anyio
async def test_send_context_rejects_password_that_strips_below_argon2_salt(
    amboss_wallet: AmbossWallet, mocker
):
    # Eight characters, but the KDF salts with the stripped string, so Argon2id
    # would reject it as a 2-byte salt. A trailing newline from an env file is
    # the realistic case.
    amboss_wallet.team_password = "ab      "
    mocker.patch.object(
        amboss_wallet,
        "_gql",
        return_value={
            "payment": {
                "id": "team-id",
                "wallet": {"find_one": {"environment": {"type": "PRODUCTION"}}},
            }
        },
    )

    with pytest.raises(ValueError, match="at least 8 characters"):
        await amboss_wallet._send_context()


@pytest.mark.anyio
async def test_status_maps_sats_balance_to_msat(
    http_wallet: AmbossWallet, gql_server: HTTPServer
):
    _expect_gql(gql_server, _wallet_data(balance=55))

    status = await http_wallet.status()

    assert status.error_message is None
    assert status.balance_msat == 55000


@pytest.mark.anyio
async def test_pay_via_node_returns_in_band_when_socket_is_unusable(
    amboss_wallet: AmbossWallet,
):
    # Unreachable via _resolve_node, but it must stay a response rather than a
    # raise: _pay_via_node is called outside pay_invoice's try blocks, so an
    # escaping error would reach core as a 400 and strand the payment PENDING.
    result = await amboss_wallet._pay_via_node(
        node={"sockets": {"lnd": {"rest": "http://plaintext"}}},
        macaroon_hex="00ff",
        payment_request=_BOLT11,
        fee_limit_msat=1000,
        checking_id="a" * 64,
    )

    # Nothing was sent to the node, so this is terminal, not pending.
    assert result.ok is False
    assert result.checking_id == "a" * 64


@pytest.mark.anyio
async def test_status_reports_a_graphql_error_as_itself(
    http_wallet: AmbossWallet, gql_server: HTTPServer
):
    # The likeliest real cases: a mistyped wallet id or a dead API key. The
    # endpoint answered, so "Unable to connect" would send an admin to DNS.
    _expect_gql(gql_server, {"errors": [{"message": "wallet not found"}]})

    status = await http_wallet.status()

    assert status.error_message == "Amboss API error: wallet not found"
    assert status.balance_msat == 0


@pytest.mark.anyio
async def test_status_reports_a_throttle_as_itself(
    http_wallet: AmbossWallet, gql_server: HTTPServer
):
    # Rate limiting is the other common one, and it arrives as a status code
    # rather than a GraphQL errors array.
    gql_server.expect_request(uri=_GQL_URI, method="POST").respond_with_json(
        {"message": "Too Many Requests"}, status=429
    )

    status = await http_wallet.status()

    assert status.error_message == "Amboss API error: HTTP 429"
    assert status.balance_msat == 0


@pytest.mark.anyio
async def test_status_reports_missing_asset_type_as_itself(
    http_wallet: AmbossWallet, gql_server: HTTPServer
):
    # Schema drift on `asset` is not a connectivity problem: the endpoint
    # answered. Same rule as the balance below it.
    drifted = _wallet_data()
    del drifted["data"]["payment"]["wallet"]["find_one"]["asset"]
    _expect_gql(gql_server, drifted)

    status = await http_wallet.status()

    assert status.error_message == "wallet response has no asset type"
    assert status.balance_msat == 0


@pytest.mark.anyio
async def test_status_reports_unusable_balance_as_itself(
    http_wallet: AmbossWallet, gql_server: HTTPServer
):
    # A balance that will not parse is not a connectivity problem either.
    broken = _wallet_data()
    broken["data"]["payment"]["wallet"]["find_one"]["balance"] = {"balance": "abc"}
    _expect_gql(gql_server, broken)

    status = await http_wallet.status()

    assert status.error_message == "wallet response has no usable balance"
    assert status.balance_msat == 0


@pytest.mark.anyio
async def test_status_reports_wrong_asset_as_itself_not_a_connection_error(
    http_wallet: AmbossWallet, gql_server: HTTPServer
):
    # Folding this into "Unable to connect to ..." sends an admin debugging DNS
    # for what is really a misconfigured wallet.
    _expect_gql(gql_server, _wallet_data(asset_type="TAPROOT_ASSET"))

    status = await http_wallet.status()

    assert status.error_message == _BASE_ASSET_ONLY
    assert status.balance_msat == 0


@pytest.mark.anyio
async def test_gql_raises_the_graphql_error_message(
    http_wallet: AmbossWallet, gql_server: HTTPServer
):
    # rails reports failures as a GraphQL `errors` array on an HTTP 200, so
    # raise_for_status alone would read this as success. Assert the message is
    # what propagates — a bare failure would also happen without this handling.
    _expect_gql(gql_server, {"errors": [{"message": "wallet not found"}]})

    with pytest.raises(AmbossApiError, match="wallet not found"):
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
    assert invoice.error_message == _BASE_ASSET_ONLY
    # Short-circuited: only the asset query went out, never create_receive.
    assert len(gql_server.log) == 1


@pytest.mark.anyio
async def test_pay_invoice_rejects_taproot_asset_wallet(
    http_wallet: AmbossWallet, gql_server: HTTPServer
):
    # Sandbox wallets never reach _resolve_node, so pay_invoice has to do its
    # own asset check.
    # The first response deliberately answers *both* the asset query and the
    # send-context query, and the second is a successful create_send: without
    # the guard the send goes through and returns pending, so this test can
    # only pass if the asset check runs first and short-circuits.
    _expect_gql(
        gql_server,
        {
            "data": {
                "payment": {
                    "id": "team-id",
                    "wallet": {
                        "find_one": {
                            "id": "test-wallet-id",
                            "balance": {"balance": 55},
                            "asset": {"type": "TAPROOT_ASSET"},
                            "environment": {"type": "SANDBOX"},
                        }
                    },
                }
            }
        },
        ordered=True,
    )
    _expect_gql(
        gql_server,
        {
            "data": {
                "payment": {
                    "transaction": {
                        "create_send": {
                            "payment_hash": "a" * 64,
                            "payment_request": _BOLT11,
                        }
                    }
                }
            }
        },
        ordered=True,
    )

    result = await http_wallet.pay_invoice(_BOLT11, fee_limit_msat=1000)

    assert result.ok is False
    assert result.error_message == _BASE_ASSET_ONLY
    assert len(gql_server.log) == 1


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
    # Guards against an always-pending stub: the lookup really was attempted.
    assert len(gql_server.log) == 1
